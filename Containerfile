FROM quay.io/redhat-ai-americas/docling-rapidocr-pipeline:1.2

ENV OMP_NUM_THREADS=4 \
    HF_HOME=/tmp/ \
    TORCH_HOME=/tmp/ \
    DEVICE=cpu \
    LOG_LEVEL=INFO \
    GRACEFUL_SHUTDOWN_TIMEOUT=30

WORKDIR /opt/app-root/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

ENV PYTHONPATH=/opt/app-root/src

EXPOSE 8080

ENV GRACEFUL_SHUTDOWN_TIMEOUT=45

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --timeout-graceful-shutdown ${GRACEFUL_SHUTDOWN_TIMEOUT}"]
