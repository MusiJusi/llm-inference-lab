ARG VLLM_IMAGE=vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089
FROM ${VLLM_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    HOME=/tmp/home HF_HOME=/tmp/huggingface XDG_CACHE_HOME=/tmp/cache \
    VLLM_CACHE_ROOT=/tmp/vllm TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor \
    VLLM_NO_USAGE_STATS=1 VLLM_CONFIGURE_LOGGING=0 VLLM_USE_V2_MODEL_RUNNER=0 \
    APP_LOGGING_CONFIG=/app/config/logging.json INFERENCE_CONFIG=/config/inference.json
USER root
RUN groupadd --gid 10001 inference \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /tmp/home inference \
    && mkdir -p /app /models /config /tmp/home \
    && chown 10001:10001 /models /tmp/home
COPY requirements.txt /app/requirements.txt
COPY scripts/check_runtime.py /app/check_runtime.py
RUN python3 /app/check_runtime.py /app/requirements.txt
COPY src/ /app/
COPY config/logging.json /app/config/logging.json
USER 10001:10001
WORKDIR /app
EXPOSE 8000
ENTRYPOINT ["python3", "-m", "app.launch"]
