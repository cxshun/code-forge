"""应用配置。

基于 pydantic-settings，按环境变量加载（dev/prod/test）。凭证（DB / Redis / 飞书 /
Anthropic key）以占位默认值给出，生产由 ``.env`` 注入。对齐 design §3.1 与 D32。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 运行环境
    app_env: Literal["dev", "prod", "test"] = "dev"
    debug: bool = Field(default=False)

    # 服务监听
    host: str = "0.0.0.0"
    port: int = 8000

    # PostgreSQL（异步 asyncpg）
    pg_dsn: str = "postgresql+asyncpg://codeforge:codeforge@localhost:5432/codeforge"

    # Redis（任务队列 / 事件总线 / 缓存）
    redis_url: str = "redis://localhost:6379/0"

    # 凭证加密主密钥（D32 / NF4.2.4），生产必须注入
    secret_key: str = "dev-insecure-secret-key-change-me"

    # 飞书开放平台（占位，T3.3 / T4.1 用）
    feishu_base_url: str = "https://open.feishu.cn/open-apis"

    # 飞书测试凭证（本地集成验证用，从 .env 读取；勿提交真实值）
    feishu_test_app_id: str = ""
    feishu_test_app_secret: str = ""
    feishu_test_chat_id: str = ""

    # Anthropic（占位，T5.1 用；国内可切 GLM，见 D3）
    anthropic_api_key: str = ""
    anthropic_model: str = ""  # 留空则用 Provider 默认（claude-sonnet-5）

    # OpenAI 兼容端点（D3 多模型备选 / D34 摘要模型可指）：智谱 GLM / 通义 / DeepSeek /
    # Moonshot 等任意 OpenAI Chat Completions 兼容服务。三项都填才启用，不绑定具体厂商。
    openai_compatible_api_key: str = ""
    openai_compatible_base_url: str = ""  # 如 https://open.bigmodel.cn/api/paas/v4
    openai_compatible_model: str = ""  # 如 glm-4.6 / qwen-plus / deepseek-chat

    # P3 D-CE.4: model 元数据覆盖（JSON 字符串），用于新 model 上线无需发版
    # 例：{"my-custom-model":{"context_window":32000,"max_output_tokens":4096}}
    model_overrides: str = ""

    # 子代理并行度上限（design D33：防 fork 爆炸，超限排队）
    agent_max_concurrency: int = 5

    # 文件系统根（design §2.3 工作空间 / 全局广场）
    data_dir: str = "./data"

    # Session cookie（自建账号密码鉴权，D32 / T1.4）
    session_cookie_name: str = "cf_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 天

    # TTL 清理（T10.4）
    span_ttl_days: int = 30
    payload_ttl_days: int = 7
    max_runs_per_chat: int = 500

    # 跨 session 历史加载：新 Run 启动时从最近一次已完成 session 加载多少条消息
    chat_history_max_messages: int = 20

    # 单聊（p2p）自动建 WS 的 owner（P2 direct-chat D-DC.3 / D-DC.7）：未配置则关闭单聊自动接受
    p2p_workspace_owner_id: int | None = None

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def pg_dsn_effective(self) -> str:
        """实际 DSN：test 环境强制切到 ``codeforge_test`` 库，避免污染 dev/prod。

        测试 fixture 的 ``reset_all()`` 会全表 TRUNCATE，必须隔离到独立测试库。
        """
        url = make_url(self.pg_dsn)
        if self.is_test:
            url = url.set(database="codeforge_test")
        # SQLAlchemy 2.0 起 str(url) 默认把密码渲染为 `***`，会导致拿此串去连接时
        # 认证失败（InvalidPasswordError）。必须显式保留真实密码。
        return url.render_as_string(hide_password=False)

    @property
    def workspaces_root(self) -> str:
        """所有 WS 物理目录的父目录：{data_dir}/workspaces/{ws_id}/。"""
        return f"{self.data_dir}/workspaces"

    @property
    def skills_root(self) -> str:
        """全局 Skill 广场：{data_dir}/skills/{skill_id}/。"""
        return f"{self.data_dir}/skills"


@lru_cache
def get_settings() -> Settings:
    """单例 Settings（lru_cache 保证进程内一份）。"""
    return Settings()


settings = get_settings()
