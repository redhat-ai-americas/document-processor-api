# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
make install       # install all dependencies (prod + dev)
make run           # start the service on http://localhost:8080 (PORT env var to override)
make test          # run unit tests
make lint          # run ruff linter
make build         # build container image with podman
make clean         # remove __pycache__, .pytest_cache, .ruff_cache, target/
```

Run a single test:
```bash
PYTHONPATH=src pytest tests/src/test_convert.py::test_missing_filename_returns_422 -v
```

Run integration tests against a live service (requires `make run` in another terminal):
```bash
pytest tests/src/test_integration_samples.py -v
SERVICE_URL=http://localhost:9000 pytest tests/src/test_integration_samples.py -v
```

`uv` is used automatically over `pip` when available.

## Architecture

The service is a FastAPI app that wraps [Docling](https://github.com/DS4SD/docling) to convert documents to Markdown. The entry point is `src/app/main.py`, which must configure logging before importing FastAPI (see the ordering comment there).

**Request flow:**

1. `POST /convert/` or `/convert/text` (alias) — both handled in `src/app/routers/convert.py`
2. The raw binary body is streamed to a named temp file with size-limit enforcement
3. `src/app/services/converter.py` calls Docling's `DocumentConverter` in a thread-pool executor (to avoid blocking the event loop)
4. The result is exported to Markdown with `ImageRefMode.EMBEDDED` (images base64-encoded inline) and split on page-break sentinels
5. A `StreamingResponse` yields one chunk per page; the temp file is cleaned up in a `finally` block

**Converter caching:** `DocumentConverter` is expensive to initialise (loads ML models). It is cached with `@lru_cache(maxsize=8)` keyed on `page_batch_size` in `converter.py`. Default batch size is 10.

**Import location for `ImageRefMode`:** it lives in `docling_core.types.doc.base`, not `docling.datamodel.base_models` (moved in the installed version).

**Configuration** is managed by pydantic-settings in `src/app/config.py`. All settings are read from environment variables or a `.env` file. Key vars: `DEVICE` (cpu/cuda/mps), `OCR_ENGINE` (rapidocr/easyocr/tesseract), `MAX_FILE_SIZE_MB`, `LOG_LEVEL`.

**Tests:** unit tests in `tests/src/` use FastAPI's `TestClient` and mock `converter.stream_to_markdown` — they do not require Docling to be installed or a running service. Integration tests in `test_integration_samples.py` hit a real running service and save output to `target/<name>.md` before asserting.

**Deployment:** Helm chart at `deploy/helm/`. Targets Kubernetes/OpenShift. Resources default to 10 CPU / 12Gi memory (requests == limits). GPU support toggled via `gpu.enabled=true`. ArgoCD manifest at `deploy/argocd-app.yaml`.
