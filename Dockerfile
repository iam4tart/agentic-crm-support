FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build-essential, dos2unix, and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    dos2unix \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

# Install curl and dos2unix in the final image
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
COPY . .

# Fix line endings and permissions
RUN dos2unix start.sh && chmod +x start.sh

ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000 7860

CMD ["bash", "./start.sh"]
