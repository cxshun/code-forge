"""OpenAICompatibleProvider 测试（mock httpx，不连真实服务）。"""

import pytest

from app.config import settings
from app.providers.base import Message
from app.providers.openai_compatible_provider import OpenAICompatibleProvider

pytestmark = pytest.mark.asyncio


class _FakeResp:
    def __init__(self, data: dict, status: int = 200) -> None:
        self._data = data
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._data


def _cfg(monkeypatch, base: str = "https://api.example.com/v1", model: str = "some-model") -> None:
    monkeypatch.setattr(settings, "openai_compatible_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_compatible_base_url", base)
    monkeypatch.setattr(settings, "openai_compatible_model", model)


async def test_chat_parses_openai_response(monkeypatch):
    _cfg(monkeypatch)
    captured: dict = {}

    async def fake_post(self, url, *, headers=None, json=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json
        return _FakeResp(
            {
                "choices": [{"message": {"content": "hello", "tool_calls": None}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    provider = OpenAICompatibleProvider()
    out, usage = await provider.chat([Message(role="user", content="hi")])
    assert out[0].content == "hello"
    assert usage.input_tokens == 10
    assert usage.output_tokens == 5
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["payload"]["model"] == "some-model"


async def test_chat_parses_tool_calls(monkeypatch):
    _cfg(monkeypatch)

    async def fake_post(self, url, *, headers=None, json=None, **kw):
        return _FakeResp(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "function": {"name": "search", "arguments": '{"q":"x"}'},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    provider = OpenAICompatibleProvider()
    out, _ = await provider.chat([Message(role="user", content="x")])
    assert out[0].tool_calls == [{"id": "c1", "name": "search", "input": '{"q":"x"}'}]


async def test_count_tokens_char_estimate(monkeypatch):
    """L2 fallback path: tiktoken 不可用时走 len//4 字符估算（design D-CE.3）。"""
    _cfg(monkeypatch)
    provider = OpenAICompatibleProvider()
    # 模拟 tiktoken 未安装，测试 fallback 路径
    monkeypatch.setattr(provider, "_enc", None)
    usage = await provider.count_tokens([Message(role="user", content="x" * 40)])
    assert usage.input_tokens == 10  # 40 // 4


async def test_unavailable_without_full_config(monkeypatch):
    monkeypatch.setattr(settings, "openai_compatible_api_key", "")
    monkeypatch.setattr(settings, "openai_compatible_base_url", "")
    monkeypatch.setattr(settings, "openai_compatible_model", "")
    provider = OpenAICompatibleProvider()
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await provider.chat([Message(role="user", content="hi")])


async def test_name_and_window(monkeypatch):
    _cfg(monkeypatch)
    provider = OpenAICompatibleProvider()
    assert provider.name == "openai_compatible"
    assert provider.context_window == 128_000


async def test_arbitrary_base_url_and_model(monkeypatch):
    """通用性：DeepSeek 端点 + 模型同样可用（证明非智谱绑定）。"""
    _cfg(monkeypatch, base="https://api.deepseek.com", model="deepseek-chat")
    captured: dict = {}

    async def fake_post(self, url, *, headers=None, json=None, **kw):
        captured["url"] = url
        captured["model"] = json["model"]
        return _FakeResp({"choices": [{"message": {"content": "ok"}}], "usage": {}})

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    provider = OpenAICompatibleProvider()
    await provider.chat([Message(role="user", content="x")])
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["model"] == "deepseek-chat"
