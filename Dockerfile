# Use the official Python 3.11 lightweight slim base image
FROM python:3.11-slim

# Set environment optimization flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Create and set application directory
WORKDIR /app

# Install base system compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python package dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose server listener port
EXPOSE 8000

# Configure non-privileged service account for security sandbox execution
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

# Run FastAPI with uvicorn bound to env-configured port (crucial for cloud platforms like Render)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
