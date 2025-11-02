# Start from a small official Python image
FROM python:3.11-slim

# Do not buffer stdout/stderr and avoid writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required by Pillow, onnxruntime and rembg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    wget \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    libgl1 \
 && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt /app/requirements.txt

# Upgrade pip and install Python dependencies. Use --no-cache to keep image small.
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Expose the port the app runs on
EXPOSE 8080

# NOTE: rembg will download model files on first run (cache under ~/.cache).
# For production consider pre-downloading models or mounting a cache volume.

# Use gunicorn for production; fall back to Flask dev server if you run the image directly
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]
