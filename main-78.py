"""
PeanutsToon — web komik standalone
Frontend: index.html
Backend: proxy ke Ikiru API by Nat + serve static
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from mangum import Mangum

APP_DIR = Path(__file__).resolve().parent
INDEX_HTML = APP_DIR / "index.html"

# API Ikiru milikmu (bisa diubah lewat env)
IKIRU_API = os.environ.get("IKIRU_API_BASE", "https://ikiru-api-by-nat.vercel.app").rstrip("/")
TIMEOUT = float(os.environ.get("IKIRU_TIMEOUT", "45"))

app = FastAPI(title="PeanutsToon", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "PeanutsToon/1.0 (Nat)",
    "Accept": "application/json",
}


async def upstream_get(path: str, params: Optional[dict] = None) -> Any:
    url = f"{IKIRU_API}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            r = await client.get(url, params=params or {}, headers=HEADERS)
    except httpx.TimeoutException:
        raise HTTPException(504, "Timeout menghubungi Ikiru API")
    except Exception as e:
        raise HTTPException(502, f"Gagal menghubungi Ikiru API: {e}")

    try:
        data = r.json()
    except Exception:
        data = {"detail": r.text[:300]}

    if r.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else str(data)
        raise HTTPException(r.status_code, detail or f"Upstream {r.status_code}")
    return data


@app.get("/")
async def home():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html; charset=utf-8")
    return HTMLResponse("<h1>PeanutsToon</h1><p>index.html tidak ditemukan.</p>")


@app.get("/health")
async def health():
    return {
        "status": "online",
        "app": "PeanutsToon",
        "version": "1.0.0",
        "ikiru_api": IKIRU_API,
        "author": "Nat",
    }


@app.get("/api/latest")
async def api_latest(page: int = Query(1, ge=1)):
    return await upstream_get("/api/latest", {"page": page})


@app.get("/api/search")
async def api_search(q: str = Query(..., min_length=1)):
    return await upstream_get("/api/search", {"q": q})


@app.get("/api/detail/{slug}")
async def api_detail(slug: str):
    return await upstream_get(f"/api/detail/{slug}")


@app.get("/api/chapter")
async def api_chapter(
    slug: str = Query(""),
    chapter: str = Query(""),
    url: str = Query(""),
    id: str = Query(""),
):
    params = {}
    if slug:
        params["slug"] = slug
    if chapter:
        params["chapter"] = chapter
    if url:
        params["url"] = url
    if id:
        params["id"] = id
    if not params:
        raise HTTPException(400, "Berikan slug+chapter atau url")
    return await upstream_get("/api/chapter", params)


# fallback static files next to main.py
@app.get("/{path:path}")
async def spa_fallback(path: str):
    # jangan telan /api
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    candidate = APP_DIR / path
    if candidate.is_file() and candidate.resolve().is_relative_to(APP_DIR.resolve()):
        return FileResponse(candidate)
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html; charset=utf-8")
    raise HTTPException(404, "Not found")


handler = Mangum(app)
