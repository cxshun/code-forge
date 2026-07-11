"""告警扫描引擎（design §7.7 / T10.3）。

定时扫描所有 enabled 规则，计算指标值，对比阈值。
命中后更新 last_triggered_at / last_result，并推送飞书卡片（best-effort）。
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db.models import AlertRule, FeishuChat, Run, RunStatus, Span, Workspace
from app.db.models.alert_rule import RuleType
from app.db.session import async_session_factory

log = logging.getLogger("observability.monitor")

MONITOR_INTERVAL_S = 60


async def _calc_error_rate(ws_id: int, window: int) -> float:
    """窗口内 Run 错误率（error / total）。"""
    since = datetime.now(UTC) - timedelta(minutes=window)
    async with async_session_factory() as s:
        total = await s.scalar(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == ws_id, Run.started_at >= since
            )
        )
        if not total:
            return 0.0
        errors = await s.scalar(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == ws_id,
                Run.started_at >= since,
                Run.status == RunStatus.error.value,
            )
        )
        return (errors or 0) / total


async def _calc_timeout_rate(ws_id: int, window: int) -> float:
    since = datetime.now(UTC) - timedelta(minutes=window)
    async with async_session_factory() as s:
        total = await s.scalar(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == ws_id, Run.started_at >= since
            )
        )
        if not total:
            return 0.0
        timeouts = await s.scalar(
            select(func.count()).select_from(Run).where(
                Run.workspace_id == ws_id,
                Run.started_at >= since,
                Run.status.in_([RunStatus.timeout.value, RunStatus.interrupted.value]),
            )
        )
        return (timeouts or 0) / total


async def _calc_p95_latency(ws_id: int, window: int) -> float:
    """P95 延迟（ms）。简化实现：取窗口内 Run 的 95 分位 duration。"""
    since = datetime.now(UTC) - timedelta(minutes=window)
    async with async_session_factory() as s:
        durations = (await s.scalars(
            select(Span.duration_ms).where(
                Span.workspace_id == ws_id,
                Span.span_type == "run",
                Span.started_at >= since,
                Span.duration_ms.isnot(None),
            ).order_by(Span.duration_ms)
        )).all()
    if not durations:
        return 0.0
    idx = int(len(durations) * 0.95)
    return float(durations[min(idx, len(durations) - 1)])


async def _calc_run_cost(ws_id: int, _window: int) -> float:
    """最新 Run 的 cost_usd 总和。"""
    async with async_session_factory() as s:
        latest_run = await s.scalar(
            select(Run.id).where(Run.workspace_id == ws_id)
            .order_by(Run.started_at.desc()).limit(1)
        )
        if not latest_run:
            return 0.0
        cost = await s.scalar(
            select(func.sum(Span.cost_usd)).where(
                Span.workspace_id == ws_id,
                Span.run_id == latest_run,
                Span.span_type == "llm",
            )
        )
    return float(cost or 0)


async def _calc_ws_daily_cost(ws_id: int, _window: int) -> float:
    """WS 最近 24h 的 cost 总和。"""
    since = datetime.now(UTC) - timedelta(hours=24)
    async with async_session_factory() as s:
        cost = await s.scalar(
            select(func.sum(Span.cost_usd)).where(
                Span.workspace_id == ws_id,
                Span.span_type == "llm",
                Span.started_at >= since,
            )
        )
    return float(cost or 0)


_CALCULATORS = {
    RuleType.error_rate.value: _calc_error_rate,
    RuleType.timeout_rate.value: _calc_timeout_rate,
    RuleType.p95_latency.value: _calc_p95_latency,
    RuleType.run_cost.value: _calc_run_cost,
    RuleType.ws_daily_cost.value: _calc_ws_daily_cost,
}


async def scan_rules() -> int:
    """扫描所有 enabled 规则。返回命中数。"""
    hits = 0
    async with async_session_factory() as s:
        rules = (await s.scalars(
            select(AlertRule).where(AlertRule.enabled.is_(True))
        )).all()
        # 分组按 ws_id 收集命中规则
        triggered: dict[int, list[tuple[AlertRule, float]]] = {}

        for rule in rules:
            calc = _CALCULATORS.get(rule.rule_type)
            if calc is None:
                continue
            try:
                value = await calc(rule.workspace_id, rule.window_minutes)
            except Exception:
                log.exception("calc failed: ws=%s rule=%s", rule.workspace_id, rule.id)
                continue
            rule.last_result = value
            if value > rule.threshold:
                rule.last_triggered_at = datetime.now(UTC)
                hits += 1
                triggered.setdefault(rule.workspace_id, []).append((rule, value))

        await s.commit()

    # 推送飞书卡片（best-effort）
    for ws_id, rule_pairs in triggered.items():
        try:
            await _push_alert_card(ws_id, rule_pairs)
        except Exception:
            log.exception("push alert failed: ws=%s", ws_id)

    return hits


async def _push_alert_card(ws_id: int, rule_pairs: list[tuple[AlertRule, float]]) -> None:
    """推飞书告警卡片。"""
    from app.feishu.cards import build_progress_card
    from app.feishu.client import FeishuClient

    async with async_session_factory() as s:
        chat = await s.scalar(
            select(FeishuChat).where(FeishuChat.workspace_id == ws_id).limit(1)
        )
        if chat is None:
            return
        app_id_val = chat.app_id if hasattr(chat, "app_id") else None
        ws = await s.get(Workspace, ws_id)
        ws_name = ws.name if ws else f"WS#{ws_id}"

    # 查找飞书 App 凭证
    from app.db.models import FeishuApp
    async with async_session_factory() as s:
        fa = await s.scalar(select(FeishuApp).where(FeishuApp.app_id == app_id_val))
        if fa is None:
            log.warning("no feishu app for alert: ws=%s", ws_id)
            return
        from app.core.security import decrypt_secret
        app_secret = decrypt_secret(fa.app_secret)

    lines = [f"**工作空间：** {ws_name}\n"]
    for rule, value in rule_pairs:
        lines.append(f"- {rule.name}：当前值 {value:.4f} > 阈值 {rule.threshold}")
    text = "🚨 告警通知\n" + "\n".join(lines)

    client = FeishuClient(fa.app_id, app_secret)
    await client.send_card(chat.chat_id, build_progress_card(text, footer=None))


async def monitor_loop() -> None:
    """后台监控循环：每 60s 扫描一次。"""
    log.info("monitor loop started")
    while True:
        try:
            hits = await scan_rules()
            if hits:
                log.info("monitor scan: %d rules triggered", hits)
        except Exception:
            log.exception("monitor loop error")
        await asyncio.sleep(MONITOR_INTERVAL_S)
