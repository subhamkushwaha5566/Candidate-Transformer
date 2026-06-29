import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from app.api.routes import router
from app.config import settings

app = FastAPI(
    title="Multi-Source Candidate Data Transformer",
    description="Transforms, merges, and normalizes candidate data from various sources.",
    version="1.0.0",
)

# Mount the static directory for CSS and JS assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router, prefix="/api/v1")

@app.get("/")
def serve_dashboard():
    """
    Serves the premium single-page UI dashboard.
    """
    static_file_path = os.path.join("app", "static", "index.html")
    if os.path.exists(static_file_path):
        return FileResponse(static_file_path)
    return HTMLResponse("<h1>Multi-Source Candidate Data Transformer (Dashboard file missing)</h1>")

@app.get("/health")
def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
