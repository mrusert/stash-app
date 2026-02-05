"""
Custom Middleware for request processing.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class PayloadSizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate request payload size.

    Checks content-length header before reading the body.
    This prevents memory exhaustion from oversized requests.

    Note: We use a conservative default limit here. The actual tier-based limit is enforced in the route handler after authentication.
    """

    DEFAULT_LIMIT = 1_048_576  # 1 MB

    async def dispatch(self, request, call_next):
        """
        Check payload size before processing the request.
        """
        if request.method in ("POST","PUT" ,"PATCH"):
            content_length = request.headers.get("content-length")

            if content_length:
                size = int(content_length)

                if size > self.DEFAULT_LIMIT:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Payload Too Large",
                            "detail": f"Request body ({size} bytes) exceeds limit ({self.DEFAULT_LIMIT} bytes)",
                            "limit_bytes": self.DEFAULT_LIMIT,
                        }
                    )
        # Continue to the route handler
        response = await call_next(request)
        return response