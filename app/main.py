"""
Stash - Ephemeral Agent RAM
Main application entry point
"""

from fastapi import FastAPI

# Create the FastAPI application instance
# This is the core object that handles all routing and middleware

app = FastAPI(
    title="Stash",
    description="Ephemeral key-value store for AI agents",
    version="0.1.0"
)

# Define a route using a "@decorator"
# The @app.get("/") decorator tells FastAPI:
# "When someone makes a GET request to /, call this function"
@app.get("/")
# Asynchronous (non-blocking) - handle other requests while waiting
async def root():
    """
    Health check endpoint.
    Returns a simple message to confirm the API is running
    """
    return {"status": "ok", "message": "Stash is running"}

@app.get("/health")
async def health_check():
    """
    Detailed health check.
    In production, this would check Redis connectivity
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
        "mode": "local"
    }