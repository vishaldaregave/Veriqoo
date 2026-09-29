from fastapi import FastAPI

from app.config import get_settings
from app.api.routes.analyze import router as analyze_router


app = FastAPI(
    title="LegalMetrologyAI Backend",
    version=get_settings().app_version,
    description=(
        "Shared backend for Legal Metrology AI analysis "
        "across Flutter, Telegram, and future channels."
    ),
)


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "LegalMetrologyAI Backend",
    }


# Register analysis routes
app.include_router(analyze_router)