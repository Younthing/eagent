from importlib.metadata import version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.actions import config, health, preprocess

try:
    app_version = version("eagent")
except Exception:
    app_version = "0.0.0"

app = FastAPI(
    title="EAgent API",
    description="Production-ready LangGraph agent API",
    version=app_version,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(config.router)
app.include_router(preprocess.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
