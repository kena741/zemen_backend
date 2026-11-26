import logging
import os
import sys

from app.api import create_app

logger = logging.getLogger("uvicorn.error")

try:
    app = create_app()
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting Zemen Service API on port %s", port)
except (ValueError, TypeError, KeyError, ImportError, AttributeError, OSError) as exc:
    logger.critical("Error starting server: %s", exc, exc_info=True)
    sys.exit(1)
