"""
Pydantic models for request/response validation.

These models serve 3 purposes:
1. Validate incoming request data
2. Serialize outgoing response data
3. Generate OpenAPI documentation automatically. 
"""

from pydantic import BaseModel, Field, field_validator
from typing  import Any
from datetime import datetime

# ============================================================
# REQUEST MODELS (what the client sends to us)
# ============================================================

class StashRequest(BaseModel):
    """
    Request boy for POST /stash endpoint

    Example:
    {
        "data": {"task": "summarize", "context": "..."},
        "ttl": 3600
    }

    """

    # Field() lets us add validation rules and documentation
    data: Any = Field(
        ..., # ... means "required"
        description="Any valid JSON data to store"
    )
    ttl: int = Field(
        default=3600,   # Default to 1 hour
        ge=1,           # Greater than or equal to 1
        le=86400,       # less than or equal to 24 hours
        description="Time-to-live in seconds (1 to 864000)"
    )

    @field_validator('ttl')
    @classmethod
    def ttl_must_be_reasonable(cls, v: int) -> int:
        """
        Ensure TTL is within acceptable bounds.
        """
        if v < 1:
            raise ValueError('TTL must be at least 1 second')
        return v
    
class ExtendRequest(BaseModel):
    """
    Request body for PATCH /extend/{memory_id} endpoint.
    """

    extra_seconds: int = Field(
        ...,
        ge=1,
        le=86400,
        description="Addtional seconds to add to TTL"
    )

# ============================================================
# RESPONSE MODELS (what we send back to the client)
# ============================================================

class StashResponse(BaseModel):
    """
    Response for successful stash operation.
    """

    memory_id: str = Field(
        ...,
        description="Unique identifier to recall this memory"
    )

    ttl: int = Field(
        ...,
        description="Time-to-live in seconds"
    )

    expires_at: datetime = Field(
        ...,
        description="UTC timestamp when this memory expires"
    )

class RecallResponse(BaseModel):
    """
    Response for successful recall operation.
    """

    memory_id: str = Field(..., description="The requested memory_id")
    data: Any = Field(..., description="The stored JSON data")
    ttl_remaining: int = Field(..., description="Seconds until expiration")

class ExtendResponse(BaseModel):
    """
    Response for successful recall operation.
    """

    memory_id: str = Field(..., description="The extended memory_id")
    new_ttl: int = Field(..., description="New TTL in seconds")
    expires_at: datetime = Field(..., description="New expiration timestamp")

class ErrorResponse(BaseModel):
    """
    Standard error response format.
    """

    error: str = Field(..., description="Error Type")
    detail: str = Field(..., description="Human-readable error message")

# ============================================================
# MODEL CONFIGURATION
# ============================================================

class StashRequest(StashRequest):
    """
    Add example to the schema for documentation.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "data": {
                        "task": "summarize_document",
                        "partial_result": "The document discusses...",
                        "step": 2
                    },
                    "ttl": 3600
                }
            ]
        }
    }