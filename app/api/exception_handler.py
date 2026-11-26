import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError as SQLAlchemyTimeoutError,
)

from app.domain.exceptions import (
    AuthenticationError,
    DomainException,
    EntityConflictError,
    EntityNotFoundError,
    PaymentProcessingError,
    PermissionDeniedError,
    StateTransitionError,
    ValidationError,
)

logger = logging.getLogger("uvicorn.error")

_INTEGRITY_SQLSTATE_MAP: dict[str, tuple[int, str]] = {
    "23505": (409, "Resource already exists or conflicts with an existing record."),
    "23503": (400, "Referenced resource does not exist."),
    "23502": (422, "Missing required field."),
    "23514": (422, "Value violates a data constraint."),
}


def _get_sqlstate(exc: SQLAlchemyError) -> str | None:
    """Extract PostgreSQL SQLSTATE code from asyncpg/psycopg2 driver exceptions."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def register_exception_handlers(app: FastAPI) -> FastAPI:
    @app.exception_handler(EntityNotFoundError)
    async def not_found_handler(request: Request, exc: EntityNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"message": exc.message, "details": exc.details},
        )

    @app.exception_handler(EntityConflictError)
    async def conflict_handler(request: Request, exc: EntityConflictError):
        return JSONResponse(
            status_code=409,
            content={"message": exc.message, "details": exc.details},
        )

    @app.exception_handler(AuthenticationError)
    async def auth_handler(request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=401,
            content={"message": exc.message, "details": exc.details},
        )

    @app.exception_handler(PermissionDeniedError)
    async def forbidden_handler(request: Request, exc: PermissionDeniedError):
        return JSONResponse(
            status_code=403,
            content={"message": exc.message, "details": exc.details},
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={"message": exc.message, "details": exc.details},
        )

    @app.exception_handler(StateTransitionError)
    async def transition_handler(request: Request, exc: StateTransitionError):
        return JSONResponse(
            status_code=400,
            content={"message": exc.message, "details": exc.details},
        )

    @app.exception_handler(PaymentProcessingError)
    async def payment_handler(request: Request, exc: PaymentProcessingError):
        return JSONResponse(
            status_code=402,
            content={"message": exc.message, "details": exc.details},
        )

    @app.exception_handler(DomainException)
    async def domain_handler(request: Request, exc: DomainException):
        return JSONResponse(
            status_code=400,
            content={"message": exc.message, "details": exc.details},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        errors = []
        for item in exc.errors():
            loc = ".".join(str(part) for part in item.get("loc", ()) if part != "body")
            errors.append(
                {
                    "field": loc or "body",
                    "message": item.get("msg", "Invalid value"),
                }
            )
        if len(errors) == 1:
            message = f"{errors[0]['field']}: {errors[0]['message']}"
        else:
            message = "Request validation failed"
        return JSONResponse(
            status_code=422,
            content={"message": message, "details": {"errors": errors}},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        sqlstate = _get_sqlstate(exc)
        status_code, message = _INTEGRITY_SQLSTATE_MAP.get(
            sqlstate or "",
            (409, "Database integrity constraint violated."),
        )
        logger.warning(
            "Database integrity error (sqlstate=%s) on %s %s: %s",
            sqlstate,
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status_code,
            content={"message": message, "details": {}},
        )

    @app.exception_handler(DataError)
    async def data_error_handler(request: Request, exc: DataError):
        logger.warning(
            "Database data error on %s %s: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=400,
            content={"message": "Invalid data format.", "details": {}},
        )

    @app.exception_handler(OperationalError)
    @app.exception_handler(SQLAlchemyTimeoutError)
    async def db_unavailable_handler(request: Request, exc: SQLAlchemyError):
        logger.error(
            "Database unavailable on %s %s: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=503,
            content={"message": "Database service temporarily unavailable.", "details": {}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
        logger.error(
            "Unhandled database error on %s %s: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"message": "An unexpected database error occurred.", "details": {}},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled error on %s %s: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"message": "Internal Server Error", "details": {}},
        )

    return app
