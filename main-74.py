"""
PeanutsToon v1.2.1 — multi-source via API only (no scrape fallback)
Sources: Ikiru · AinzScans · ManhwaIndo · Shinigami (opsional env)
By: Nat
"""
from __future__ import annotations

import os
import asyncio
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from mangum import Mangum

APP_DIR = Path(__file__).resolve().parent
INDEX_HTML = APP_DIR / "index.html"

IKIRU_API = os.environ.get("IKIRU_API_BASE", "https://ikiru-api-by-nat.vercel.app").rstrip("/")
AINZ_API = os.environ.get("AINZ_API_BASE", "https://ainz-scans-api-by-nat2.vercel.app").rstrip("/")
MANHWAINDO_API = os.environ.get("MANHWAINDO_API_BASE", "https://manhwa-indo-api-by-nat.vercel.app").rstrip("/")
SHINIGAMI_API = os.environ.get("SHINIGAMI_API_BASE", "").rstrip("/")
TIMEOUT = float(os.environ.get("PT_TIMEOUT", "15"))

app = FastAPI(title="PeanutsToon", version="1.2.2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JSON_HEADERS = {"User-Agent": "PeanutsToon/1.2 (Nat)", "Accept": "application/json"}


def _item(judul, slug, thumb, type_, source, **extra):
    return {
        "judul": (judul or slug or "").strip() or slug,
        "slug": (slug or "").strip(),
        "thumbnail": thumb or "",
        "type": (type_ or "").upper() or "COMIC",
        "source": source,
        **extra,
    }


async def _json(url: str, params: Optional[dict] = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
            r = await c.get(url, params=params or {}, headers=JSON_HEADERS)
    except httpx.TimeoutException:
        raise HTTPException(504, "Timeout upstream")
    except Exception as e:
        raise HTTPException(502, f"{type(e).__name__}")
    try:
        data = r.json()
    except Exception:
        data = {"detail": (r.text or "")[:300]}
    if r.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else str(data)
        raise HTTPException(r.status_code, detail or f"HTTP {r.status_code}")
    return data


async def _safe(coro, timeout: float = 12.0):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception:
        return []


# ---- Ikiru ----
async def ikiru_latest(page=1):
    data = await _json(f"{IKIRU_API}/api/latest", {"page": page})
    return [
        _item(it.get("judul"), it.get("slug"), it.get("thumbnail"), it.get("type") or "MANHWA", "ikiru")
        for it in (data.get("data") or [])
        if isinstance(it, dict) and it.get("slug")
    ]


async def ikiru_search(q):
    data = await _json(f"{IKIRU_API}/api/search", {"q": q})
    return [
        _item(it.get("judul"), it.get("slug"), it.get("thumbnail"), it.get("type") or "", "ikiru")
        for it in (data.get("data") or [])
        if isinstance(it, dict) and it.get("slug")
    ]


async def ikiru_detail(slug):
    data = await _json(f"{IKIRU_API}/api/detail/{slug}")
    d = data.get("data") if isinstance(data.get("data"), dict) else data
    if not isinstance(d, dict):
        d = {}
    chapters = d.get("chapters") or []
    return {
        "status": True,
        "source": "ikiru",
        "data": {
            "judul": d.get("judul") or d.get("title") or slug,
            "slug": d.get("slug") or slug,
            "thumbnail": d.get("thumbnail") or d.get("cover") or "",
            "sinopsis": d.get("sinopsis") or d.get("synopsis") or "",
            "genre": d.get("genre") or d.get("genres") or [],
            "status": d.get("status") or "",
            "type": d.get("type") or "",
            "chapters": chapters,
            "source": "ikiru",
        },
    }


async def ikiru_chapter(**kw):
    params = {k: v for k, v in kw.items() if v}
    return await _json(f"{IKIRU_API}/api/chapter", params)


# ---- AinzScans ----
async def ainz_latest(page=1):
    data = await _json(f"{AINZ_API}/api/latest", {"page": page})
    return [
        _item(it.get("judul"), it.get("slug"), it.get("thumbnail"), it.get("type") or "MANGA", "ainzscans")
        for it in (data.get("data") or [])
        if isinstance(it, dict) and it.get("slug")
    ]


async def ainz_search(q):
    data = await _json(f"{AINZ_API}/api/search", {"q": q})
    return [
        _item(it.get("judul"), it.get("slug"), it.get("thumbnail"), it.get("type") or "", "ainzscans")
        for it in (data.get("data") or [])
        if isinstance(it, dict) and it.get("slug")
    ]


async def ainz_detail(slug):
    data = await _json(f"{AINZ_API}/api/detail/{slug}")
    d = data.get("data") if isinstance(data.get("data"), dict) else {}
    chapters = []
    for ch in d.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        chapters.append({
            "judul": ch.get("judul") or f"Chapter {ch.get('number', '')}",
            "slug": ch.get("slug") or "",
            "number": str(ch.get("number") or ""),
            "url": ch.get("url") or "",
        })
    return {
        "status": True,
        "source": "ainzscans",
        "data": {
            "judul": d.get("judul") or slug,
            "slug": d.get("slug") or slug,
            "thumbnail": d.get("thumbnail") or "",
            "sinopsis": d.get("sinopsis") or "",
            "genre": d.get("genre") or [],
            "status": d.get("status") or "",
            "type": d.get("type") or "",
            "chapters": chapters,
            "source": "ainzscans",
        },
    }


async def ainz_chapter(slug="", chapter="", url=""):
    params = {"url": url} if url else {"slug": slug, "chapter": chapter}
    return await _json(f"{AINZ_API}/api/chapter", params)


# ---- ManhwaIndo ----
async def manhwaindo_latest(page=1):
    data = await _json(f"{MANHWAINDO_API}/api/latest", {"page": page})
    return [
        _item(it.get("judul"), it.get("slug"), it.get("thumbnail") or it.get("sampul"), "MANHWA", "manhwaindo")
        for it in (data.get("data") or [])
        if isinstance(it, dict) and it.get("slug")
    ]


async def manhwaindo_search(q):
    data = await _json(f"{MANHWAINDO_API}/api/search", {"q": q})
    return [
        _item(it.get("judul"), it.get("slug"), it.get("thumbnail") or it.get("sampul"), "MANHWA", "manhwaindo")
        for it in (data.get("data") or [])
        if isinstance(it, dict) and it.get("slug")
    ]


async def manhwaindo_detail(slug):
    # API returns flat object (not always nested under data)
    data = await _json(f"{MANHWAINDO_API}/api/detail/{slug}")
    d = data.get("data") if isinstance(data.get("data"), dict) else data
    if not isinstance(d, dict):
        d = {}
    chapters = []
    for ch in d.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        num = str(ch.get("chapter") or ch.get("number") or "")
        chapters.append({
            "judul": ch.get("title") or ch.get("judul") or (f"Chapter {num}" if num else "Chapter"),
            "slug": str(ch.get("id") or ch.get("slug") or num),
            "number": num,
            "url": ch.get("url") or "",
            "id": str(ch.get("id") or ""),
        })
    return {
        "status": True,
        "source": "manhwaindo",
        "data": {
            "judul": d.get("judul") or d.get("title") or slug,
            "slug": d.get("slug") or slug,
            "thumbnail": d.get("thumbnail") or d.get("sampul") or "",
            "sinopsis": d.get("sinopsis") or d.get("synopsis") or "",
            "genre": d.get("genres") or d.get("genre") or [],
            "status": d.get("status") or "",
            "type": d.get("type") or "MANHWA",
            "chapters": chapters,
            "source": "manhwaindo",
        },
    }


async def manhwaindo_chapter(slug="", chapter="", url="", id=""):
    params = {}
    if url:
        params["url"] = url
    elif id:
        params["id"] = id
    elif chapter:
        if str(chapter).startswith("http"):
            params["url"] = chapter
        else:
            params["id"] = chapter
    if not params:
        raise HTTPException(400, "url atau id chapter dibutuhkan (ManhwaIndo)")
    data = await _json(f"{MANHWAINDO_API}/api/chapter", params)
    # normalize images field for frontend
    images = data.get("images") or data.get("gambar") or []
    if isinstance(data.get("data"), list):
        images = data["data"] or images
    return {"status": True, "source": "manhwaindo", "images": images, "url": data.get("url") or url}


# ---- Shinigami (API only, butuh SHINIGAMI_API_BASE) ----
async def shinigami_latest(page=1):
    if not SHINIGAMI_API:
        return []
    data = await _json(f"{SHINIGAMI_API}/api/manga/latest", {"page": page})
    rows = data.get("data") or data.get("results") or (data if isinstance(data, list) else [])
    out = []
    for it in rows:
        if not isinstance(it, dict):
            continue
        sid = str(it.get("id") or it.get("slug") or "")
        if not sid:
            continue
        out.append(_item(it.get("title") or it.get("judul") or sid, sid, it.get("cover") or it.get("thumbnail") or "", it.get("type") or "MANHWA", "shinigami"))
    return out


async def shinigami_search(q):
    if not SHINIGAMI_API:
        return []
    data = await _json(f"{SHINIGAMI_API}/api/manga/search", {"q": q})
    rows = data.get("data") or data.get("results") or (data if isinstance(data, list) else [])
    out = []
    for it in rows:
        if not isinstance(it, dict):
            continue
        sid = str(it.get("id") or it.get("slug") or "")
        if not sid:
            continue
        out.append(_item(it.get("title") or it.get("judul") or sid, sid, it.get("cover") or it.get("thumbnail") or "", it.get("type") or "", "shinigami"))
    return out


async def shinigami_detail(slug):
    if not SHINIGAMI_API:
        raise HTTPException(503, "SHINIGAMI_API_BASE belum di-set di Environment Variables")
    data = await _json(f"{SHINIGAMI_API}/api/manga/{slug}")
    d = data.get("data") if isinstance(data.get("data"), dict) else data
    if not isinstance(d, dict):
        d = {}
    chapters = []
    chs = d.get("chapters") or []
    if not chs:
        try:
            ch_raw = await _json(f"{SHINIGAMI_API}/api/manga/{slug}/chapters")
            chs = ch_raw.get("data") or ch_raw.get("chapters") or []
        except Exception:
            chs = []
    for ch in chs:
        if not isinstance(ch, dict):
            continue
        chapters.append({
            "judul": ch.get("title") or ch.get("judul") or str(ch.get("number", "")),
            "slug": str(ch.get("id") or ch.get("slug") or ""),
            "number": str(ch.get("number") or ""),
            "url": ch.get("url") or "",
        })
    return {
        "status": True,
        "source": "shinigami",
        "data": {
            "judul": d.get("title") or d.get("judul") or slug,
            "slug": slug,
            "thumbnail": d.get("cover") or d.get("thumbnail") or "",
            "sinopsis": d.get("description") or d.get("sinopsis") or "",
            "genre": d.get("genres") or d.get("genre") or [],
            "status": d.get("status") or "",
            "type": d.get("type") or "MANHWA",
            "chapters": chapters,
            "source": "shinigami",
        },
    }


async def shinigami_chapter(slug="", chapter="", url="", id=""):
    if not SHINIGAMI_API:
        raise HTTPException(503, "SHINIGAMI_API_BASE belum di-set")
    cid = chapter or id
    if not cid:
        raise HTTPException(400, "chapter id dibutuhkan")
    data = await _json(f"{SHINIGAMI_API}/api/manga/chapter/{cid}/pages")
    pages = data.get("data") or data.get("pages") or data.get("images") or []
    images = []
    for p in pages:
        if isinstance(p, str) and p.startswith("http"):
            images.append(p)
        elif isinstance(p, dict):
            u = p.get("url") or p.get("src") or ""
            if u.startswith("http"):
                images.append(u)
    return {"status": True, "source": "shinigami", "images": images}


# ---- Routes ----
@app.get("/")
async def home():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html; charset=utf-8")
    return HTMLResponse("<h1>PeanutsToon</h1>")


@app.get("/health")
async def health():
    sources = ["ikiru", "ainzscans", "manhwaindo"]
    if SHINIGAMI_API:
        sources.append("shinigami")
    return {
        "status": "online",
        "app": "PeanutsToon",
        "version": "1.2.2",
        "sources": sources,
        "ikiru_api": IKIRU_API,
        "ainz_api": AINZ_API,
        "manhwaindo_api": MANHWAINDO_API,
        "shinigami_api": SHINIGAMI_API or None,
        "author": "Nat",
    }


@app.get("/api/sources")
async def api_sources():
    sources = [
        {"id": "all", "name": "Semua"},
        {"id": "ikiru", "name": "Ikiru"},
        {"id": "ainzscans", "name": "AinzScans"},
        {"id": "manhwaindo", "name": "ManhwaIndo"},
    ]
    if SHINIGAMI_API:
        sources.append({"id": "shinigami", "name": "Shinigami"})
    return {"sources": sources}


@app.get("/api/latest")
async def api_latest(page: int = Query(1, ge=1), source: str = Query("all")):
    source = (source or "all").lower()
    tasks = []
    if source in ("all", "ikiru"):
        tasks.append(_safe(ikiru_latest(page)))
    if source in ("all", "ainzscans"):
        tasks.append(_safe(ainz_latest(page)))
    if source in ("all", "manhwaindo"):
        tasks.append(_safe(manhwaindo_latest(page)))
    if source in ("all", "shinigami") and SHINIGAMI_API:
        tasks.append(_safe(shinigami_latest(page)))
    parts = await asyncio.gather(*tasks) if tasks else []
    items = []
    for part in parts:
        items += part or []
    seen, out = set(), []
    for it in items:
        key = f"{it.get('source')}:{it.get('slug')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return {"status": True, "page": page, "source": source, "total": len(out), "data": out}


@app.get("/api/search")
async def api_search(q: str = Query(..., min_length=1), source: str = Query("all")):
    source = (source or "all").lower()
    q = q.strip()
    tasks = []
    if source in ("all", "ikiru"):
        tasks.append(_safe(ikiru_search(q)))
    if source in ("all", "ainzscans"):
        tasks.append(_safe(ainz_search(q)))
    if source in ("all", "manhwaindo"):
        tasks.append(_safe(manhwaindo_search(q)))
    if source in ("all", "shinigami") and SHINIGAMI_API:
        tasks.append(_safe(shinigami_search(q)))
    parts = await asyncio.gather(*tasks) if tasks else []
    items = []
    for part in parts:
        items += part or []
    seen, out = set(), []
    for it in items:
        key = f"{it.get('source')}:{it.get('slug')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return {"status": True, "query": q, "source": source, "total": len(out), "data": out}


@app.get("/api/detail/{slug}")
async def api_detail(slug: str, source: str = Query("ikiru")):
    source = (source or "ikiru").lower()
    if source == "ainzscans":
        return await ainz_detail(slug)
    if source == "manhwaindo":
        return await manhwaindo_detail(slug)
    if source == "shinigami":
        return await shinigami_detail(slug)
    return await ikiru_detail(slug)


@app.get("/api/chapter")
async def api_chapter(
    source: str = Query("ikiru"),
    slug: str = Query(""),
    chapter: str = Query(""),
    url: str = Query(""),
    id: str = Query(""),
):
    source = (source or "ikiru").lower()
    ch = chapter or id
    if source == "ainzscans":
        return await ainz_chapter(slug=slug, chapter=ch, url=url)
    if source == "manhwaindo":
        return await manhwaindo_chapter(slug=slug, chapter=ch, url=url, id=id or ch)
    if source == "shinigami":
        return await shinigami_chapter(slug=slug, chapter=ch, url=url, id=id)
    return await ikiru_chapter(slug=slug, chapter=chapter, url=url, id=id)


@app.get("/{path:path}")
async def spa_fallback(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    candidate = APP_DIR / path
    if candidate.is_file() and candidate.resolve().is_relative_to(APP_DIR.resolve()):
        return FileResponse(candidate)
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html; charset=utf-8")
    raise HTTPException(404, "Not found")


handler = Mangum(app)
