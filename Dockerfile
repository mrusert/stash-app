# Use Python 3.11 slim image (smaller than full image)
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install dependencies first (this layer gets cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create non-root user and data directory
RUN useradd --create-home appuser && \
    mkdir -p /data && \
    chown appuser:appuser /data

USER appuser

# Expose port
EXPOSE 8000

# Command to run when container starts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]