"""FeishuApp 模型（飞书企业自建应用，D7）。

每个 App 对应一个独立飞书 WebSocket 长连接（T4.2）。``app_secret`` 经应用层加密
存储（D32 / NF4.2.4），列名 ``app_secret_enc``；列表 / 详情脱敏仅展示前后各 4 位。
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FeishuApp(Base, TimestampMixin):
    __tablename__ = "feishu_apps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    # 应用层加密密文（Fernet），永不存明文
    app_secret_enc: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # 连接状态：disconnected / connecting / connected / error
    connection_status: Mapped[str] = mapped_column(
        String(32), default="disconnected", nullable=False
    )
