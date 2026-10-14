"""测试基建：假时钟（限频/过期不用真等）+ 假发送器捕获（验证码从日志侧截获）+ 独立 app。

跑法：cd backend && python -m pytest -n auto（并行，需 pytest-xdist；排查单测时去掉 -n auto）
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import clock
from app.core.config import Settings
from app.db.models import PhoneCode
from app.main import create_app
from app.services.sms import ConsoleSender


class FakeClock:
    def __init__(self) -> None:
        self.t = datetime(2026, 10, 4, 12, 0, 0)

    def now(self) -> datetime:
        return self.t

    def advance(self, **kw: int) -> None:
        self.t += timedelta(**kw)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fc = FakeClock()
    monkeypatch.setattr(clock, "now", fc.now)
    return fc


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    """截获假发送器发出的 (phone, code, purpose)。"""
    out: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        ConsoleSender,
        "send",
        lambda self, phone, code, purpose: out.append((phone, code, purpose)),
    )
    return out


@pytest.fixture
def client(tmp_path, fake: FakeClock, sent: list) -> TestClient:
    app = create_app(
        Settings(
            db_url=f"sqlite:///{tmp_path}/test.db",
            pepper="test-pepper",
            sms_provider="console",
            sms_daily_budget=200,
        )
    )
    return TestClient(app)


def signup(client: TestClient, phone: str, device: str, **card) -> dict:
    body = {"device_marker": device, "card": {"phone": phone, **card}}
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def send_code(client: TestClient, phone: str, purpose: str = "recovery") -> None:
    r = client.post("/api/auth/sms", json={"phone": phone, "purpose": purpose})
    assert r.status_code == 200, r.text


def code_of(
    sent: list[tuple[str, str, str]], phone: str, purpose: str = "recovery"
) -> str:
    for p, c, pu in reversed(sent):
        if p == phone and pu == purpose:
            return c
    raise AssertionError(f"no code captured for {phone}/{purpose}")


def redeem(
    client: TestClient,
    phone: str,
    code: str,
    purpose: str,
    device: str,
    card: dict | None = None,
) -> dict:
    r = client.post(
        "/api/auth/redeem",
        json={
            "phone": phone,
            "code": code,
            "purpose": purpose,
            "device_marker": device,
            "card": card,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def me(client: TestClient, token: str | None) -> dict | None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["account"]


def auth(token: str | None) -> dict:
    """Bearer 头构造（None=游客不带）——曾七处测试文件各抄一份，收编到此。"""
    return {"Authorization": f"Bearer {token}"} if token else {}


def _pwd_post(
    client: TestClient, path: str, body: dict, token: str | None = None
) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = client.post(f"/api/auth/password/{path}", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def password_set(
    client: TestClient, token: str, code: str = "", password: str = "123456"
) -> dict:
    return _pwd_post(client, "set", {"code": code, "password": password}, token)


def password_login(client: TestClient, phone: str, password: str, device: str) -> dict:
    return _pwd_post(
        client, "login", {"phone": phone, "password": password, "device_marker": device}
    )


def password_reset(
    client: TestClient, phone: str, code: str, password: str, device: str
) -> dict:
    return _pwd_post(
        client,
        "reset",
        {"phone": phone, "code": code, "password": password, "device_marker": device},
    )


def password_change(client: TestClient, token: str, old: str, new: str) -> dict:
    return _pwd_post(client, "change", {"old": old, "new": new}, token)


def password_redeem(
    client: TestClient, phone: str, password: str, device: str, card: dict | None = None
) -> dict:
    return _pwd_post(
        client,
        "redeem",
        {"phone": phone, "password": password, "device_marker": device, "card": card},
    )
