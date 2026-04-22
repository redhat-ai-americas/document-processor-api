import os
import signal

from app.logging_config import configure_logging
from app.routers import convert_to_json, convert_to_md, health

configure_logging()

import logging  # noqa: E402

_log = logging.getLogger(__name__)


def _handle_termination(signum, frame):
    _log.info("Received signal %s, terminating immediately", signum)
    os._exit(0)


for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
    signal.signal(_sig, _handle_termination)

from pathlib import Path  # noqa: E402

from fastapi import FastAPI  # noqa: E402 — must come after logging is configured
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Convert PDFs and other document types to Markdown or JSON.",
)

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

app.include_router(health.router)
app.include_router(convert_to_md.router)
app.include_router(convert_to_json.router)


@app.get("/", include_in_schema=False)
async def ui() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(__import__("os").getenv("PORT", "8080")), reload=True)
