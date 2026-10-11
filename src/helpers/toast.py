import json
from typing import Any
from flask import Flask, Response, request, session
from src.config import Settings, setup_logger

logger = setup_logger(Settings.LOG_DIR / "helpers.log", name="bew.helpers.toast")


def _pop_flashes() -> list[dict[str, str]]:
    flashes: list[tuple[str, str]] | None = session.pop("_flashes", None)
    if not flashes:
        return []
    return [{"message": msg, "type": cat} for cat, msg in flashes]


def _merge_trigger_header(response: Response, toasts: list[dict[str, str]]) -> Response:
    existing: str | None = response.headers.get("HX-Trigger")
    payload: dict[str, Any]
    if existing:
        try:
            parsed: Any = json.loads(existing)
            if isinstance(parsed, dict):
                payload = parsed
                current: Any = payload.get("bewToast", [])
                normalized: list[Any] = current if isinstance(current, list) else [current]
                payload["bewToast"] = normalized + toasts
            else:
                payload = {"_existing": parsed, "bewToast": toasts}
        except (ValueError, TypeError):
            payload = {"_existing": existing, "bewToast": toasts}
    else:
        payload = {"bewToast": toasts}
    response.headers["HX-Trigger"] = json.dumps(payload, ensure_ascii=False)
    return response


def toast_response(response: Response, message: str, type: str = "info") -> Response:
    return _merge_trigger_header(response, [{"message": message, "type": type}])


def register_toast_bridge(app: Flask) -> Flask:
    @app.after_request
    def _toast_bridge(response: Response) -> Response:
        try:
            if not request.headers.get("HX-Request"):
                return response
            if response.headers.get("HX-Redirect") or response.headers.get("HX-Refresh"):
                return response
            toasts = _pop_flashes()
            if toasts:
                _merge_trigger_header(response, toasts)
        except Exception:
            logger.exception("toast bridge failed")
        return response

    return app
