"""API-facing errors and mapping from storage/domain exceptions (Stage 5.2)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pipeline.adjudication.errors import (
    AdjudicationIntegrityError,
    FamilyNotFoundError,
    InvalidDecisionForTargetError,
    ReviewerNotFoundError,
)


class ErrorCode(str, Enum):
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_REVIEWER = "unknown_reviewer"
    UNKNOWN_FAMILY = "unknown_family"
    UNKNOWN_CORPUS_TARGET = "unknown_corpus_target"
    CORPUS_INDEX_UNAVAILABLE = "corpus_index_unavailable"
    INVALID_DECISION = "invalid_decision"
    INVALID_TARGET_DECISION_PAIR = "invalid_target_decision_pair"
    BAD_REQUEST = "bad_request"


class ApiErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] | None = Field(default=None)


class AdjudicationApiError(Exception):
    """Raised by adjudication services; mapped to HTTP by exception handler."""

    def __init__(
        self,
        *,
        error_code: ErrorCode | str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code.value if isinstance(error_code, ErrorCode) else error_code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def map_integrity_error(exc: AdjudicationIntegrityError) -> AdjudicationApiError:
    if isinstance(exc, ReviewerNotFoundError):
        return AdjudicationApiError(
            error_code=ErrorCode.UNKNOWN_REVIEWER,
            message=str(exc),
            status_code=404,
            details={"reviewer_id": exc.reviewer_id},
        )
    if isinstance(exc, FamilyNotFoundError):
        return AdjudicationApiError(
            error_code=ErrorCode.UNKNOWN_FAMILY,
            message=str(exc),
            status_code=404,
            details={"family_id": exc.family_id},
        )
    if isinstance(exc, InvalidDecisionForTargetError):
        return AdjudicationApiError(
            error_code=ErrorCode.INVALID_TARGET_DECISION_PAIR,
            message=str(exc),
            status_code=400,
            details={
                "target_type": exc.target_type.value,
                "decision_type": exc.decision_type.value,
            },
        )
    return AdjudicationApiError(
        error_code=ErrorCode.BAD_REQUEST,
        message=str(exc),
        status_code=400,
    )


async def adjudication_api_error_handler(request: Request, exc: AdjudicationApiError) -> JSONResponse:
    body = ApiErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=exc.status_code, content=body)
