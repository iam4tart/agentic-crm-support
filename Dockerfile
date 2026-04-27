FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build-essential and dos2unix to fix line endings
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

# Install dos2unix in the final image as well to be safe
RUN apt-get update && apt-get install -y --no-install-recommends \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
COPY . .

# Fix line endings and permissions for the startup script
RUN dos2unix start.sh && chmod +x start.sh

ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000 7860

CMD ["bash", "./start.sh"]
