# ---- Build stage ----
    FROM python:3.12-slim AS builder
    WORKDIR /build
    RUN python -m venv /opt/venv
    ENV PATH="/opt/venv/bin:$PATH"
    COPY requirements.txt requirements-ai.txt ./
    RUN pip install --no-cache-dir -r requirements.txt -r requirements-ai.txt

    # ---- Runtime stage ----
    FROM python:3.12-slim
    COPY --from=builder /opt/venv /opt/venv
    ENV PATH="/opt/venv/bin:$PATH" \
        PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1
    WORKDIR /app
    COPY . .
    RUN useradd --create-home appuser && chown -R appuser /app
    USER appuser
    CMD ["python", "-m", "src", "run-daily", "--user", "saida"]