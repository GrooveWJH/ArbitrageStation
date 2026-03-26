from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _error_message_from_detail(detail, fallback: str) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, dict):
        msg = detail.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg
    return fallback


def _error_payload(*, request: Request, status_code: int, detail, fallback_message: str) -> dict:
    request_id = request.headers.get("X-Request-Id") or request.headers.get("Idempotency-Key")
    return {
        "detail": detail,
        "error": {
            "code": f"HTTP_{status_code}",
            "message": _error_message_from_detail(detail, fallback_message),
            "quality_reason": None,
            "request_id": request_id,
        },
    }


def register_exception_handlers(app, logger) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                request=request,
                status_code=exc.status_code,
                detail=exc.detail,
                fallback_message="Request failed",
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                request=request,
                status_code=422,
                detail=exc.errors(),
                fallback_message="Validation error",
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                request=request,
                status_code=500,
                detail="Internal server error",
                fallback_message="Internal server error",
            ),
        )
