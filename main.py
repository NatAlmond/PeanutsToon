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
SHINIGAMI_API = (os.environ.get("SHINIGAMI_API_BASE", "") or "https://api.shngm.io").rstrip("/")
SHINIGAMI_APP = os.environ.get("SHINIGAMI_APP", "https://app.shinigami.asia").rstrip("/")
TIMEOUT = float(os.environ.get("PT_TIMEOUT", "15"))

app = FastAPI(title="PeanutsToon", version="1.3.0")
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



# ---- Shinigami (api.shngm.io — sama pola Nat-Multi-Tools3) ----
def _shini_headers():
    return {
        "Accept": "application/json",
        "Origin": SHINIGAMI_APP,
        "Referer": SHINIGAMI_APP + "/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }


async def _shini_json(path: str, params: Optional[dict] = None) -> Any:
    url = f"{SHINIGAMI_API}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, headers=_shini_headers()) as c:
            r = await c.get(url, params=params or {})
    except httpx.TimeoutException:
        raise HTTPException(504, "Timeout Shinigami")
    except Exception as e:
        raise HTTPException(502, f"Shinigami: {type(e).__name__}")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"Shinigami HTTP {r.status_code}")
    try:
        return r.json()
    except Exception:
        raise HTTPException(502, "Shinigami JSON invalid")


def _shini_cover(row: dict) -> str:
    return (
        row.get("cover_portrait_url")
        or row.get("cover_image_url")
        or row.get("thumbnail")
        or row.get("cover")
        or ""
    )


async def shinigami_latest(page=1):
    body = await _shini_json("/v1/manga/list", {"page": page, "page_size": 30, "sort": "popularity"})
    rows = body.get("data") if isinstance(body.get("data"), list) else []
    out = []
    for it in rows:
        if not isinstance(it, dict):
            continue
        sid = str(it.get("manga_id") or it.get("id") or "")
        if not sid:
            continue
        out.append(_item(it.get("title") or sid, sid, _shini_cover(it), "MANHWA", "shinigami"))
    return out


async def shinigami_search(q):
    body = await _shini_json("/v1/manga/list", {"page": 1, "page_size": 30, "q": q})
    rows = body.get("data") if isinstance(body.get("data"), list) else []
    out = []
    for it in rows:
        if not isinstance(it, dict):
            continue
        sid = str(it.get("manga_id") or it.get("id") or "")
        if not sid:
            continue
        out.append(_item(it.get("title") or sid, sid, _shini_cover(it), "MANHWA", "shinigami"))
    return out


async def shinigami_detail(slug):
    body = await _shini_json(f"/v1/manga/detail/{slug}")
    d = body.get("data") if isinstance(body.get("data"), dict) else {}
    genres = []
    tax = d.get("taxonomy") or {}
    for g in (tax.get("Genre") or [])[:12]:
        if isinstance(g, dict):
            genres.append(str(g.get("name") or ""))
        elif g:
            genres.append(str(g))
    chapters = []
    page = 1
    while page <= 50:
        cb = await _shini_json(f"/v1/chapter/{slug}/list", {"page": page, "page_size": 100})
        rows = cb.get("data") if isinstance(cb.get("data"), list) else []
        if not rows:
            break
        for ch in rows:
            if not isinstance(ch, dict):
                continue
            cid = str(ch.get("chapter_id") or ch.get("id") or "")
            num = ch.get("chapter_number")
            title = ch.get("chapter_title") or (f"Chapter {num}" if num is not None else cid)
            chapters.append({
                "judul": title,
                "slug": cid,
                "number": str(num) if num is not None else "",
                "id": cid,
                "url": "",
            })
        if len(rows) < 100:
            break
        page += 1
    return {
        "status": True,
        "source": "shinigami",
        "data": {
            "judul": d.get("title") or slug,
            "slug": str(d.get("manga_id") or d.get("id") or slug),
            "thumbnail": _shini_cover(d),
            "sinopsis": d.get("description") or "",
            "genre": genres,
            "status": d.get("status") or "",
            "type": "MANHWA",
            "chapters": chapters,
            "source": "shinigami",
        },
    }


async def shinigami_chapter(slug="", chapter="", url="", id=""):
    cid = (chapter or id or "").strip().split("/")[-1]
    if not cid:
        raise HTTPException(400, "chapter id dibutuhkan")
    body = await _shini_json(f"/v1/chapter/detail/{cid}")
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    base = (data.get("base_url") or data.get("base_url_low") or "https://assets.shngm.id").rstrip("/")
    chapter_obj = data.get("chapter") if isinstance(data.get("chapter"), dict) else {}
    path = chapter_obj.get("path") or data.get("path") or ""
    if path and not str(path).startswith("/"):
        path = "/" + str(path)
    if path and not str(path).endswith("/"):
        path = str(path) + "/"
    pages = chapter_obj.get("data") or data.get("pages") or []
    images = []
    if isinstance(pages, list):
        for p in pages:
            if isinstance(p, str):
                if p.startswith("http"):
                    images.append(p)
                else:
                    images.append(f"{base}{path}{p}")
            elif isinstance(p, dict):
                u = p.get("url") or p.get("src") or ""
                if u:
                    images.append(u if u.startswith("http") else f"{base}{path}{u}")
    return {"status": True, "source": "shinigami", "images": images}


# ---- Routes ----

@app.get("/favicon.png")
@app.get("/logo.png")
@app.get("/favicon.ico")
async def favicon():
    for name in ("favicon.png", "logo.png", "favicon.ico"):
        p = APP_DIR / name
        if p.exists():
            media = "image/png" if name.endswith(".png") else "image/x-icon"
            return FileResponse(p, media_type=media)
    raise HTTPException(404, "icon not found")

@app.get("/proxy-img")
async def proxy_img(url: str = ""):
    url = (url or "").strip()
    if not url.startswith("http"):
        raise HTTPException(400, "url invalid")
    allow = ("ikiru", "ainzscans", "shngm", "gmbr.pro", "manhwaindo", "wp.com", "googleusercontent", "voratoon")
    if not any(a in url.lower() for a in allow):
        raise HTTPException(403, "host not allowed")
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": SHINIGAMI_APP + "/",
            "Accept": "image/*,*/*;q=0.8",
        }) as c:
            r = await c.get(url)
            if r.status_code != 200 or not r.content:
                raise HTTPException(404, "img fail")
            ctype = r.headers.get("content-type") or "image/jpeg"
            from fastapi.responses import Response
            return Response(content=r.content, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, type(e).__name__)


@app.get("/")
async def home():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html; charset=utf-8")
    return HTMLResponse("<h1>PeanutsToon</h1>")


@app.get("/health")
async def health():
    sources = ["ikiru", "ainzscans", "manhwaindo", "shinigami"]
    return {
        "status": "online",
        "app": "PeanutsToon",
        "version": "1.3.0",
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
    if source in ("all", "shinigami"):
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
    if source in ("all", "shinigami"):
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
