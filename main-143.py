"""
PeanutsToon v1.5.21 — multi-source via API only (no scrape fallback)
Sources: Ikiru · AinzScans · ManhwaIndo · Shinigami (opsional env)
By: Nat
"""
from __future__ import annotations

import os
import json
import re
import asyncio
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urljoin

import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from mangum import Mangum

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

APP_DIR = Path(__file__).resolve().parent
INDEX_HTML = APP_DIR / "index.html"

IKIRU_API = os.environ.get("IKIRU_API_BASE", "https://ikiru-api-by-nat.vercel.app").rstrip("/")
AINZ_API = os.environ.get("AINZ_API_BASE", "https://ainz-scans-api-by-nat2.vercel.app").rstrip("/")
MANHWAINDO_API = os.environ.get("MANHWAINDO_API_BASE", "https://manhwa-indo-api-by-nat.vercel.app").rstrip("/")
SHINIGAMI_API = (os.environ.get("SHINIGAMI_API_BASE", "") or "https://api.shngm.io").rstrip("/")
SHINIGAMI_APP = os.environ.get("SHINIGAMI_APP", "https://app.shinigami.asia").rstrip("/")
VORATOON_API = os.environ.get(
    "VORATOON_API_BASE",
    os.environ.get("VORATOON_API", "https://voratoon-api-by-nat.vercel.app"),
).rstrip("/")
KIRYUU_API = os.environ.get("KIRYUU_API_BASE", "https://kiryuu-api-by-nat.vercel.app").rstrip("/")
WURMZ_API = os.environ.get("WURMZ_API_BASE", "https://wurmz-api-by-nat.vercel.app").rstrip("/")
TIMEOUT = float(os.environ.get("PT_TIMEOUT", "22"))

app = FastAPI(title="PeanutsToon", version="1.5.21")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

JSON_HEADERS = {"User-Agent": "PeanutsToon/1.2 (Nat)", "Accept": "application/json"}


def _clean_title(title: str, slug: str = "") -> str:
    """Buang angka view/like/#chapter sampah dari judul HTML."""
    t = re.sub(r"\s+", " ", (title or "").strip())
    # pola: 3.4K 218.3K #371 Judul Asli
    t = re.sub(r"(?:\d+(?:[.,]\d+)?[KkMmBb]\s*)+", "", t)
    t = re.sub(r"#\d+\s*", "", t)
    t = re.sub(r"(?:\d+(?:[.,]\d+)?\s+){2,}", "", t)
    t = re.sub(r"(?i)^(manga|manhwa|manhua|comic|komik)\s+", "", t)
    t = re.sub(r"\s+", " ", t).strip(" -|·")
    if len(t) < 3:
        t = re.sub(r"[-_]+", " ", (slug or "")).strip().title()
    return t[:110]


def _https(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://"):]
    return u


def _item(judul, slug, thumb, type_, source, **extra):
    slug = (slug or "").strip()
    return {
        "judul": _clean_title(judul or "", slug) or slug,
        "slug": slug,
        "thumbnail": _https(thumb or ""),
        "type": (type_ or "").upper() or "COMIC",
        "source": source,
        **extra,
    }


async def _json_soft(url: str, params: Optional[dict] = None) -> Any:
    """GET JSON tanpa raise — untuk list source agar satu API mati tidak bawa turun semua."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
            r = await c.get(url, params=params or {}, headers=JSON_HEADERS)
        if r.status_code >= 400:
            return {}
        try:
            return r.json()
        except Exception:
            return {}
    except Exception:
        return {}


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


async def _safe(coro, timeout: float = 14.0):
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
        _item(it.get("judul"), it.get("slug"), it.get("thumbnail") or it.get("sampul") or it.get("cover") or it.get("image"), it.get("type") or "MANGA", "ainzscans")
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
    data = await _json(f"{AINZ_API}/api/chapter", params)
    images = data.get("images") or data.get("gambar") or data.get("pages") or []
    if isinstance(data.get("data"), list):
        images = data["data"] or images
    clean = []
    for u in images or []:
        if not isinstance(u, str):
            continue
        u = _https(u)
        low = u.lower()
        if any(x in low for x in ("logo", "banner", "avatar", "histats", "/0.gif", "emoji")):
            continue
        if u not in clean:
            clean.append(u)
    data = dict(data) if isinstance(data, dict) else {}
    data["status"] = True
    data["source"] = "ainzscans"
    data["images"] = clean
    return data


# ---- ManhwaIndo ----
async def manhwaindo_latest(page=1):
    data = await _json(f"{MANHWAINDO_API}/api/latest", {"page": page})
    out = []
    for it in (data.get("data") or []):
        if not isinstance(it, dict) or not it.get("slug"):
            continue
        th = it.get("thumbnail") or it.get("sampul") or ""
        if isinstance(th, str) and th.startswith("http://"):
            th = "https://" + th[7:]
        out.append(_item(it.get("judul"), it.get("slug"), th, "MANHWA", "manhwaindo"))
    return out


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
    # buang sampul/thumbnail & tracking
    clean = []
    for u in images or []:
        if not isinstance(u, str):
            continue
        low = u.lower()
        if "thumbnail" in low or "assets.shngm.id/thumbnail" in low:
            continue
        if "histats" in low or "/0.gif" in low:
            continue
        if "manga-images" in low or "imgx" in low or low.endswith((".jpg", ".jpeg", ".png", ".webp", ".avif")):
            clean.append(u)
        elif u.startswith("http") and "manga" in low:
            clean.append(u)
    if len(clean) >= 2:
        images = clean
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




# ---- Voratoon (API by Nat — voratoon.web.id) ----
async def voratoon_latest(page=1):
    data = await _json(f"{VORATOON_API}/api/latest", {"page": page})
    return [
        _item(
            it.get("judul") or it.get("title"),
            it.get("slug"),
            it.get("thumbnail") or it.get("sampul"),
            it.get("type") or "MANHWA",
            "voratoon",
        )
        for it in (data.get("data") or [])
        if isinstance(it, dict) and it.get("slug")
    ]


async def voratoon_search(q):
    data = await _json(f"{VORATOON_API}/api/search", {"q": q})
    return [
        _item(
            it.get("judul") or it.get("title"),
            it.get("slug"),
            it.get("thumbnail") or it.get("sampul"),
            it.get("type") or "MANHWA",
            "voratoon",
        )
        for it in (data.get("data") or [])
        if isinstance(it, dict) and it.get("slug")
    ]


async def voratoon_detail(slug):
    data = await _json(f"{VORATOON_API}/api/detail/{slug}")
    d = data.get("data") or data
    chapters = []
    for c in d.get("chapters") or []:
        if not isinstance(c, dict):
            continue
        chapters.append({
            "judul": c.get("judul") or c.get("title") or "",
            "slug": c.get("slug") or "",
            "number": c.get("number") or "",
            "id": c.get("id") or c.get("slug") or "",
            "url": c.get("url") or "",
        })
    return {
        "judul": d.get("judul") or d.get("title") or slug,
        "slug": d.get("slug") or slug,
        "thumbnail": d.get("thumbnail") or d.get("sampul") or "",
        "sinopsis": d.get("sinopsis") or d.get("synopsis") or "",
        "type": d.get("type") or "MANHWA",
        "status": d.get("status") or "",
        "genres": d.get("genres") or d.get("genre") or [],
        "chapters": chapters,
        "source": "voratoon",
    }


async def voratoon_chapter(slug, chapter="", url="", id_=""):
    params = {"slug": slug}
    if chapter:
        params["chapter"] = chapter
    if url:
        params["url"] = url
    data = await _json(f"{VORATOON_API}/api/chapter", params)
    images = data.get("images") or data.get("gambar") or []
    return [u for u in images if isinstance(u, str) and u.startswith("http")]


async def kiryuu_latest(page=1):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
            r = await c.get(f"{KIRYUU_API}/api/latest", params={"page": page})
        if r.status_code >= 400:
            return []
        body = r.json() or {}
        rows = body.get("data") if isinstance(body.get("data"), list) else []
        out = []
        for it in rows:
            if not isinstance(it, dict):
                continue
            slug = str(it.get("slug") or "")
            if not slug:
                continue
            out.append(_item(
                it.get("judul") or it.get("title") or slug,
                slug,
                it.get("thumbnail") or it.get("sampul") or "",
                it.get("type") or "MANGA",
                "kiryuu",
            ))
        return out
    except Exception:
        return []


async def kiryuu_search(q):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
            r = await c.get(f"{KIRYUU_API}/api/search", params={"q": q})
        if r.status_code >= 400:
            return []
        body = r.json() or {}
        rows = body.get("data") if isinstance(body.get("data"), list) else []
        out = []
        for it in rows:
            if not isinstance(it, dict):
                continue
            slug = str(it.get("slug") or "")
            if not slug:
                continue
            out.append(_item(
                it.get("judul") or it.get("title") or slug,
                slug,
                it.get("thumbnail") or it.get("sampul") or "",
                it.get("type") or "MANGA",
                "kiryuu",
            ))
        return out
    except Exception:
        return []


async def kiryuu_detail(slug):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
            r = await c.get(f"{KIRYUU_API}/api/detail/{slug}")
        if r.status_code == 404:
            raise HTTPException(404, "Manga not found")
        if r.status_code >= 400:
            raise HTTPException(502, f"Kiryuu detail HTTP {r.status_code}")
        body = r.json() or {}
        d = body.get("data") if isinstance(body.get("data"), dict) else body
        chapters = []
        for ch in (d.get("chapters") or []):
            if not isinstance(ch, dict):
                continue
            chapters.append({
                "judul": ch.get("judul") or ch.get("title") or "",
                "slug": ch.get("slug") or ch.get("id") or "",
                "number": str(ch.get("number") or ""),
                "id": ch.get("id") or ch.get("slug") or "",
                "url": ch.get("url") or "",
            })
        return {
            "status": True,
            "source": "kiryuu",
            "data": {
                "judul": d.get("judul") or d.get("title") or slug,
                "slug": d.get("slug") or slug,
                "thumbnail": _https(d.get("thumbnail") or d.get("sampul") or ""),
                "sinopsis": d.get("sinopsis") or d.get("synopsis") or "",
                "genre": d.get("genre") or d.get("genres") or [],
                "status": d.get("status") or "",
                "type": d.get("type") or "MANGA",
                "chapters": chapters,
                "source": "kiryuu",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Kiryuu detail: {type(e).__name__}")


async def kiryuu_chapter(slug="", chapter="", url="", id=""):
    params = {}
    if url:
        params["url"] = url
    if slug:
        params["slug"] = slug
    if chapter:
        params["chapter"] = chapter
    if id:
        params["id"] = id
    if not params:
        raise HTTPException(400, "url/chapter dibutuhkan")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
            r = await c.get(f"{KIRYUU_API}/api/chapter", params=params)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f"Kiryuu chapter HTTP {r.status_code}")
        body = r.json() or {}
        images = body.get("images") or body.get("gambar") or []
        if not isinstance(images, list):
            images = []
        return {"status": True, "source": "kiryuu", "images": images}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Kiryuu chapter: {type(e).__name__}")

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
    # http → https (banyak CDN gmbr)
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    allow = (
        "ikiru", "ainzscans", "ainzscans01", "shngm", "gmbr.pro", "manhwaindo",
        "wp.com", "googleusercontent", "voratoon", "cloudfront", "amazonaws",
        "kiryuu", "cdn.ikiru",
    )
    if not any(a in url.lower() for a in allow):
        raise HTTPException(403, "host not allowed")
    # Referer menyesuaikan host (gmbr sering butuh voratoon/manhwa)
    ref = "https://voratoon.web.id/"
    low = url.lower()
    if "shngm" in low:
        ref = SHINIGAMI_APP.rstrip("/") + "/"
    elif "ainz" in low:
        ref = "https://ainzscans.site/"
    elif "ikiru" in low:
        ref = "https://ikiru.wtf/"
    elif "kiryuu" in low:
        ref = "https://v7.kiryuu.to/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        "Referer": ref,
        "Origin": ref.rstrip("/"),
    }
    try:
        async with httpx.AsyncClient(timeout=22.0, follow_redirects=True) as c:
            r = await c.get(url, headers=headers)
            if r.status_code != 200 or not r.content:
                # coba referer alternatif
                for ref2 in ("https://voratoon.web.id/", "https://www.google.com/", "https://manhwaindo.one/"):
                    if ref2 == ref:
                        continue
                    headers["Referer"] = ref2
                    headers["Origin"] = ref2.rstrip("/")
                    r = await c.get(url, headers=headers)
                    if r.status_code == 200 and r.content:
                        break
            if r.status_code != 200 or not r.content:
                raise HTTPException(404, "img fail")
            ctype = r.headers.get("content-type") or "image/jpeg"
            if "text/html" in ctype:
                raise HTTPException(404, "img blocked")
            from fastapi.responses import Response
            return Response(
                content=r.content,
                media_type=ctype.split(";")[0].strip(),
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "img fail")



@app.get("/")
async def home():
    content = _read_index_html()
    if content:
        return HTMLResponse(content, media_type="text/html; charset=utf-8")
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><title>PeanutsToon</title>"
        "<body style='font-family:system-ui;background:#12100e;color:#f5efe6;padding:24px'>"
        "<h1>PeanutsToon</h1>"
        "<p>index.html tidak ditemukan di deploy.</p>"
        "<p>Pastikan <b>index.html</b> ada di <b>root repo</b> GitHub (sejajar main.py), lalu Redeploy.</p>"
        "</body>"
    )


@app.get("/app")
@app.get("/home")
async def home_alias():
    return await home()


@app.get("/health")
async def health():
    sources = ["ikiru", "ainzscans", "manhwaindo", "shinigami", "voratoon", "kiryuu", "wurmz"]
    return {
        "status": "online",
        "app": "PeanutsToon",
        "version": "1.5.21",
        "sources": sources,
        "ikiru_api": IKIRU_API,
        "ainz_api": AINZ_API,
        "manhwaindo_api": MANHWAINDO_API,
        "shinigami_api": SHINIGAMI_API,
        "voratoon_api": VORATOON_API,
        "kiryuu_api": KIRYUU_API,
        "wurmz_api": WURMZ_API or None,
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
    sources.append({"id": "voratoon", "name": "Voratoon"})
    sources.append({"id": "kiryuu", "name": "Kiryuu"})
    return {"sources": sources}


# ---- Wurmz (API by Nat) ----
def _wurmz_type_slug(it):
    """id sering 'manhwa/slug' — pecah type+slug."""
    typ = str(it.get("type") or "").lower().strip()
    slug = str(it.get("slug") or "").strip()
    _id = str(it.get("id") or "").strip()
    if "/" in _id and not typ:
        parts = _id.split("/", 1)
        typ, slug = parts[0], parts[1] if len(parts) > 1 else slug
    if "/" in slug:
        parts = slug.split("/", 1)
        typ = typ or parts[0]
        slug = parts[-1]
    if typ not in ("manga", "manhwa", "manhua"):
        typ = typ if typ else "manhwa"
    return typ, slug


async def wurmz_latest(page=1):
    # API tidak pakai page di /latest — gabung latest + list
    out, seen = [], set()
    paths = ["/latest", "/list?sort=new", "/popular?range=7d"]
    if page and int(page) > 1:
        paths = ["/list?sort=new", "/popular?range=all"]
    for path in paths:
        data = await _json_soft(f"{WURMZ_API}{path}")
        rows = data.get("data") or data.get("results") or data.get("items") or []
        if not isinstance(rows, list):
            continue
        for it in rows:
            if not isinstance(it, dict):
                continue
            typ, slug = _wurmz_type_slug(it)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            title = it.get("title") or it.get("judul") or slug
            thumb = it.get("cover") or it.get("thumbnail") or it.get("sampul") or ""
            item = _item(title, slug, thumb, typ.upper() if typ else "COMIC", "wurmz")
            item["comic_type"] = typ  # simpan untuk detail/chapter
            out.append(item)
    return out


async def wurmz_search(q):
    data = await _json_soft(f"{WURMZ_API}/search", {"q": q})
    rows = data.get("data") or data.get("results") or []
    out, seen = [], set()
    for it in rows if isinstance(rows, list) else []:
        if not isinstance(it, dict):
            continue
        typ, slug = _wurmz_type_slug(it)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        title = it.get("title") or it.get("judul") or slug
        thumb = it.get("cover") or it.get("thumbnail") or ""
        item = _item(title, slug, thumb, typ.upper() if typ else "COMIC", "wurmz")
        item["comic_type"] = typ
        out.append(item)
    return out


async def wurmz_detail(slug, comic_type=""):
    # coba type yang mungkin
    types = []
    if comic_type:
        types.append(comic_type)
    types += ["manhwa", "manga", "manhua"]
    d = {}
    used_type = ""
    for typ in types:
        data = await _json(f"{WURMZ_API}/series/{typ}/{slug}")
        if not isinstance(data, dict):
            continue
        # success if title/chapters present
        if data.get("title") or data.get("chapters") or data.get("ok"):
            d = data
            used_type = typ
            break
    chapters = []
    for ch in d.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        num = str(ch.get("number") or ch.get("num") or "")
        chapters.append({
            "judul": ch.get("title") or f"Chapter {num}",
            "slug": num or str(ch.get("slug") or ""),
            "number": num,
            "url": ch.get("url") or "",
            "api": ch.get("api") or "",
        })
    return {
        "status": True,
        "source": "wurmz",
        "data": {
            "judul": d.get("title") or d.get("judul") or slug,
            "slug": d.get("slug") or slug,
            "thumbnail": _https(d.get("cover") or d.get("thumbnail") or ""),
            "sinopsis": d.get("synopsis") or d.get("sinopsis") or "",
            "status": d.get("status") or "",
            "type": (used_type or d.get("type") or "").upper(),
            "comic_type": used_type or d.get("type") or "manhwa",
            "genres": d.get("genres") or [],
            "chapters": chapters,
            "source": "wurmz",
        },
    }


async def wurmz_chapter(slug="", chapter="", url="", id="", comic_type=""):
    ch = str(chapter or id or "").strip().strip("/")
    types = []
    if comic_type:
        types.append(comic_type)
    types += ["manhwa", "manga", "manhua"]
    images = []
    meta = {}
    for typ in types:
        data = await _json(f"{WURMZ_API}/chapter/{typ}/{slug}/{ch}")
        if not isinstance(data, dict):
            continue
        imgs = data.get("images") or data.get("gambar") or []
        if imgs:
            images = [_https(u) for u in imgs if isinstance(u, str) and u.startswith("http")]
            meta = data
            break
    return {
        "status": True,
        "source": "wurmz",
        "slug": slug,
        "chapter": ch,
        "images": images,
        "total": len(images),
        "title": meta.get("title") or "",
    }


@app.get("/api/latest")
async def api_latest(page: int = Query(1, ge=1), source: str = Query("all")):
    source = (source or "all").lower()
    tasks = []
    # page kedua hanya untuk source tunggal → lebih banyak kartu tanpa lag "Semua"
    extra = (source != "all" and page == 1)

    def add_src(name, fn):
        if source in ("all", name):
            tasks.append(_safe(fn(page)))
            if extra:
                tasks.append(_safe(fn(page + 1)))

    add_src("ikiru", ikiru_latest)
    add_src("ainzscans", ainz_latest)
    add_src("manhwaindo", manhwaindo_latest)
    add_src("shinigami", shinigami_latest)
    add_src("voratoon", voratoon_latest)
    add_src("kiryuu", kiryuu_latest)
    add_src("wurmz", wurmz_latest)
    parts = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
    items = []
    for part in parts:
        if isinstance(part, Exception) or not isinstance(part, list):
            continue
        items += part
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
    if source in ("all", "voratoon"):
        tasks.append(_safe(voratoon_search(q)))
    if source in ("all", "kiryuu"):
        tasks.append(_safe(kiryuu_search(q)))
    if source in ("all", "wurmz"):
        tasks.append(_safe(wurmz_search(q)))
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
    if source == "voratoon":
        return await voratoon_detail(slug)
    if source == "kiryuu":
        return await kiryuu_detail(slug)
    if source == "wurmz":
        return await wurmz_detail(slug)
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
    if source == "voratoon":
        return await voratoon_chapter(slug=slug, chapter=ch, url=url, id=id or ch)
    if source == "kiryuu":
        return await kiryuu_chapter(slug=slug, chapter=ch, url=url, id=id or ch)
    if source == "wurmz":
        return await wurmz_chapter(slug=slug, chapter=ch, url=url, id=id or ch)
    return await ikiru_chapter(slug=slug, chapter=chapter, url=url, id=id)




@app.get("/api/img")
async def proxy_img(url: str = Query("", min_length=8)):
    """Proxy gambar agar lolos hotlink (Kiryuu/Voratoon)."""
    from fastapi.responses import Response
    if not url.startswith("http"):
        raise HTTPException(400, "url invalid")
    # hanya host yang diizinkan
    allow = (
        "kiryuu.to", "cdn.kiryuu", "voratoon.", "cvr.voratoon", "cdn.voratoon", "cdn.ikiru",
        "ainzscans", "api.ainzscans", "gmbr.pro", "imgx", "shngm", "assets.shngm",
        "wurmz.net", "cdn.wurmz", "cdn7.wurmz",
    )
    if not any(a in url for a in allow):
        raise HTTPException(403, "host tidak diizinkan")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    if "kiryuu" in url:
        headers["Referer"] = "https://v7.kiryuu.to/"
    elif "voratoon" in url or "cvr.voratoon" in url:
        headers["Referer"] = "https://v10.voratoon.com/"
        headers["Origin"] = "https://v10.voratoon.com"
    elif "ainz" in url:
        headers["Referer"] = "https://v3.ainzscans01.com/"
        headers["Origin"] = "https://v3.ainzscans01.com"
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as c:
            r = await c.get(url, headers=headers)
        if r.status_code >= 400 or not r.content:
            raise HTTPException(r.status_code or 502, "gagal ambil gambar")
        ctype = r.headers.get("content-type") or "image/jpeg"
        if not ctype.startswith("image"):
            ctype = "image/jpeg"
        return Response(content=r.content, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, str(e))



@app.get("/api/config")
async def public_config():
    """Konfig publik untuk frontend (Turnstile site key, dll)."""
    return {
        "status": True,
        "turnstile_site_key": os.environ.get("CF_TURNSTILE_SITE_KEY", "").strip(),
        "turnstile_enabled": bool(os.environ.get("CF_TURNSTILE_SITE_KEY", "").strip()),
        "auth_mode": "local",  # akun disimpan di perangkat; cloud auth nanti
        "version": "1.5.21",
    }


@app.post("/api/auth/turnstile")
async def verify_turnstile(request: Request):
    """Verifikasi token Cloudflare Turnstile (opsional jika secret diset)."""
    secret = os.environ.get("CF_TURNSTILE_SECRET_KEY", "").strip()
    site = os.environ.get("CF_TURNSTILE_SITE_KEY", "").strip()
    if not secret or not site:
        return {"status": True, "skipped": True, "message": "Turnstile belum dikonfigurasi di server"}
    try:
        body = await request.json()
    except Exception:
        body = {}
    token = (body.get("token") or body.get("cf-turnstile-response") or "").strip()
    if not token:
        raise HTTPException(400, "Token Turnstile kosong")
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret, "response": token},
            )
        data = r.json() if r.status_code == 200 else {}
        if not data.get("success"):
            raise HTTPException(403, "Verifikasi Cloudflare gagal")
        return {"status": True, "success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Turnstile error: {e}")




# ---------- Auth + weekly leaderboard (server) ----------
import hashlib
import hmac
import time
from datetime import datetime, timezone

_AUTH_SECRET = (os.environ.get("AUTH_SECRET") or os.environ.get("CF_TURNSTILE_SECRET_KEY") or "peanutstoon-dev-secret").encode()
_USERS: dict = {}
_READ_WEEK: dict = {}  # week_key -> {email: {seconds, name, avatar}}
_DATA_FILE = Path("/tmp/peanutstoon_store.json")
_FEEDBACK: list = []


def _week_key(ts=None):
    dt = datetime.fromtimestamp(ts or time.time(), tz=timezone.utc)
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_store():
    global _USERS, _READ_WEEK, _FEEDBACK
    try:
        if _DATA_FILE.exists():
            raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
            _USERS = raw.get("users") or {}
            _READ_WEEK = raw.get("read_week") or {}
            _FEEDBACK = raw.get("feedback") or []
    except Exception:
        pass



def _save_store():
    try:
        _DATA_FILE.write_text(
            json.dumps({"users": _USERS, "read_week": _READ_WEEK, "feedback": _FEEDBACK}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

def _admin_emails():
    raw = (os.environ.get("ADMIN_EMAILS") or "").strip()
    if raw:
        return {e.strip().lower() for e in raw.split(",") if e.strip()}
    return {
        "skibidialmond@gmail.com",
        "ohkangwookimchijigae@gmail.com",
        "momonggasamaorewamaoudenaru@gmail.com",
    }

def _is_admin(email: str) -> bool:
    return (email or "").strip().lower() in _admin_emails()



_load_store()


def _hash_pass(email: str, password: str) -> str:
    return hashlib.sha256(f"{email.lower().strip()}:{password}".encode()).hexdigest()


def _token_for(email: str) -> str:
    email = email.lower().strip()
    sig = hmac.new(_AUTH_SECRET, email.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{email}.{sig}"


def _verify_token(token: str) -> str:
    token = (token or "").strip()
    if "." not in token:
        raise HTTPException(401, "Token invalid")
    email, sig = token.rsplit(".", 1)
    expect = hmac.new(_AUTH_SECRET, email.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expect):
        raise HTTPException(401, "Token invalid")
    _load_store()
    if email not in _USERS:
        if email in _admin_emails():
            _USERS[email] = {
                "email": email,
                "name": email.split("@")[0] or "Admin",
                "pass": "",
                "created": int(time.time()),
                "last_active": int(time.time()),
                "is_admin": True,
            }
            _save_store()
        else:
            raise HTTPException(401, "Akun tidak ditemukan di server (store reset). Silakan login ulang.")
    else:
        _USERS[email]["last_active"] = int(time.time())
        if email in _admin_emails():
            _USERS[email]["is_admin"] = True
    return email


async def _require_turnstile(token: str):
    secret = os.environ.get("CF_TURNSTILE_SECRET_KEY", "").strip()
    if not secret:
        # jika secret belum dipasang, izinkan (dev) tapi production sebaiknya dipasang
        return True
    token = (token or "").strip()
    if not token:
        raise HTTPException(400, "Centang verifikasi Cloudflare terlebih dahulu")
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret, "response": token},
            )
        data = r.json() if r.status_code == 200 else {}
        if not data.get("success"):
            raise HTTPException(403, "Verifikasi Cloudflare gagal")
        return True
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Turnstile error: {e}")


@app.post("/api/auth/register")
async def auth_register(request: Request):
    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    name = str(body.get("name") or "").strip() or (email.split("@")[0] if email else "User")
    cf = str(body.get("token") or body.get("cf_token") or "")
    if not email or "@" not in email:
        raise HTTPException(400, "Email tidak valid")
    if len(password) < 6:
        raise HTTPException(400, "Password minimal 6 karakter")
    await _require_turnstile(cf)
    _load_store()
    if email in _USERS:
        # jika password sama → anggap login ulang (bukan error)
        if _USERS[email].get("pass_hash") == _hash_pass(email, password):
            u = _USERS[email]
            u["is_admin"] = _is_admin(email)
            if name and name != email.split("@")[0]:
                u["name"] = name[:32]
            _USERS[email] = u
            _save_store()
            return {
                "status": True,
                "token": _token_for(email),
                "user": {
                    "email": email,
                    "name": u.get("name") or name,
                    "avatar": u.get("avatar") or "",
                    "is_admin": _is_admin(email),
                },
                "message": "Sudah terdaftar — langsung masuk",
            }
        raise HTTPException(409, "Email sudah terdaftar. Gunakan password lama untuk masuk, atau buka Lupa Sandi untuk ganti password.")
    _USERS[email] = {
        "email": email,
        "pass_hash": _hash_pass(email, password),
        "name": name[:32],
        "avatar": "",
        "created": int(time.time()),
        "last_active": int(time.time()),
        "is_admin": _is_admin(email),
    }
    _save_store()
    return {
        "status": True,
        "token": _token_for(email),
        "user": {"email": email, "name": name, "avatar": "", "is_admin": _is_admin(email)},
    }


@app.post("/api/auth/login")
async def auth_login(request: Request):
    """Login — Turnstile TIDAK wajib (hanya daftar yang wajib).
    Logout hanya menghapus sesi; email+password tetap valid.
    """
    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    if not email or "@" not in email:
        raise HTTPException(400, "Email tidak valid")
    if len(password) < 6:
        raise HTTPException(400, "Password minimal 6 karakter")
    _load_store()
    user = _USERS.get(email)
    if not user:
        # /tmp Vercel sering kosong setelah cold start
        raise HTTPException(
            401,
            "Akun tidak ditemukan di server. Jika baru deploy/cold start, daftar ulang dengan email & password yang sama.",
        )
    if user.get("pass_hash") != _hash_pass(email, password):
        raise HTTPException(401, "Password salah. Gunakan password saat daftar pertama kali (logout tidak mengganti password). Atau pakai Lupa Sandi.")
    # pastikan flag admin selalu sync
    user["is_admin"] = _is_admin(email)
    user["last_active"] = int(time.time())
    _USERS[email] = user
    _save_store()
    return {
        "status": True,
        "token": _token_for(email),
        "user": {
            "email": email,
            "name": user.get("name") or email.split("@")[0],
            "avatar": user.get("avatar") or "",
            "is_admin": _is_admin(email),
        },
    }



@app.post("/api/auth/reset-password")
async def auth_reset_password(request: Request):
    """Lupa sandi — ganti password akun yang sudah ada.
    Wajib Turnstile (seperti Nexora recovery + captcha).
    Tidak kirim email (serverless); verifikasi manusia + email terdaftar.
    """
    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    password2 = str(body.get("password2") or body.get("confirm") or "")
    cf = str(body.get("token") or body.get("cf_token") or "")
    if not email or "@" not in email:
        raise HTTPException(400, "Email tidak valid")
    if len(password) < 6:
        raise HTTPException(400, "Password baru minimal 6 karakter")
    if password2 and password != password2:
        raise HTTPException(400, "Konfirmasi password tidak sama")
    await _require_turnstile(cf)
    _load_store()
    user = _USERS.get(email)
    if not user:
        raise HTTPException(
            404,
            "Email tidak terdaftar di server. Daftar akun baru, atau coba lagi setelah login sebelumnya (cold start).",
        )
    user["pass_hash"] = _hash_pass(email, password)
    user["last_active"] = int(time.time())
    user["is_admin"] = _is_admin(email)
    _USERS[email] = user
    _save_store()
    return {
        "status": True,
        "message": "Password diganti. Silakan masuk dengan password baru.",
        "token": _token_for(email),
        "user": {
            "email": email,
            "name": user.get("name") or email.split("@")[0],
            "avatar": user.get("avatar") or "",
            "is_admin": _is_admin(email),
        },
    }


@app.post("/api/auth/profile")
async def auth_profile(request: Request):
    body = await request.json()
    email = _verify_token(body.get("token") or "")
    _load_store()
    user = _USERS.get(email) or {}
    if "name" in body and str(body.get("name") or "").strip():
        user["name"] = str(body.get("name")).strip()[:32]
    if "avatar" in body and isinstance(body.get("avatar"), str):
        av = body.get("avatar") or ""
        if len(av) <= 900_000:  # ~0.9MB data URL
            user["avatar"] = av
    _USERS[email] = user
    _save_store()
    return {"status": True, "user": {"email": email, "name": user.get("name"), "avatar": user.get("avatar") or ""}}


@app.post("/api/reading/report")
async def reading_report(request: Request):
    """Lapor detik baca dengan anti-cheat ketat → leaderboard mingguan."""
    body = await request.json()
    email = _verify_token(body.get("token") or "")
    try:
        seconds = int(body.get("seconds") or 0)
    except Exception:
        seconds = 0
    if seconds < 5:
        return {"status": True, "added": 0, "reason": "too_short"}
    # max 90 detik per report (client flush ~30s; cegah inject besar)
    seconds = min(max(0, seconds), 90)
    now = int(time.time())
    _load_store()
    user = _USERS.get(email) or {}
    if not user:
        raise HTTPException(401, "Akun tidak ditemukan")

    # akun baru < 30 menit: belum boleh mengirim waktu baca (anti-spam daftar)
    created = int(user.get("created") or 0)
    if created and (now - created) < 30 * 60:
        return {
            "status": True,
            "added": 0,
            "reason": "new_account",
            "message": "Akun baru harus menunggu 30 menit sebelum waktu baca dihitung leaderboard",
        }

    wk = _week_key()
    bucket = _READ_WEEK.setdefault(wk, {})
    row = bucket.get(email) or {
        "seconds": 0,
        "name": user.get("name") or email.split("@")[0],
        "avatar": user.get("avatar") or "",
        "last_report": 0,
        "reports": 0,
        "day_map": {},
    }

    # rate limit: minimal 20 detik antar report
    last_r = int(row.get("last_report") or 0)
    if last_r and (now - last_r) < 20:
        return {"status": True, "added": 0, "reason": "rate_limit"}

    # max ~3 jam per hari kalender UTC (10800s)
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    day_map = row.get("day_map") if isinstance(row.get("day_map"), dict) else {}
    day_sec = int(day_map.get(day) or 0)
    room = max(0, 10800 - day_sec)
    if room <= 0:
        return {
            "status": True,
            "added": 0,
            "reason": "daily_cap",
            "message": "Batas baca harian untuk leaderboard (3 jam) tercapai",
            "total": int(row.get("seconds") or 0),
        }
    seconds = min(seconds, room)

    # max ~20 jam per minggu
    week_sec = int(row.get("seconds") or 0)
    if week_sec >= 72000:
        return {
            "status": True,
            "added": 0,
            "reason": "weekly_cap",
            "total": week_sec,
        }
    seconds = min(seconds, 72000 - week_sec)

    row["seconds"] = week_sec + seconds
    day_map[day] = day_sec + seconds
    # keep day_map kecil
    if len(day_map) > 10:
        for k in sorted(day_map.keys())[:-7]:
            day_map.pop(k, None)
    row["day_map"] = day_map
    row["last_report"] = now
    row["reports"] = int(row.get("reports") or 0) + 1
    row["name"] = user.get("name") or row.get("name") or email.split("@")[0]
    row["avatar"] = user.get("avatar") or row.get("avatar") or ""
    bucket[email] = row

    user["last_active"] = now
    _USERS[email] = user
    if len(_READ_WEEK) > 4:
        for k in sorted(_READ_WEEK.keys())[:-3]:
            _READ_WEEK.pop(k, None)
    _save_store()
    return {
        "status": True,
        "added": seconds,
        "week": wk,
        "total": row["seconds"],
        "qualified": row["seconds"] >= 300,
    }


@app.get("/api/leaderboard/weekly")
async def leaderboard_weekly():
    """Hanya akun yang memenuhi syarat ketat yang masuk ranking 1–100."""
    _load_store()
    wk = _week_key()
    bucket = _READ_WEEK.get(wk) or {}
    MIN_SECONDS = 300  # minimal 5 menit baca valid minggu ini
    rows = []
    for email, row in (bucket or {}).items():
        sec = int(row.get("seconds") or 0)
        if sec < MIN_SECONDS:
            continue
        user = _USERS.get(email) or {}
        name = (user.get("name") or row.get("name") or email.split("@")[0] or "Pembaca")[:32]
        avatar = user.get("avatar") or row.get("avatar") or ""
        rows.append({
            "email": email,
            "name": name,
            "avatar": avatar,
            "seconds": sec,
            "reports": int(row.get("reports") or 0),
        })
    # urut waktu baca terbanyak; tie-break: lebih sedikit report (kurang spam), lalu nama
    rows.sort(key=lambda x: (-x["seconds"], x.get("reports") or 0, x.get("name") or ""))
    out = []
    for i, r in enumerate(rows[:100], 1):
        em = r.pop("email", "")
        r.pop("reports", None)
        r["rank"] = i
        r["minutes"] = round(r["seconds"] / 60, 1)
        r["id"] = hashlib.sha256(em.encode()).hexdigest()[:10]
        out.append(r)
    return {
        "status": True,
        "week": wk,
        "resets": "Setiap Senin 00:00 UTC",
        "min_minutes": 5,
        "max_rank": 100,
        "rules": [
            "Harus login (akun terdaftar)",
            "Minimal 5 menit baca valid minggu ini",
            "Akun baru menunggu 30 menit sebelum waktu dihitung",
            "Maks 3 jam/hari dan 20 jam/minggu yang dihitung",
            "Laporan waktu dibatasi (anti-spam / anti-bypass)",
        ],
        "total_qualified": len(out),
        "total_readers": len(bucket),
        "data": out,
    }




@app.post("/api/feedback")
async def submit_feedback(request: Request):
    """Pengguna kirim saran — tersimpan di server."""
    body = await request.json()
    email = _verify_token(body.get("token") or "")
    msg = str(body.get("message") or body.get("saran") or "").strip()
    if len(msg) < 3:
        raise HTTPException(400, "Saran terlalu pendek")
    if len(msg) > 2000:
        raise HTTPException(400, "Saran terlalu panjang")
    _load_store()
    user = _USERS.get(email) or {}
    import time as _t
    uname = (user.get("name") or "").strip() or email.split("@")[0]
    # izinkan client kirim nama terbaru (opsional)
    client_name = str(body.get("name") or "").strip()
    if client_name:
        uname = client_name[:32]
        user["name"] = uname
        _USERS[email] = user
    ts = int(_t.time())
    from datetime import datetime, timezone
    created_iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    created_local_hint = ts  # client format ke waktu lokal
    _FEEDBACK.append({
        "id": hashlib.sha256(f"{email}:{ts}:{msg[:20]}".encode()).hexdigest()[:12],
        "email": email,
        "name": uname,
        "message": msg,
        "created": ts,
        "created_iso": created_iso,
        "read": False,
    })
    # keep last 200
    if len(_FEEDBACK) > 200:
        del _FEEDBACK[:-200]
    _save_store()
    return {"status": True, "message": "Saran terkirim"}



@app.get("/api/admin/users")
async def admin_list_users(token: str = Query(""), inactive_days: int = Query(7)):
    """Daftar pengguna + yang jarang aktif. Khusus admin."""
    email = _verify_token(token)
    if not _is_admin(email):
        raise HTTPException(403, "Khusus admin")
    _load_store()
    now = int(time.time())
    try:
        days = max(1, min(int(inactive_days or 7), 365))
    except Exception:
        days = 7
    cutoff = now - days * 86400
    rows = []
    for em, u in (_USERS or {}).items():
        la = int(u.get("last_active") or u.get("created") or 0)
        created = int(u.get("created") or 0)
        inactive = la < cutoff
        rows.append({
            "email": em,
            "name": u.get("name") or em.split("@")[0],
            "is_admin": _is_admin(em),
            "created": created,
            "last_active": la,
            "inactive": inactive,
            "days_idle": int((now - la) / 86400) if la else None,
        })
    rows.sort(key=lambda x: (not x["inactive"], x["last_active"] or 0))
    inactive_rows = [r for r in rows if r["inactive"] and not r["is_admin"]]
    return {
        "status": True,
        "total": len(rows),
        "inactive_days": days,
        "inactive_count": len(inactive_rows),
        "data": rows,
        "inactive": inactive_rows,
    }


@app.post("/api/admin/users/delete")
async def admin_delete_user(request: Request):
    """Hapus akun pengguna (bukan admin)."""
    body = await request.json()
    admin_email = _verify_token(body.get("token") or "")
    if not _is_admin(admin_email):
        raise HTTPException(403, "Khusus admin")
    target = str(body.get("email") or "").strip().lower()
    if not target or "@" not in target:
        raise HTTPException(400, "Email target tidak valid")
    if _is_admin(target):
        raise HTTPException(403, "Tidak bisa menghapus akun admin")
    if target == admin_email:
        raise HTTPException(400, "Tidak bisa menghapus akun sendiri")
    _load_store()
    if target not in _USERS:
        raise HTTPException(404, "Akun tidak ditemukan")
    _USERS.pop(target, None)
    # bersihkan leaderboard minggu ini
    for wk, bucket in list(_READ_WEEK.items()):
        if isinstance(bucket, dict):
            bucket.pop(target, None)
    _save_store()
    return {"status": True, "message": f"Akun {target} dihapus"}



@app.get("/api/admin/feedback")
async def admin_list_feedback(token: str = Query("")):
    email = _verify_token(token)
    if not _is_admin(email):
        raise HTTPException(403, "Khusus admin")
    _load_store()
    rows = list(reversed(_FEEDBACK))
    return {"status": True, "total": len(rows), "data": rows}


@app.post("/api/admin/feedback/read")
async def admin_mark_feedback(request: Request):
    body = await request.json()
    email = _verify_token(body.get("token") or "")
    if not _is_admin(email):
        raise HTTPException(403, "Khusus admin")
    fid = str(body.get("id") or "")
    _load_store()
    for row in _FEEDBACK:
        if row.get("id") == fid:
            row["read"] = True
    _save_store()
    return {"status": True}


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    """Logout hanya di client (token dibuang). Akun tetap di server."""
    return {"status": True, "message": "Logout OK — email & password tetap bisa dipakai masuk lagi"}


@app.get("/api/auth/me")
async def auth_me(token: str = Query("")):
    email = _verify_token(token)
    _load_store()
    user = _USERS.get(email) or {}
    return {
        "status": True,
        "user": {
            "email": email,
            "name": user.get("name") or email.split("@")[0],
            "avatar": user.get("avatar") or "",
            "is_admin": _is_admin(email),
        },
    }



@app.get("/{path:path}")
async def spa_fallback(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    candidate = APP_DIR / path
    if candidate.is_file() and candidate.resolve().is_relative_to(APP_DIR.resolve()):
        return FileResponse(candidate)
    content = _read_index_html()
    if content:
        return HTMLResponse(content, media_type="text/html; charset=utf-8")
    raise HTTPException(404, "Not found")


handler = Mangum(app)
