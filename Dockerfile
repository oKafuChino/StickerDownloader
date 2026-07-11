FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

FROM base AS test

COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]"

FROM base AS runtime

CMD ["python", "-m", "app.main"]

