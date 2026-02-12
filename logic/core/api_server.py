import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from bull_project.bull_bot.config.constants import ABS_UPLOADS_DIR
from bull_project.bull_bot.database.setup import init_db
from bull_project.bull_bot.api.routes.rooms import router as rooms_router
from bull_project.bull_bot.api.routes.admin_requests import router as admin_requests_router
from bull_project.bull_bot.api.routes.open_date import router as open_date_router
from bull_project.bull_bot.api.routes.websockets import router as websockets_router
from bull_project.bull_bot.api.routes.packages import router as packages_router
from bull_project.bull_bot.api.routes.bookings import router as bookings_router
from bull_project.bull_bot.api.routes.care import router as care_router
from bull_project.bull_bot.api.routes.passports import router as passports_router
from bull_project.bull_bot.api.routes.admin import router as admin_router

os.makedirs(ABS_UPLOADS_DIR, exist_ok=True)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type"],
)

app.include_router(rooms_router)
app.include_router(admin_requests_router)
app.include_router(open_date_router)
app.include_router(websockets_router)
app.include_router(packages_router)
app.include_router(bookings_router)
app.include_router(care_router)
app.include_router(passports_router)
app.include_router(admin_router)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARE_WEBAPP_DIR = os.path.join(PROJECT_ROOT, "care_webapp")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

@app.on_event("startup")
async def startup_event():
    await init_db()

if os.path.isdir(CARE_WEBAPP_DIR):
    app.mount(
        "/care-webapp",
        StaticFiles(directory=CARE_WEBAPP_DIR, html=True),
        name="care-webapp",
    )
if os.path.isdir(ASSETS_DIR):
    app.mount(
        "/assets",
        StaticFiles(directory=ASSETS_DIR, html=False),
        name="assets",
    )


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/")
async def root():
    index_path = os.path.join(CARE_WEBAPP_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Bull API", "status": "running"}


@app.get("/{full_path:path}")
async def catch_all(full_path: str):

    if full_path.startswith("api/"):
        return {"error": "API endpoint not found"}

    file_path = os.path.join(CARE_WEBAPP_DIR, full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)

    asset_path = os.path.join(ASSETS_DIR, full_path)
    if os.path.exists(asset_path) and os.path.isfile(asset_path):
        return FileResponse(asset_path)

    
    index_path = os.path.join(CARE_WEBAPP_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {"error": "Not found"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT") or os.getenv("PORT0") or "8000")
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=port,
    )
