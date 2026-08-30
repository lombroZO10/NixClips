FROM denoland/deno:bin-2.9.5 AS deno

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=deno /deno /usr/local/bin/deno
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 ca-certificates && rm -rf /var/lib/apt/lists/*
# Documentation and application source must not invalidate the multi-gigabyte
# inference dependency layer. Only pyproject.toml participates in this cache.
COPY pyproject.toml ./
# Install the expensive CPU inference stack in a source-independent layer.
# Only yt-dlp uses the nightly channel; the rest stays on stable releases.
RUN mkdir -p src/nixclip_processor \
  && touch src/nixclip_processor/__init__.py \
  && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio \
  && pip install --no-cache-dir .[vision,diarization] \
  && pip install --no-cache-dir --upgrade --pre "yt-dlp[default]" \
  && rm -rf src
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

ENV NIXCLIP_HOST=0.0.0.0 NIXCLIP_PORT=8788
EXPOSE 8788
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8788/health', timeout=3)" || exit 1
CMD ["uvicorn", "nixclip_processor.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8788"]
