import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import EnvironmentOptions, settings
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

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled error on %s %s: %s\n%s",
            request.method,
            request.url.path,
            exc,
            traceback.format_exc(),
        )
        content = {"message": "Internal Server Error"}
        if settings.ENVIRONMENT != EnvironmentOptions.PRODUCTION:
            content["detail"] = str(exc)
        return JSONResponse(status_code=500, content=content)

    return app
