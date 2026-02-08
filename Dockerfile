# Use Python 3.11 slim image (smaller than full image)
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install dependencies first (this layer gets cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create data directory for SQLite (writable by any user)
RUN mkdir -p /app/data && chmod 777 /app/data

# Point SQLite database to the writable data directory
ENV USERS_DB_PATH=/app/data/users.db

# Create non-root user
RUN useradd --create-home appuser

USER appuser

# Expose port
EXPOSE 8000

# Command to run when container starts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]