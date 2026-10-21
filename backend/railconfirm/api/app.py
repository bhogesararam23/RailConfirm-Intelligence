"""FastAPI application factory for RailConfirm Intelligence.

Creates and configures the FastAPI application instance.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from railconfirm.api.v1.router import router as v1_router
from railconfirm.api.v1.schemas import ErrorDetail, ErrorResponse
from railconfirm.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Local-first Indian Railways ticket confirmation probability estimation. "
            "Returns structured abstentions when no trained model is available. "
            "Never returns fabricated probabilities."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Register routers ───────────────────────────────────────────────────────
    app.include_router(v1_router)

    # ── Exception handlers ─────────────────────────────────────────────────────
    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                code="VALIDATION_ERROR",
                message=str(err["msg"]),
                field=".".join(str(loc) for loc in err["loc"]),
            )
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="Request validation failed.",
                details=details,
            ).model_dump(mode="json"),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=str(exc),
                details=[ErrorDetail(code="INVALID_INPUT", message=str(exc))],
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="An internal server error occurred.",
                details=[ErrorDetail(code="INTERNAL_ERROR", message=str(exc))],
            ).model_dump(mode="json"),
        )

    return app


# Application instance for use with uvicorn.
app = create_app()
