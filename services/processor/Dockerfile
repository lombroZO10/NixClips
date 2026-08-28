FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .[vision,diarization]

ENV NIXCLIP_HOST=0.0.0.0 NIXCLIP_PORT=8788
EXPOSE 8788
CMD ["uvicorn", "nixclip_processor.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8788"]
