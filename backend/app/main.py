from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic import HttpUrl
from tempfile import NamedTemporaryFile
import os


from .config import get_settings
from .services.mcp_client import (
    enhance_text as enhance_with_mcp,
    rag_import as mcp_rag_import,
    rag_search as mcp_rag_search,
    rag_sources as mcp_rag_sources,
    rag_upsert_text as mcp_rag_upsert,
)


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
    message_id: Optional[int] = None
    enhanced_id: Optional[int] = None
    processing: Dict[str, Any]


class RagImportPayload(BaseModel):
    urls: Optional[List[HttpUrl]] = None
    texts: Optional[List[str]] = None
    store: Optional[str] = None
    source_prefix: Optional[str] = None


class RagImportResult(BaseModel):
    id: str
    source: Optional[str] = None
    store: Optional[str] = None


class RagImportResponse(BaseModel):
    items: List[RagImportResult]


class RagSearchResponseItem(BaseModel):
    id: str
    source: Optional[str] = None
    store: Optional[str] = None
    score: float
    snippet: str


class RagSearchResponse(BaseModel):
    results: List[RagSearchResponseItem]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MCP Relay", version="0.1.0")

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

    @app.get("/api/rag/stores", response_model=List[str])
    async def rag_list_stores() -> List[str]:
        return await mcp_rag_sources()

    @app.post("/api/rag/import", response_model=RagImportResponse)
    async def rag_import(payload: RagImportPayload) -> RagImportResponse:
        items: List[RagImportResult] = []

        urls = payload.urls or []
        source_prefix = payload.source_prefix or ""

        for url in urls:
            data = await mcp_rag_import(
                location=str(url),
                store=payload.store,
                source=source_prefix or str(url),
            )
            items.append(RagImportResult(**data))

        texts = payload.texts or []
        for idx, text in enumerate(texts, start=1):
            if not text.strip():
                continue
            source = source_prefix or f"text-{idx}"
            data = await mcp_rag_upsert(content=text, store=payload.store, source=source)
            items.append(RagImportResult(**data))

        return RagImportResponse(items=items)

    @app.post("/api/rag/upload", response_model=RagImportResponse)
    async def rag_upload(
        files: List[UploadFile] = File(...),
        store: Optional[str] = Form(None),
        source_prefix: Optional[str] = Form(None),
    ) -> RagImportResponse:
        items: List[RagImportResult] = []
        for index, uploaded in enumerate(files, start=1):
            data = await uploaded.read()
            if not data:
                continue
            suffix = os.path.splitext(uploaded.filename or "upload.txt")[1]
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                source = source_prefix or uploaded.filename or f"file-{index}"
                result = await mcp_rag_import(location=tmp_path, store=store, source=source)
                items.append(RagImportResult(**result))
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        return RagImportResponse(items=items)

    @app.get("/api/rag/search", response_model=RagSearchResponse)
    async def rag_search(
        query: str = Query(..., min_length=1),
        limit: int = Query(3, ge=1, le=20),
        store: Optional[str] = Query(None),
    ) -> RagSearchResponse:
        store_filters = None
        if store:
            store_filters = [part.strip() for part in store.split(",") if part.strip()]
        raw_results = await mcp_rag_search(query=query, limit=limit, stores=store_filters)
        items: List[RagSearchResponseItem] = []
        for entry in raw_results:
            content = entry.get("content", "")
            snippet = content[:400]
            items.append(
                RagSearchResponseItem(
                    id=str(entry.get("id")),
                    source=entry.get("source"),
                    store=entry.get("store"),
                    score=float(entry.get("score", 0.0)),
                    snippet=snippet,
                )
            )
        return RagSearchResponse(results=items)

    return app


app = create_app()
