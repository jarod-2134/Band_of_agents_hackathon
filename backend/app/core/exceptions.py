from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

class PlatformException(HTTPException):
    """
    Custom exception class to explicitly enforce our machine-readable contract code strings.
    """
    def __init__(self, status_code: int, code: str, message: str, field: str | None = None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.field = field

async def platform_exception_handler(request: Request, exc: PlatformException):
    """Formats intentional domain errors into the state-machine contract."""
    request_id = getattr(request.state, "request_id", "req-unknown")
    if hasattr(request, "headers") and not request_id or request_id == "req-unknown":
        request_id = request.headers.get("x-request-id", "req-unknown")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "field": exc.field,
                "request_id": request_id
            }
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Overwrites default FastAPI 422 parameters to align structural schema errors."""
    request_id = getattr(request.state, "request_id", "req-unknown")
    if hasattr(request, "headers") and not request_id or request_id == "req-unknown":
        request_id = request.headers.get("x-request-id", "req-unknown")

    # Extract the first failing parameter element description
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    
    # Reconstruct readable target path string (e.g., "body.email" or "query.slug")
    loc = ".".join(str(x) for x in first_error.get("loc", ["body"]))
    msg = first_error.get("msg", "Validation error encountered.")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": {
                "code": "validation_error",
                "message": f"Field validation failed at {loc}: {msg}",
                "field": loc,
                "request_id": request_id
            }
        }
    )