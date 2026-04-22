IMAGE_NAME   	?= document-processor-api
IMAGE_TAG    	?= 1.0
REGISTRY     	?= quay.io/redhat-ai-americas
FULL_IMAGE   	:= $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
PORT         	?= 8080
PYTHONPATH   	:= $(CURDIR)/src
DEPLOYMENT_URL 	:= https://document-processor-api-docling.apps.<CLUSTER_URL>

HAS_UV := $(shell command -v uv >/dev/null 2>&1; if [ $$? -eq 0 ]; then echo "true"; else echo "false"; fi)
ifeq ($(HAS_UV), true)
    PIP = uv pip
else
    PIP = pip
endif

.PHONY: help install install-dev run test lint build push clean

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install      Install production dependencies"
	@echo "  install-dev  Install dev + test dependencies"
	@echo "  run          Run the service locally via python"
	@echo "  test         Run unit tests"
	@echo "  lint         Run ruff linter"
	@echo "  build        Build the container image"
	@echo "  push         Push the container image to REGISTRY"
	@echo "  clean        Remove __pycache__ and .pytest_cache"

install:
	$(PIP) install --no-cache-dir -r requirements.txt
	$(PIP) install --no-cache-dir -r requirements-dev.txt

run:
	PYTHONPATH=$(PYTHONPATH) PORT=$(PORT) python src/app/main.py

test:
	PYTHONPATH=$(PYTHONPATH) pytest tests/ -v

test-deployment:
	SERVICE_URL=$(DEPLOYMENT_URL) PYTHONPATH=$(PYTHONPATH) pytest tests/ -v

lint:
	PYTHONPATH=$(PYTHONPATH) ruff check src/ tests/

build:
	podman build -f Containerfile -t $(FULL_IMAGE) .

push:
	podman push $(FULL_IMAGE)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache  -exec rm -rf {} + 2>/dev/null || true
	rm -rf target/
