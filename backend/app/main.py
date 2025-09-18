from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import get_settings
from .services.mcp_client import enhance_text as enhance_with_mcp


class EchoIn(BaseModel):
    message: str


class EchoOut(BaseModel):
    message: str
    length: int


class EnhanceIn(BaseModel):
    text: str
    instructions: Optional[str] = None
    model: Optional[str] = None


class EnhanceOut(BaseModel):
    original: str
    enhanced: str


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FastAPI + React Sample", version="0.1.0")

    # CORS
    origins = settings.cors_origins
    if origins:
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

    @app.post("/api/enhance", response_model=EnhanceOut)
    async def enhance(payload: EnhanceIn) -> EnhanceOut:
        try:
            result = await enhance_with_mcp(
                text=payload.text,
                instructions=payload.instructions,
                model=payload.model,
            )
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return EnhanceOut(**result)

    return app


app = create_app()
