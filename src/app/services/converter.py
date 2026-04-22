import asyncio
import logging
from collections.abc import AsyncGenerator
from functools import lru_cache
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling_core.types.doc.base import ImageRefMode
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

from app.config import Device, settings

log = logging.getLogger(__name__)

DEFAULT_PAGE_BATCH_SIZE = 10

# Sentinel used to locate page boundaries inside exported markdown.
_PAGE_BREAK = "\x00DOCLING_PAGE\x00"

SUPPORTED_MIME_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/html": ".html",
    "image/png": ".png",
    "image/jpeg": ".jpeg",
    "image/tiff": ".tiff",
}

SUPPORTED_EXTENSIONS: set[str] = set(SUPPORTED_MIME_TYPES.values())

_ACCELERATOR_DEVICE_MAP: dict[Device, AcceleratorDevice] = {
    Device.cpu: AcceleratorDevice.CPU,
    Device.cuda: AcceleratorDevice.CUDA,
    Device.mps: AcceleratorDevice.MPS,
}


@lru_cache(maxsize=8)
def _get_converter(page_batch_size: int) -> DocumentConverter:
    """Initialise (and cache) a DocumentConverter for the given *page_batch_size*.

    Keying the cache on batch size means we load models once per unique value
    (in practice almost always the default) while still honouring per-request
    overrides without reloading models on every call.
    """
    accelerator = AcceleratorOptions(device=_ACCELERATOR_DEVICE_MAP[settings.device])
    ocr_options = RapidOcrOptions()

    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        ocr_options=ocr_options,
        accelerator_options=accelerator,
        page_batch_size=page_batch_size,
        # Required for ImageRefMode.EMBEDDED — docling must render picture regions
        # so they can be base64-encoded into the markdown output.
        generate_picture_images=True,
        images_scale=2.0,
    )

    log.info(
        "Initialising DocumentConverter — device=%s page_batch_size=%d",
        settings.device.value,
        page_batch_size,
    )

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def is_supported(filename: str) -> bool:
    """Return True if the file extension is in the supported set."""
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def _page_count(document) -> int | None:
    try:
        pages = document.pages
        return len(pages) if pages else None
    except AttributeError:
        return None


def _run_conversion(doc_converter: DocumentConverter, file_path: Path):
    """Blocking docling call — always run inside run_in_executor."""
    return doc_converter.convert(str(file_path))


async def convert_to_json(
    file_path: Path,
    filename: str,
    page_batch_size: int = DEFAULT_PAGE_BATCH_SIZE,
) -> dict[str, Any]:
    """Convert a document and return the Docling JSON representation as a dict.

    The blocking docling conversion runs in a thread-pool executor so the
    event loop is never stalled.
    """
    log.info("Converting to JSON for '%s' (batch_size=%d)", filename, page_batch_size)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _run_conversion, _get_converter(page_batch_size), file_path
    )

    page_count = _page_count(result.document)
    log.info("Conversion done for '%s' — %s page(s)", filename, page_count)

    return result.document.export_to_dict()


async def stream_to_markdown(
    file_path: Path,
    filename: str,
    page_batch_size: int = DEFAULT_PAGE_BATCH_SIZE,
) -> AsyncGenerator[str, None]:
    """Async generator that yields converted Markdown one page at a time.

    Images are base64-encoded and embedded directly in the Markdown output
    (``ImageRefMode.EMBEDDED``) so no auxiliary files are produced.

    The blocking docling conversion runs in a thread-pool executor so the
    event loop is never stalled.  Once conversion is complete the exported
    Markdown is split on page-break sentinels and each page's content is
    yielded individually, allowing the HTTP layer to flush chunks to the
    client as soon as they are available.

    Yields:
        One string per page containing that page's Markdown content,
        followed by a trailing blank line.
    """
    log.info("Streaming markdown for '%s' (batch_size=%d)", filename, page_batch_size)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _run_conversion, _get_converter(page_batch_size), file_path
    )

    page_count = _page_count(result.document)
    log.info("Conversion done for '%s' — %s page(s), streaming now", filename, page_count)

    full_markdown = result.document.export_to_markdown(
        image_mode=ImageRefMode.EMBEDDED,
        page_break_placeholder=_PAGE_BREAK,
    )

    for segment in full_markdown.split(_PAGE_BREAK):
        content = segment.strip()
        if content:
            yield content + "\n\n"
            # Yield control back so the event loop can flush the chunk.
            await asyncio.sleep(0)
