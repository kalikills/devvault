from __future__ import annotations

from io import BytesIO
from urllib.error import HTTPError

from devvault import validation_client as vc


def test_validate_now_maps_http_500_to_internal_error(monkeypatch) -> None:
    monkeypatch.setattr(
        vc,
        "build_validation_payload",
        lambda app_version=vc.APP_VERSION: {
            "license_id": "lic-1",
            "product": "devvault",
            "plan": "pro",
            "seats": 1,
            "app_version": app_version,
        },
    )

    def fake_urlopen(req, timeout=15):
        raise HTTPError(
            req.full_url,
            500,
            "Internal Server Error",
            hdrs=None,
            fp=BytesIO(b"server exploded"),
        )

    monkeypatch.setattr(vc.urllib.request, "urlopen", fake_urlopen)

    result = vc.validate_now()

    assert result.ok is False
    assert result.result == "validation_service_internal_error"
    assert "internal error" in result.message.lower()
    assert "HTTP 500" not in result.message


def test_validate_now_honors_known_result_from_http_error_body(monkeypatch) -> None:
    monkeypatch.setattr(
        vc,
        "build_validation_payload",
        lambda app_version=vc.APP_VERSION: {
            "license_id": "lic-1",
            "product": "devvault",
            "plan": "pro",
            "seats": 1,
            "app_version": app_version,
        },
    )

    saved: dict[str, object] = {}

    def fake_save_state(**kwargs):
        saved.update(kwargs)
        return kwargs

    def fake_urlopen(req, timeout=15):
        body = b'{"result":"revoked","license_status":"revoked"}'
        raise HTTPError(
            req.full_url,
            403,
            "Forbidden",
            hdrs=None,
            fp=BytesIO(body),
        )

    monkeypatch.setattr(vc, "save_state", fake_save_state)
    monkeypatch.setattr(vc.urllib.request, "urlopen", fake_urlopen)

    result = vc.validate_now()

    assert result.ok is False
    assert result.result == "revoked"
    assert result.message == "License validation returned: revoked"
    assert saved["last_result"] == "revoked"
