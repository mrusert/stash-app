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

