# document-processor-api

A FastAPI microservice that converts PDFs and other document types to Markdown or JSON using [Docling](https://github.com/DS4SD/docling). Markdown responses are streamed page-by-page with base64-embedded images, making each response fully self-contained.

The service runs as a **Knative Serverless** workload on **OpenShift Serverless**. It scales to zero when idle and scales out automatically under load.

## Features

- Converts PDF, DOCX, PPTX, XLSX, HTML, PNG, JPEG, and TIFF to Markdown or JSON
- Streams Markdown output with chunked transfer encoding — one chunk per page
- Embeds images as base64 directly in the Markdown output
- RapidOCR for optical character recognition
- CPU and GPU (CUDA) acceleration support
- Scales to zero when idle via Knative Serving on OpenShift Serverless
- Deployed via Helm chart and ArgoCD GitOps

## API

### `GET /health`

Returns service status and version.

```json
{ "status": "ok", "version": "0.1.0" }
```

---

### `POST /convert_to_md/`

Upload a document as a raw binary body and receive a streaming Markdown response. Images are base64-encoded and embedded inline so the output is fully self-contained.

**Query parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `filename` | Yes | — | Original filename including extension, e.g. `report.pdf` |
| `page_batch_size` | No | `10` | Pages per inference batch (1–128) |

**Request:**

```
Content-Type: application/octet-stream
Body: raw file bytes
```

**Response:**

```
Content-Type: text/plain; charset=utf-8
X-Filename: <original filename>
Transfer-Encoding: chunked
```

Each chunk contains the Markdown for one page.

**Errors:**

| Status | Reason |
|--------|--------|
| 413 | File exceeds the configured size limit (default 50 MB) |
| 415 | Unsupported file extension |
| 422 | Missing or invalid query parameters |

**Supported extensions:** `.pdf` `.docx` `.pptx` `.xlsx` `.html` `.png` `.jpeg` `.tiff`

**Example — curl:**

```bash
curl -X POST "http://localhost:8080/convert_to_md/?filename=report.pdf" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @report.pdf
```

Save the streamed output to a file:

```bash
curl -X POST "http://localhost:8080/convert_to_md/?filename=report.pdf" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @report.pdf \
  -o report.md
```

**Example — Python:**

```python
import requests

with open("report.pdf", "rb") as f:
    resp = requests.post(
        "http://localhost:8080/convert_to_md/",
        params={"filename": "report.pdf"},
        data=f,
        headers={"Content-Type": "application/octet-stream"},
        stream=True,
    )
    for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
        print(chunk, end="")
```

---

### `POST /convert_to_json/`

Upload a document as a raw binary body and receive the full Docling document representation as JSON. Unlike `convert_to_md`, this endpoint returns a single JSON response (not a stream).

**Query parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `filename` | Yes | — | Original filename including extension, e.g. `report.pdf` |
| `page_batch_size` | No | `10` | Pages per inference batch (1–128) |

**Request:**

```
Content-Type: application/octet-stream
Body: raw file bytes
```

**Response:**

```
Content-Type: application/json
X-Filename: <original filename>
```

The response body is the full Docling JSON document object.

**Errors:**

| Status | Reason |
|--------|--------|
| 413 | File exceeds the configured size limit (default 50 MB) |
| 415 | Unsupported file extension |
| 422 | Missing or invalid query parameters |

**Supported extensions:** `.pdf` `.docx` `.pptx` `.xlsx` `.html` `.png` `.jpeg` `.tiff`

**Example — curl:**

```bash
curl -X POST "http://localhost:8080/convert_to_json/?filename=report.pdf" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @report.pdf
```

Save the JSON output to a file:

```bash
curl -X POST "http://localhost:8080/convert_to_json/?filename=report.pdf" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @report.pdf \
  -o report.json
```

Pretty-print with `jq`:

```bash
curl -X POST "http://localhost:8080/convert_to_json/?filename=report.pdf" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @report.pdf \
  | jq .
```

**Example — Python:**

```python
import requests

with open("report.pdf", "rb") as f:
    resp = requests.post(
        "http://localhost:8080/convert_to_json/",
        params={"filename": "report.pdf"},
        data=f,
        headers={"Content-Type": "application/octet-stream"},
    )
    resp.raise_for_status()
    doc = resp.json()
    print(doc)
```

## Running locally

**Prerequisites:** Python 3.11+, `uv` or `pip`

```bash
make install   # install dependencies
make run       # start the service on http://localhost:8080
```

Override the port:

```bash
PORT=9000 make run
```

Run the unit test suite:

```bash
make test
```

Run integration tests against a live service (requires `make run` in another terminal):

```bash
pytest tests/src/test_integration_samples.py -v
# Custom URL:
SERVICE_URL=http://localhost:9000 pytest tests/src/test_integration_samples.py -v
```

## Configuration

All settings are read from environment variables (or a `.env` file in the working directory).

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE` | `cpu` | Compute device: `cpu`, `cuda`, `mps` |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit in megabytes |
| `LOG_LEVEL` | `INFO` | Python log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DOCLING_ARTIFACTS_PATH` | `/opt/app-root/src/.cache/docling/models` | Path to cached Docling ML models |
| `DEBUG` | `false` | Enable FastAPI debug mode |
| `GRACEFUL_SHUTDOWN_TIMEOUT` | `60` | Seconds uvicorn waits for in-flight requests to complete after receiving SIGTERM before forcibly closing connections |

## Building the container image

```bash
make build   # builds quay.io/<USER>/document-processor-api:latest
make push    # pushes to the registry
```

Override image coordinates:

```bash
make build REGISTRY=registry.example.com IMAGE_NAME=doc-api IMAGE_TAG=v1.2.3
make push  REGISTRY=registry.example.com IMAGE_NAME=doc-api IMAGE_TAG=v1.2.3
```

The `Containerfile` uses `quay.io/bball/docling-rapidocr-pipeline:1.0` as the base image, which includes Docling and all ML model dependencies pre-installed.

## Deploying to OpenShift

The service is deployed as a Knative Service via the Helm chart at `deploy/helm/` and managed by ArgoCD. It targets OpenShift Serverless (Red Hat's distribution of Knative Serving).

### Prerequisites

- OpenShift Serverless operator installed and a `KnativeServing` instance running in the `knative-serving` namespace
- GPU nodes available with the NVIDIA GPU operator installed (if using GPU)
- ArgoCD installed (for GitOps deployment)

### OpenShift Serverless operator configuration

The following settings must be applied to the `KnativeServing` custom resource by a cluster administrator. **Do not patch the underlying ConfigMaps directly** — the operator owns them and will overwrite any manual changes.

Edit the `KnativeServing` CR:

```bash
kubectl edit knativeserving knative-serving -n knative-serving
```

#### Enabling nodeSelector support

By default, Knative Serving's admission webhook rejects `nodeSelector` fields in Knative Service specs. This must be explicitly enabled:

```yaml
spec:
  config:
    features:
      kubernetes.podspec-nodeselector: "enabled"
```

This propagates the setting into the managed `config-features` ConfigMap so the webhook allows `nodeSelector` in Knative Service specs.

#### Raising the maximum request timeout

Knative Serving's default maximum per-revision timeout is 600 seconds. This service uses a 900-second timeout to accommodate large document conversions. A cluster administrator must raise the cap first:

```yaml
spec:
  config:
    defaults:
      max-revision-timeout-seconds: "900"
```

Without this change, Knative will reject revisions that specify `timeoutSeconds` above 600. Once applied, the Helm chart value `knative.timeoutSeconds` can be set up to 900.

Both settings can be combined in a single edit:

```yaml
spec:
  config:
    features:
      kubernetes.podspec-nodeselector: "enabled"
    defaults:
      max-revision-timeout-seconds: "900"
```

### Helm chart values

| Value | Default | Description |
|-------|---------|-------------|
| `image.repository` | `quay.io/redhat-ai-americas/document-processor-api` | Image repository |
| `image.tag` | `1.0` | Image tag |
| `config.device` | `cuda` | Compute device (`cpu`, `cuda`) |
| `config.maxFileSizeMb` | `100` | Upload size limit |
| `config.gracefulShutdownTimeout` | `30` | Seconds uvicorn waits for in-flight requests after SIGTERM before forcibly closing connections |
| `knative.timeoutSeconds` | `900` | Per-request timeout (requires operator `max-revision-timeout-seconds` ≥ this value) |
| `knative.maxScale` | `4` | Maximum number of replicas |
| `knative.scaleDownDelay` | `300s` | Idle time before scale-to-zero |
| `knative.targetConcurrency` | `10` | Concurrent requests per replica before scale-out |
| `gpu.enabled` | `true` | Request GPU resources and add GPU node selector |
| `gpu.nodeSelector` | `nvidia.com/gpu.present: "true"` | Node selector applied when GPU is enabled |

### ArgoCD GitOps

An ArgoCD Application manifest is available at `deploy/argocd-app.yaml`. Apply it to your ArgoCD namespace to enable GitOps-managed deployments:

```bash
kubectl apply -f deploy/argocd-app.yaml
```

## Project structure

```
├── src/app/
│   ├── main.py            # FastAPI app + entry point
│   ├── config.py          # Settings and enums
│   ├── routers/
│   │   ├── health.py          # GET /health
│   │   ├── convert_to_md.py   # POST /convert_to_md/
│   │   └── convert_to_json.py # POST /convert_to_json/
│   └── services/
│       └── converter.py   # Docling wrapper, streaming generator
├── tests/src/
│   ├── test_health.py
│   ├── test_convert.py
│   └── test_integration_samples.py
├── samples/               # Sample documents for integration tests
├── deploy/helm/           # Helm chart
├── Containerfile
└── Makefile
```
