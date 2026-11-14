import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Crop rotation decision-support backend grounded in observed NASA & SoilGrids data."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DISCLAIMER = "This tool supports farmer judgment and does not replace local expertise."


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "data_mode": settings.DATA_MODE,
        "notice": DISCLAIMER
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_mode": settings.DATA_MODE,
        "disclaimer": DISCLAIMER
    }


@app.get("/api/regions")
def get_regions():
    regions_file = settings.DATA_DIR / "demo_regions.json"
    if regions_file.exists():
        with open(regions_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# T7 API routers
from backend.routers import fields, plans, replay, crops
app.include_router(fields.router)
app.include_router(plans.router)
app.include_router(replay.router)
app.include_router(crops.router)
