"""安全基础：凭证加密（Fernet）/ 密码哈希（argon2）/ secret 脱敏。

对齐 D32 / NF4.2.4（敏感凭证静态加密）。
- Fernet 主密钥从 settings.secret_key 派生（SHA-256 → url-safe base64）。
- git token / 飞书 app_secret / Anthropic key 等凭证落盘前 encrypt_secret，DB 与日志
  均不存明文。
- 密码用 argon2 哈希（PasswordHasher）。
- mask_secret 列表/详情脱敏，前后各 4 位。
"""

import base64
import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.config import settings

_hasher = PasswordHasher()


def _fernet_key() -> bytes:
    """从 secret_key 派生 Fernet 兼容的 32 字节 url-safe base64 key。"""
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_fernet_key())


def encrypt_secret(plaintext: str) -> str:
    """凭证加密 → 密文字符串（存 DB）。"""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    """凭证解密 → 明文（仅在需要原值时调用，如发飞书请求）。"""
    return _fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        # 哈希格式异常等，统一视为校验失败
        return False


def mask_secret(secret: str) -> str:
    """脱敏：前后各 4 位，中间省略。过短则全掩。"""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"


# 配置结构中视为敏感的字段名（小写匹配）
SECRET_KEY_NAMES = {
    "password",
    "secret",
    "app_secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
}


def encrypt_secrets(value):
    """递归：dict / list 中名字命中 SECRET_KEY_NAMES 的字符串值加密。"""
    if isinstance(value, dict):
        return {
            k: (
                encrypt_secret(v)
                if k.lower() in SECRET_KEY_NAMES and isinstance(v, str)
                else encrypt_secrets(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [encrypt_secrets(v) for v in value]
    return value


def mask_secrets(value):
    """递归：对已加密的 secret 字段解密后脱敏返回（列表 / 详情用）。"""
    if isinstance(value, dict):
        return {
            k: (
                _safe_mask(v)
                if k.lower() in SECRET_KEY_NAMES and isinstance(v, str)
                else mask_secrets(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [mask_secrets(v) for v in value]
    return value


def _safe_mask(ciphertext: str) -> str:
    """解密失败（非密文）时退化为整体脱敏，避免异常外泄。"""
    try:
        return mask_secret(decrypt_secret(ciphertext))
    except Exception:
        return "*" * 8
