from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import get_settings


class EchoIn(BaseModel):
    message: str


class EchoOut(BaseModel):
    message: str
    length: int


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FastAPI + React Sample", version="0.1.0")

    # CORS
    if settings.cors_origins:
        origins = [o.strip() for o in settings.cors_origins] if isinstance(settings.cors_origins, list) else ["*"]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/healthz")
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/echo", response_model=EchoOut)
    def echo(payload: EchoIn) -> EchoOut:
        return EchoOut(message=payload.message, length=len(payload.message))

    return app


app = create_app()

