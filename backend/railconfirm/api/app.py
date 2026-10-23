"""FastAPI application factory for RailConfirm Intelligence.

Creates and configures the FastAPI application instance: CORS for the local
frontend, a documented error envelope, request identification, payload bounds,
and privacy-aware access logging.

This is a local-first development server. It is not authenticated and must not be
treated as a public production security boundary; see docs/SECURITY_AND_PRIVACY.md.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from railconfirm.api.problems import ApiProblem
from railconfirm.api.v1.router import router as v1_router
from railconfirm.api.v1.schemas import ErrorDetail, ErrorResponse
from railconfirm.config import settings
from railconfirm.domain.exceptions import (
    JourneyValidationError,
    RailConfirmError,
    TemporalIntegrityError,
)
from railconfirm.domain.validation import ReasonCode
from railconfirm.inference.engine import InferenceEngine
from railconfirm.storage.predictions import PredictionStorageError, PredictionStore

ACCESS_LOG = logging.getLogger("railconfirm.access")

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging() -> None:
    """Set the root level from configuration. Idempotent."""
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    logging.getLogger().setLevel(getattr(logging, settings.log_level, logging.INFO))


def _error_payload(
    error: str,
    details: list[ErrorDetail],
    request: Request | None,
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None) if request else None
    return ErrorResponse(
        error=error,
        details=details,
        request_id=request_id,
    ).model_dump(mode="json")


class RequestIdentityMiddleware(BaseHTTPMiddleware):
    """Attach an identifier to each request so a log line and an error response
    can be correlated without logging any request content."""

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request.state.request_id = (
            incoming[:64] if incoming and incoming.isascii() and incoming.isprintable()
            else uuid.uuid4().hex
        )
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response


class RequestAccessLogMiddleware(BaseHTTPMiddleware):
    """Log one safe JSON line per request.

    Never includes request bodies, query strings, passenger statuses or model
    inputs: a status string is booking information.
    """

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            ACCESS_LOG.exception(
                json.dumps(
                    {
                        "event": "request",
                        "request_id": getattr(request.state, "request_id", None),
                        "method": request.method,
                        "path": request.url.path,
                        "status": 500,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                    sort_keys=True,
                )
            )
            raise
        ACCESS_LOG.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": getattr(request.state, "request_id", None),
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
                sort_keys=True,
            )
        )
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject an obviously oversized request before it is read or parsed."""

    def __init__(self, app: Any, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("content-length")
        if header is not None:
            try:
                declared = int(header)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=_error_payload(
                        "Malformed Content-Length header.",
                        [ErrorDetail(code=ReasonCode.INVALID_INPUT, message="Content-Length must be an integer.")],
                        request,
                    ),
                )
            if declared > self.max_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content=_error_payload(
                        f"Request body exceeds the {self.max_bytes} byte limit.",
                        [
                            ErrorDetail(
                                code="REQUEST_TOO_LARGE",
                                message=f"Limited to {self.max_bytes} bytes.",
                            )
                        ],
                        request,
                    ),
                )
        return await call_next(request)


def create_app(
    engine: InferenceEngine | None = None,
    prediction_store: PredictionStore | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    engine:
        Optional inference engine to serve. Injected so tests and later phases
        can supply a registry or baseline without module-level globals.
    prediction_store:
        Optional history store. When it is omitted, one is opened only if
        ``RAILCONFIRM_PERSIST_PREDICTIONS`` is enabled — otherwise the app keeps no
        history at all and says so in the response.
    """
    configure_logging()

    resolved_engine = engine or InferenceEngine()
    store = prediction_store
    if store is None and settings.persist_predictions:
        store = PredictionStore(
            settings.storage_dir / "predictions.sqlite3",
            retention_days=settings.prediction_retention_days,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # A lifespan, not a deprecated shutdown-event list: the store is opened for the
        # life of the application, so its file handle closes with the application.
        yield
        if store is not None:
            store.close()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Local-first Indian Railways ticket confirmation probability estimation. "
            "Returns structured abstentions when no validated model or approved data is "
            "available. Never returns fabricated probabilities."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.engine = resolved_engine
    app.state.prediction_store = store

    # ── Middleware (outermost last) ────────────────────────────────────────────
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(RequestAccessLogMiddleware)
    app.add_middleware(RequestIdentityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", REQUEST_ID_HEADER],
        max_age=600,
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(v1_router)

    # ── Exception handlers ─────────────────────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI raises RequestValidationError for request bodies; without this
        # handler the response would be Starlette's {"detail": [...]} shape and
        # clients could not read the documented error envelope.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_payload(
                "Request validation failed.", _validation_details(exc.errors()), request
            ),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_payload(
                "Request validation failed.", _validation_details(exc.errors()), request
            ),
        )

    @app.exception_handler(TemporalIntegrityError)
    async def temporal_integrity_handler(
        request: Request, exc: TemporalIntegrityError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_payload(
                "The supplied timestamps cannot support a prediction.",
                [ErrorDetail(code=ReasonCode.INVALID_PREDICTION_AT, message=str(exc))],
                request,
            ),
        )

    @app.exception_handler(JourneyValidationError)
    async def journey_validation_handler(
        request: Request, exc: JourneyValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_payload(
                "The journey context is invalid.",
                [ErrorDetail(code=ReasonCode.INVALID_INPUT, message=str(exc))],
                request,
            ),
        )

    @app.exception_handler(ApiProblem)
    async def api_problem_handler(request: Request, exc: ApiProblem) -> JSONResponse:
        # An endpoint-level problem (unknown report id, history not enabled) still
        # arrives in the documented envelope, so a client parses one shape.
        logging.getLogger(__name__).info("api problem: %s %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                exc.message,
                [ErrorDetail(code=exc.code, message=exc.message)],
                request,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # A path nothing routes to, or a method a path refuses. Without this the reply
        # is Starlette's {"detail": …} and the contract's "every error is an envelope"
        # statement is false for the most common mistake a client can make.
        detail = exc.detail if isinstance(exc.detail, str) else "The request failed."
        code = ReasonCode.NOT_FOUND if exc.status_code == 404 else (
            ReasonCode.INTERNAL_ERROR if exc.status_code >= 500 else ReasonCode.INVALID_INPUT
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(detail, [ErrorDetail(code=code, message=detail)], request),
        )

    @app.exception_handler(RailConfirmError)
    async def domain_error_handler(
        request: Request, exc: RailConfirmError
    ) -> JSONResponse:
        logging.getLogger(__name__).warning("Domain error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                "The request could not be processed.",
                [ErrorDetail(code=ReasonCode.INTERNAL_ERROR, message=exc.__class__.__name__)],
                request,
            ),
        )

    @app.exception_handler(PredictionStorageError)
    async def storage_error_handler(
        request: Request, exc: PredictionStorageError
    ) -> JSONResponse:
        # A history row this build cannot trust is a storage problem, not a mystery
        # internal error: the operator needs to see which gate the store refused.
        logging.getLogger(__name__).warning("Prediction storage error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                "Prediction history could not be read.",
                [ErrorDetail(code=ReasonCode.STORAGE_UNAVAILABLE, message=str(exc))],
                request,
            ),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # The exception text stays server-side: it can contain field values from
        # the request body.
        logging.getLogger(__name__).exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                "An internal server error occurred.",
                [
                    ErrorDetail(
                        code=ReasonCode.INTERNAL_ERROR,
                        message="The error was logged with this request id.",
                    )
                ],
                request,
            ),
        )

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "health": "/v1/health",
            "docs": "/docs",
        }

    return app


def _field_path(loc: object) -> str | None:
    """Join a pydantic error location into a dotted path relative to the body.

    Starlette prefixes request-body locations with "body"; clients care about the
    field they sent, so that wrapper is dropped.
    """
    parts = [str(item) for item in loc] if isinstance(loc, (list, tuple)) else [str(loc)]
    parts = [part for part in parts if part]
    if parts and parts[0] in {"body", "query", "path", "header"}:
        parts = parts[1:]
    return ".".join(parts) or None


def _validation_details(errors: Sequence[Mapping[str, Any]]) -> list[ErrorDetail]:
    """Convert pydantic error entries into the documented error envelope.

    Pydantic prefixes a raised ``ValueError`` with "Value error, "; the prefix is
    a Python artefact, not information the client can act on.
    """
    details = []
    for err in errors:
        message = str(err.get("msg", "Invalid value."))
        for prefix in ("Value error, ", "Assertion failed, "):
            message = message.removeprefix(prefix)
        details.append(
            ErrorDetail(
                code=ReasonCode.VALIDATION_ERROR,
                message=message,
                field=_field_path(err.get("loc", ())),
            )
        )
    return details


# Application instance for use with uvicorn.
app = create_app()
