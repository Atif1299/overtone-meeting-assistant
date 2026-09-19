from __future__ import annotations

import hashlib
import hmac
import json

from app.config import get_settings
from app.db import SessionLocal, create_tables
from app.db.models import Subscription
from app.http.billing import (
    handle_paddle_webhook,
    paddle_environment,
    plan_from_paddle_payload,
    verify_paddle_signature,
)
from app.http.paddle_ips import ip_in_cidrs, source_ip_from_request

STARTER_PRICE = "pri_01m2v77c4sfdjmp2xk4wbp7apb"
PRO_PRICE = "pri_01m2v74zwdp5egjscr89dk906c"
SECRET = "pdl_test_webhook_secret"


def _sign(raw_body: str, secret: str = SECRET, ts: str = "1717000000") -> str:
    digest = hmac.new(secret.encode("utf-8"), f"{ts}:{raw_body}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts};h1={digest}"


def test_verify_paddle_signature_accepts_valid_hmac():
    body = '{"event_type":"transaction.completed"}'
    assert verify_paddle_signature(body.encode("utf-8"), _sign(body), SECRET) is True


def test_verify_paddle_signature_rejects_tampered_body():
    body = '{"event_type":"transaction.completed"}'
    header = _sign(body)
    assert verify_paddle_signature(b'{"event_type":"transaction.failed"}', header, SECRET) is False


def test_verify_paddle_signature_rejects_missing_header():
    assert verify_paddle_signature(b"{}", "", SECRET) is False
    assert verify_paddle_signature(b"{}", "nope", SECRET) is False


def test_plan_from_custom_data():
    assert (
        plan_from_paddle_payload(
            {"custom_data": {"plan": "starter"}, "items": []},
            starter_price=STARTER_PRICE,
            pro_price=PRO_PRICE,
        )
        == "starter"
    )
    assert (
        plan_from_paddle_payload(
            {"custom_data": {"plan": "pro"}},
            starter_price=STARTER_PRICE,
            pro_price=PRO_PRICE,
        )
        == "pro"
    )


def test_plan_prefers_price_id_over_conflicting_custom_data():
    assert (
        plan_from_paddle_payload(
            {
                "custom_data": {"plan": "starter"},
                "items": [{"price": {"id": PRO_PRICE}}],
            },
            starter_price=STARTER_PRICE,
            pro_price=PRO_PRICE,
        )
        == "pro"
    )


def test_plan_from_price_id_when_custom_data_missing():
    starter = plan_from_paddle_payload(
        {"items": [{"price": {"id": STARTER_PRICE}}]},
        starter_price=STARTER_PRICE,
        pro_price=PRO_PRICE,
    )
    pro = plan_from_paddle_payload(
        {"items": [{"price_id": PRO_PRICE, "quantity": 1}]},
        starter_price=STARTER_PRICE,
        pro_price=PRO_PRICE,
    )
    unknown = plan_from_paddle_payload(
        {"items": [{"price": {"id": "pri_other"}}]},
        starter_price=STARTER_PRICE,
        pro_price=PRO_PRICE,
    )
    assert starter == "starter"
    assert pro == "pro"
    assert unknown == "free"


def test_transaction_completed_sets_starter_plan():
    create_tables()
    db = SessionLocal()
    workspace_id = "ws_paddle_starter"
    try:
        db.query(Subscription).filter(Subscription.workspace_id == workspace_id).delete()
        db.commit()
        get_settings.cache_clear()
        handle_paddle_webhook(
            db,
            {
                "event_type": "transaction.completed",
                "data": {
                    "id": "txn_test_1",
                    "customer_id": "ctm_test_1",
                    "subscription_id": "sub_test_1",
                    "custom_data": {"workspace_id": workspace_id, "plan": "starter"},
                    "items": [{"price": {"id": STARTER_PRICE}}],
                },
            },
        )
        sub = db.query(Subscription).filter(Subscription.workspace_id == workspace_id).one()
        assert sub.plan == "starter"
        assert sub.status == "active"
        assert sub.paddle_customer_id == "ctm_test_1"
        assert sub.paddle_subscription_id == "sub_test_1"
    finally:
        db.query(Subscription).filter(Subscription.workspace_id == workspace_id).delete()
        db.commit()
        db.close()


def test_subscription_canceled_reverts_to_free():
    create_tables()
    db = SessionLocal()
    workspace_id = "ws_paddle_cancel"
    try:
        db.query(Subscription).filter(Subscription.workspace_id == workspace_id).delete()
        db.commit()
        db.add(
            Subscription(
                workspace_id=workspace_id,
                plan="pro",
                status="active",
                paddle_customer_id="ctm_test_2",
                paddle_subscription_id="sub_test_2",
            )
        )
        db.commit()
        handle_paddle_webhook(
            db,
            {
                "event_type": "subscription.canceled",
                "data": {
                    "id": "sub_test_2",
                    "status": "canceled",
                    "customer_id": "ctm_test_2",
                    "custom_data": {"workspace_id": workspace_id, "plan": "pro"},
                },
            },
        )
        sub = db.query(Subscription).filter(Subscription.workspace_id == workspace_id).one()
        assert sub.plan == "free"
        assert sub.status == "canceled"
        assert sub.paddle_subscription_id is None
        assert sub.paddle_customer_id == "ctm_test_2"
    finally:
        db.query(Subscription).filter(Subscription.workspace_id == workspace_id).delete()
        db.commit()
        db.close()


def test_paddle_environment_from_api_base():
    assert paddle_environment("https://sandbox-api.paddle.com") == "sandbox"
    assert paddle_environment("https://api.paddle.com") == "live"


def test_paddle_source_ip_allowlist_helpers():
    assert source_ip_from_request(None) is None
    assert source_ip_from_request("34.237.3.244, 10.0.0.1") == "34.237.3.244"
    cidrs = ["34.237.3.244/32", "10.0.0.0/8"]
    assert ip_in_cidrs("34.237.3.244", cidrs) is True
    assert ip_in_cidrs("203.0.113.10", cidrs) is False


def test_paddle_webhook_route_rejects_bad_signature(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            body = json.dumps({"event_type": "transaction.completed", "data": {}})
            r = client.post(
                "/webhooks/paddle",
                content=body,
                headers={"Content-Type": "application/json", "Paddle-Signature": "ts=1;h1=deadbeef"},
            )
            assert r.status_code == 400
            ok = client.post(
                "/webhooks/paddle",
                content=body,
                headers={"Content-Type": "application/json", "Paddle-Signature": _sign(body)},
            )
            assert ok.status_code == 200
            assert ok.json()["ok"] is True

            monkeypatch.setattr(
                "app.http.me.fetch_paddle_ipv4_cidrs",
                lambda: ["34.237.3.244/32"],
            )
            blocked = client.post(
                "/webhooks/paddle",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "Paddle-Signature": _sign(body),
                    "X-Forwarded-For": "203.0.113.10",
                },
            )
            assert blocked.status_code == 403
            allowed = client.post(
                "/webhooks/paddle",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "Paddle-Signature": _sign(body),
                    "X-Forwarded-For": "34.237.3.244",
                },
            )
            assert allowed.status_code == 200
    finally:
        get_settings.cache_clear()
