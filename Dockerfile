FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    TMPDIR=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
RUN command -v lottie_convert.py \
    && ffmpeg -hide_banner -decoders 2>&1 | grep -q 'libvpx-vp9'

FROM base AS test

COPY tests ./tests
RUN pip install --no-cache-dir ".[dev,security]"

FROM base AS runtime

CMD ["python", "-m", "app.main"]
