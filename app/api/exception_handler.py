import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import EnvironmentOptions, settings

logger = logging.getLogger("uvicorn.error")


def register_exception_handlers(app: FastAPI) -> FastAPI:
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
