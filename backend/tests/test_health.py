"""健康检查接口测试（task T0.1 验收）。"""

from fastapi.testclient import TestClient

from app.main import app


def test_healthz_ok() -> None:
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
