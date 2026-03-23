from __future__ import annotations

from typing import List, Optional

from fastapi.responses import JSONResponse

from mini_exchange_service.schemas import ApiErrorResponse, ErrorBody, ErrorDetail


def json_error(
    status_code: int,
    *,
    code: str,
    message: str,
    details: Optional[List[ErrorDetail]] = None,
) -> JSONResponse:
    body = ApiErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or [],
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
    )
