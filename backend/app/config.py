"""应用配置。

基于 pydantic-settings，按环境变量加载（dev/prod/test）。凭证（DB / Redis / 飞书 /
Anthropic key）以占位默认值给出，生产由 ``.env`` 注入。对齐 design §3.1 与 D32。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # 文件系统根（design §2.3 工作空间 / 全局广场）
    data_dir: str = "./data"

    # Session cookie（自建账号密码鉴权，D32 / T1.4）
    session_cookie_name: str = "cf_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 天

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

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
