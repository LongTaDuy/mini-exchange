# Build context must be the repository root so `pip install -e .` can see
# pyproject.toml and src/. Build with:
#   docker build -f services/matching-service/Dockerfile -t mini-exchange-matching .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# Install the shared root package (provides the `mini_exchange` core library).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e .

# Bring in the matching service application code.
COPY services/matching-service/app ./app

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
