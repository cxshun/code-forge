"""ContextConfig 解析测试（D34 WS 级配置容错）。"""

from app.agent.context_config import ContextConfig


def test_default_when_none():
    cfg = ContextConfig.from_ws(None)
    assert cfg.enabled is True
    assert cfg.trigger1 == 0.5
    assert cfg.trigger2 == 0.75
    assert cfg.clear_keep == 6
    assert cfg.compact_recent == 6
    assert cfg.summary_provider == "anthropic"


def test_default_when_empty():
    cfg = ContextConfig.from_ws({})
    assert cfg.enabled is True


def test_parses_known_keys():
    cfg = ContextConfig.from_ws(
        {"trigger1": 0.6, "summary_provider": "glm", "summary_model": "glm-4", "exclude_tools": ["Bash"]}
    )
    assert cfg.trigger1 == 0.6
    assert cfg.summary_provider == "glm"
    assert cfg.summary_model == "glm-4"
    assert cfg.exclude_tools == ["Bash"]
    # 未设的用默认
    assert cfg.trigger2 == 0.75


def test_unknown_keys_ignored():
    cfg = ContextConfig.from_ws({"foo": "bar", "enabled": False})
    assert cfg.enabled is False
    # 未知 key 不影响其它字段
    assert cfg.trigger1 == 0.5


def test_invalid_value_falls_back_to_default():
    # trigger1 非法 → Pydantic 校验失败 → from_ws 捕获 → 默认
    cfg = ContextConfig.from_ws({"trigger1": "not-a-number"})  # type: ignore[dict-item]
    assert cfg.trigger1 == 0.5
