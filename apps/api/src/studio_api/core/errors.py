from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    FACTUAL_VALIDATION_FAILED = "FACTUAL_VALIDATION_FAILED"
    INSUFFICIENT_MEMORY = "INSUFFICIENT_MEMORY"
    INSUFFICIENT_STORAGE = "INSUFFICIENT_STORAGE"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    ASSET_STALE = "ASSET_STALE"
    POLICY_REJECTED = "POLICY_REJECTED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    INVALID_TRANSITION = "INVALID_TRANSITION"


class StudioError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ConflictError(StudioError):
    def __init__(self, message: str = "The resource changed since it was loaded") -> None:
        super().__init__(ErrorCode.REVISION_CONFLICT, message, status_code=409)


async def studio_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StudioError)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )
