# Build context must be the repository root so `pip install -e .` can see
# pyproject.toml and src/. Build with:
#   docker build -f services/api-gateway/Dockerfile -t mini-exchange-gateway .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MATCHING_SERVICE_URL=http://localhost:8001

WORKDIR /code

# Install the root package; its dependencies include fastapi, uvicorn, httpx.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e .

# Bring in the gateway application code.
COPY services/api-gateway/app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
