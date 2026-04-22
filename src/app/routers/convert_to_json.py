import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.services import converter
from app.services.converter import DEFAULT_PAGE_BATCH_SIZE

log = logging.getLogger(__name__)

router = APIRouter(prefix="/convert_to_json", tags=["convert_to_json"])

_MAX_BYTES = settings.max_file_size_mb * 1024 * 1024


def _check_extension(filename: str) -> None:
    if not converter.is_supported(filename):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{Path(filename).suffix}'. "
                f"Supported extensions: {sorted(converter.SUPPORTED_EXTENSIONS)}"
            ),
        )


async def _write_upload_to_tmp(request: Request, suffix: str) -> Path:
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        bytes_written = 0
        async for chunk in request.stream():
            bytes_written += len(chunk)
            if bytes_written > _MAX_BYTES:
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds the {settings.max_file_size_mb} MB limit.",
                )
            tmp.write(chunk)
        tmp.flush()
        return Path(tmp.name)


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Convert an uploaded document and return Docling JSON",
    response_description="application/json — full Docling document JSON",
)
async def convert_document(
    request: Request,
    filename: str = Query(..., description="Original filename including extension (e.g. report.pdf)"),
    page_batch_size: int = Query(
        DEFAULT_PAGE_BATCH_SIZE, ge=1, le=128,
        description="Number of pages per inference batch",
    ),
) -> JSONResponse:
    """Upload a document as a raw binary body and receive the Docling JSON representation.

    The request body must be the raw binary file content
    (``Content-Type: application/octet-stream``).
    """
    log.info("POST /convert_to_json/ filename='%s' batch_size=%d", filename, page_batch_size)
    _check_extension(filename)

    tmp_path = await _write_upload_to_tmp(request, Path(filename).suffix)
    try:
        doc_dict = await converter.convert_to_json(tmp_path, filename, page_batch_size)
    finally:
        tmp_path.unlink(missing_ok=True)
        log.debug("Removed temp file %s", tmp_path)

    return JSONResponse(
        content=doc_dict,
        headers={"X-Filename": filename},
    )
