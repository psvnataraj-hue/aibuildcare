import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# allow `python app/main.py` (add the backend/ dir so `app` is importable)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import get_settings  # noqa: E402
from app.routers import (  # noqa: E402
    admin,
    auth,
    complaints,
    health,
    webhooks,
)


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(complaints.router)
    app.include_router(admin.router)
    app.include_router(webhooks.router)

    @app.on_event("startup")
    def _startup() -> None:
        from app.seed import seed

        seed()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
