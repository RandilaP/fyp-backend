import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api import user_crud, auth, ward, bht_record, llm_report, patient

logging.basicConfig(level=logging.INFO)

app = FastAPI()


@app.middleware("http")
async def capture_raw_body(request: Request, call_next):
    """Read and store the raw request body so we can log it if JSON parsing fails.

    This middleware reads the body into memory and attaches it to request.state.raw_body.
    It's intended for debugging only (remove or limit in production).
    """
    body = await request.body()
    request.state.raw_body = body
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Try to present a helpful preview of the raw body that caused the JSON decode error
    raw = getattr(request.state, "raw_body", b"")
    try:
        decoded = raw.decode("utf-8", "replace")
    except Exception:
        decoded = str(raw)
    logging.error("Request validation error: %s", exc)
    logging.error("Raw request body (truncated 1000 chars): %s", decoded[:1000])
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "raw_body_preview": decoded[:1000]},
    )


app.include_router(user_crud.router, prefix="/api", tags=["users"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(ward.router, prefix="/api", tags=["wards"])
app.include_router(bht_record.router, prefix="/api", tags=["bht_records"])
app.include_router(llm_report.router, prefix="/api", tags=["llm_reports"])
app.include_router(patient.router, prefix="/api", tags=["patients"])

# Ensure OpenAPI exposes a clear Bearer auth scheme named 'bearerAuth'
from fastapi.openapi.utils import get_openapi


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        routes=app.routes,
    )
    # define a clear bearer scheme
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    openapi_schema["components"]["securitySchemes"]["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }

    # remove any leftover HTTPBearer entry so the UI only shows bearerAuth
    sec_schemes = openapi_schema["components"]["securitySchemes"]
    if "HTTPBearer" in sec_schemes:
        sec_schemes.pop("HTTPBearer", None)

    # replace any HTTPBearer usages with bearerAuth
    paths = openapi_schema.get("paths", {})
    for path_item in paths.values():
        for operation in path_item.values():
            sec = operation.get("security")
            if sec:
                new_sec = []
                for s in sec:
                    if "HTTPBearer" in s:
                        new_sec.append({"bearerAuth": []})
                    else:
                        new_sec.append(s)
                operation["security"] = new_sec

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)