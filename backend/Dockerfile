FROM python:3.11-slim

# ffmpeg + fonts (fonts needed so libass can render the burned-in captions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# faster-whisper is heavy; it's listed in requirements but only imported lazily.
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects $PORT
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
