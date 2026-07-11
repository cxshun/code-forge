"""敏感信息脱敏管线（design §7.6 / D30 / NF4.6.2）。

所有 payload 落盘前过 ``redact()``，统一脱敏，不依赖 Agent 自觉。
覆盖两类规则：
- 结构化字段名匹配：password / api_key / secret / token 等 → 值替换为 ***REDACTED***
- 正则模式匹配：AWS Key / Bearer token / 私钥块 / GitHub token / Slack token / 连接串密码

命中后保留字段名与结构，只脱敏值。
"""

import copy
import logging
import re

log = logging.getLogger("observability.redaction")

REDACTED = "***REDACTED***"

# 字段名匹配（复用 core/security.SECRET_KEY_NAMES 并扩展）
SENSITIVE_KEY_NAMES = {
    "password",
    "secret",
    "app_secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "access_key",
    "secret_key",
    "auth_token",
    "bearer",
    "private_key",
    "client_secret",
    "access_token",
    "refresh_token",
}

# 正则模式（命中即替换为 REDACTED）
_REGEX_PATTERNS: list[re.Pattern] = [
    # AWS Access Key ID (AKIA... 20 chars)
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # AWS Secret Access Key (40 char base64-ish after "aws_secret" context)
    re.compile(r"(aws_secret_access_key[=:\s]+)([A-Za-z0-9/+=]{40})", re.IGNORECASE),
    # Generic API key pattern (key=... or api_key=...)
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{20,}['\"]?"),
    # Bearer token
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.=]{20,}"),
    # GitHub token (ghp_... / gho_... / ghs_...)
    re.compile(r"gh[opsu]_[A-Za-z0-9]{36}"),
    # Slack token (xoxb-... / xoxp-... — includes dashes between segments)
    re.compile(r"xox[bpors]-[0-9a-zA-Z\-]{10,}"),
    # Private key blocks (PEM)
    re.compile(r"-----BEGIN\s+(RSA\s+|EC\s+|OPENSSH\s+|PGP\s+)?PRIVATE\s+KEY-----.*?-----END\s+(RSA\s+|EC\s+|OPENSSH\s+|PGP\s+)?PRIVATE\s+KEY-----", re.DOTALL),
    # Connection string password (postgres://user:password@host)
    re.compile(r"(://[^:]+:)([^@]+)(@)"),
]


def redact(data):
    """递归脱敏 dict / list / str。

    返回副本，不修改原数据。
    """
    return _redact_value(copy.deepcopy(data))


def _redact_value(value):
    if isinstance(value, dict):
        return {k: _redact_field(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _redact_field(key: str, value):
    """字段名命中 → 整值替换。"""
    if key.lower() in SENSITIVE_KEY_NAMES and isinstance(value, str):
        return REDACTED
    return _redact_value(value)


def _redact_string(s: str) -> str:
    """正则模式匹配 → 替换命中部分。

    带捕获组的模式（如 AWS secret / 连接串）保留前缀，仅脱敏值。
    """
    for pattern in _REGEX_PATTERNS:
        s = pattern.sub(_redact_replacer, s) if pattern.groups >= 2 else pattern.sub(REDACTED, s)
    return s


def _redact_replacer(m: re.Match) -> str:
    """保留第一个捕获组，其余替换为 REDACTED。"""
    groups = m.groups()
    if len(groups) >= 3:
        return f"{groups[0]}{REDACTED}{groups[-1]}"
    return f"{groups[0]}{REDACTED}"


__all__ = ["REDACTED", "redact"]
