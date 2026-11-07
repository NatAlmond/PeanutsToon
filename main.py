"""
PeanutsToon v1.4.2 — multi-source via API only (no scrape fallback)
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
from fastapi import FastAPI, HTTPException, Query
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
VORATOON_API = os.environ.get("VORATOON_API", "https://api.voratoon.com").rstrip("/")
VORATOON_WEB = os.environ.get("VORATOON_WEB", "https://voratoon.co").rstrip("/")
VORATOON_BASE = os.environ.get("VORATOON_BASE", "https://v10.voratoon.com").rstrip("/")
KIRYUU_API = os.environ.get("KIRYUU_API_BASE", "https://kiryuu-api-by-nat.vercel.app").rstrip("/")
TIMEOUT = float(os.environ.get("PT_TIMEOUT", "28"))

app = FastAPI(title="PeanutsToon", version="1.4.2")
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



# ---- Voratoon (API + HTML fallback, ignore 403 body) ----
async def _vora_get(url: str, headers: Optional[dict] = None) -> tuple:
    is_api = "api.voratoon" in (url or "")
    origin = VORATOON_BASE if is_api else VORATOON_WEB
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*" if is_api else "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        "Referer": origin + "/",
        "Origin": origin,
    }
    if headers:
        h.update(headers)
    try:
        async with httpx.AsyncClient(timeout=max(TIMEOUT, 22.0), follow_redirects=True) as c:
            r = await c.get(url, headers=h)
        return r.status_code, r.text, r.content
    except Exception:
        return 0, "", b""


def _vora_parse_list(html: str) -> list:
    if not html:
        return []
    cover_map = {}
    html_n = html.replace('&amp;', '&')
    for cm in re.finditer(
        r'(https://cvr\.voratoon\.id/prod/series/([a-z0-9\-]+)/cover/\S+)',
        html_n,
        re.I,
    ):
        cover_map[cm.group(2).lower()] = cm.group(1).rstrip('"\'\\')

    out, seen = [], set()
    for m in re.finditer(r'/series/([a-z0-9\-]+)', html_n, re.I):
        slug = m.group(1).lower()
        if not slug or slug in seen or slug in ('page', 'genre', 'tag', 'library', 'browse', 'series'):
            continue
        seen.add(slug)
        title = _clean_title(slug.replace('-', ' ').title(), slug)
        thumb = cover_map.get(slug, '')
        out.append(_item(title, slug, thumb, 'COMIC', 'voratoon'))

    if HAS_BS4:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.select("a[href*='/series/']"):
                href = a.get('href') or ''
                mm = re.search(r'/series/([a-z0-9\-]+)', href, re.I)
                if not mm:
                    continue
                slug = mm.group(1).lower()
                img = a.find('img')
                alt = ''
                thumb = cover_map.get(slug, '')
                if img is not None:
                    alt = (img.get('alt') or img.get('title') or '').strip()
                    if not thumb:
                        thumb = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
                title = _clean_title(alt or a.get_text(' ', strip=True), slug)
                updated = False
                for it in out:
                    if it['slug'] == slug:
                        if alt and len(_clean_title(alt, slug)) >= 3:
                            it['judul'] = _clean_title(alt, slug)
                        if thumb and not it.get('thumbnail'):
                            it['thumbnail'] = _https(thumb)
                        updated = True
                        break
                if not updated and slug not in seen:
                    seen.add(slug)
                    out.append(_item(title, slug, thumb, 'COMIC', 'voratoon'))
        except Exception:
            pass
    return out



async def voratoon_latest(page=1):
    items = []
    # try API first
    code, text, _ = await _vora_get(f"{VORATOON_API}/series?page={page}&limit=40", {"Accept": "application/json"})
    if code == 200 and text:
        try:
            import json as _json
            body = _json.loads(text)
            rows = body.get("data") or body.get("series") or body if isinstance(body, list) else []
            if isinstance(body, dict) and isinstance(body.get("data"), dict):
                rows = body["data"].get("series") or body["data"].get("items") or []
            for it in rows if isinstance(rows, list) else []:
                if not isinstance(it, dict):
                    continue
                slug = str(it.get("slug") or it.get("id") or "")
                if not slug:
                    continue
                items.append(_item(it.get("title") or it.get("name") or slug, slug, it.get("cover") or it.get("thumbnail") or it.get("image") or "", "COMIC", "voratoon"))
        except Exception:
            pass
    if items:
        return items
    # HTML fallback — ambil banyak halaman browse agar setara NMT
    urls = [f"{VORATOON_WEB}/", f"{VORATOON_WEB}/browse", f"{VORATOON_WEB}/library"]
    start = max(1, int(page or 1))
    # page=1 → ambil browse 1..6 ; page=2 → 7..12 dst
    base_p = (start - 1) * 6
    for p in range(base_p + 1, base_p + 7):
        urls.append(VORATOON_WEB + ("/browse" if p == 1 else f"/browse?page={p}"))
    seen = set()
    merged = []
    for u in urls:
        code, text, _ = await _vora_get(u)
        if not text or len(text) < 400:
            continue
        for it in _vora_parse_list(text):
            if it["slug"] in seen:
                continue
            seen.add(it["slug"])
            merged.append(it)
        if len(merged) >= 80:
            break
    return merged or items


async def voratoon_search(q):
    items = []
    code, text, _ = await _vora_get(f"{VORATOON_API}/series?search={quote(q)}&page=1&limit=40", {"Accept": "application/json"})
    if code == 200 and text:
        try:
            import json as _json
            body = _json.loads(text)
            rows = body.get("data") or body.get("series") or (body if isinstance(body, list) else [])
            for it in rows if isinstance(rows, list) else []:
                if not isinstance(it, dict):
                    continue
                slug = str(it.get("slug") or it.get("id") or "")
                if slug:
                    items.append(_item(it.get("title") or slug, slug, it.get("cover") or it.get("thumbnail") or "", "COMIC", "voratoon"))
        except Exception:
            pass
    if items:
        return items
    for u in [f"{VORATOON_WEB}/?s={quote(q)}", f"{VORATOON_WEB}/browse?q={quote(q)}"]:
        code, text, _ = await _vora_get(u)
        if text and len(text) > 400:
            items = _vora_parse_list(text)
            if items:
                return items
    return items


async def voratoon_detail(slug):
    # API
    code, text, _ = await _vora_get(f"{VORATOON_API}/series/{slug}", {"Accept": "application/json"})
    title, syn, thumb, chapters = slug, "", "", []
    if code == 200 and text:
        try:
            import json as _json
            body = _json.loads(text)
            d = body.get("data") if isinstance(body.get("data"), dict) else body
            if isinstance(d, dict):
                title = d.get("title") or d.get("name") or slug
                syn = d.get("description") or d.get("synopsis") or ""
                thumb = d.get("cover") or d.get("thumbnail") or d.get("image") or ""
        except Exception:
            pass
    code2, text2, _ = await _vora_get(f"{VORATOON_API}/series/{slug}/chapters", {"Accept": "application/json"})
    if code2 == 200 and text2:
        try:
            import json as _json
            body = _json.loads(text2)
            rows = body.get("data") or body.get("chapters") or (body if isinstance(body, list) else [])
            for ch in rows if isinstance(rows, list) else []:
                if not isinstance(ch, dict):
                    continue
                cid = str(ch.get("slug") or ch.get("id") or ch.get("number") or "")
                chapters.append({
                    "judul": ch.get("title") or f"Chapter {ch.get('number','')}",
                    "slug": cid,
                    "number": str(ch.get("number") or ""),
                    "url": ch.get("url") or "",
                    "id": cid,
                })
        except Exception:
            pass
    if not chapters and HAS_BS4:
        for u in [f"{VORATOON_WEB}/series/{slug}", f"{VORATOON_WEB}/{slug}", f"{VORATOON_BASE}/series/{slug}"]:
            code, text, _ = await _vora_get(u)
            if not text or len(text) < 500:
                continue
            soup = BeautifulSoup(text, "html.parser")
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(" ", strip=True) or title
            og = soup.find("meta", property="og:image")
            if og:
                thumb = og.get("content") or thumb
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "chapter" not in href.lower() and not re.search(r"/ch[\-/]?\d", href, re.I):
                    continue
                cid = href.rstrip("/").split("/")[-1]
                chapters.append({"judul": a.get_text(" ", strip=True) or cid, "slug": cid, "number": "", "url": href if href.startswith("http") else urljoin(VORATOON_WEB, href), "id": cid})
            if chapters:
                break
    return {"status": True, "source": "voratoon", "data": {
        "judul": title, "slug": slug, "thumbnail": thumb, "sinopsis": syn,
        "genre": [], "status": "", "type": "COMIC", "chapters": chapters, "source": "voratoon",
    }}


async def voratoon_chapter(slug="", chapter="", url="", id=""):
    """Ambil gambar chapter Voratoon — coba beberapa pola URL + CDN."""
    ch = str(chapter or id or "").strip().strip("/")
    if ch.lower().startswith("chapter/"):
        ch = ch.split("/", 1)[-1]
    page_urls = []
    if url:
        page_urls.append(url)
    if slug and ch:
        page_urls += [
            f"{VORATOON_WEB}/series/{slug}/chapter/{ch}",
            f"{VORATOON_WEB}/series/{slug}/{ch}",
            f"{VORATOON_WEB}/series/{slug}/chapter-{ch}",
            f"https://voratoon.co/series/{slug}/chapter/{ch}",
            f"https://v10.voratoon.com/series/{slug}/chapter/{ch}",
            f"https://v1.voratoon.com/series/{slug}/chapter/{ch}",
        ]
    images = []
    if slug and ch:
        for api_path in (
            f"{VORATOON_API}/series/{slug}/chapters/{ch}",
            f"{VORATOON_API}/series/{slug}/chapter/{ch}",
            f"{VORATOON_API}/chapter/{slug}/{ch}",
        ):
            try:
                code, text, _ = await _vora_get(api_path, {"Accept": "application/json"})
                if code == 200 and text:
                    try:
                        body = json.loads(text)
                    except Exception:
                        body = None
                    if isinstance(body, dict):
                        for key in ("images", "pages", "data", "files"):
                            arr = body.get(key)
                            if isinstance(arr, list) and arr:
                                for u in arr:
                                    if isinstance(u, str) and u.startswith("http"):
                                        images.append(u)
                                    elif isinstance(u, dict):
                                        u2 = u.get("url") or u.get("src") or u.get("image") or ""
                                        if str(u2).startswith("http"):
                                            images.append(str(u2))
                                if images:
                                    break
                    if images:
                        break
            except Exception:
                continue

    if len(images) < 2:
        for page_url in page_urls:
            if not page_url:
                continue
            code, text, _ = await _vora_get(page_url)
            if not text or code >= 400:
                continue
            text_n = text.replace("\\/", "/")
            for u in re.findall(r"https?://cdn\.voratoon\.com[^\s\"'<>]+", text_n, re.I):
                u = u.rstrip("\\\"'")
                if u not in images:
                    images.append(u)
            for u in re.findall(r"https?://[^\s\"'<>]*voratoon[^\s\"'<>]+\.(?:jpg|jpeg|png|webp|avif)", text_n, re.I):
                u = u.rstrip("\\\"'")
                if u not in images:
                    images.append(u)
            if len(images) < 2 and HAS_BS4:
                soup = BeautifulSoup(text, "html.parser")
                for img in soup.find_all("img"):
                    src = (img.get("data-src") or img.get("src") or "").strip()
                    if not src.startswith("http"):
                        continue
                    low = src.lower()
                    if any(x in low for x in ("logo", "icon", "avatar", "banner", "ads", "emoji", "thumb")):
                        continue
                    if src not in images:
                        images.append(src)
            if len(images) >= 2:
                break

    seen = set()
    out = []
    for u in images:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return {"status": True, "source": "voratoon", "images": out}




# ---- Kiryuu (via Kiryuu-Api-By-Nat) ----
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
    allow = ("ikiru", "ainzscans", "ainzscans01", "shngm", "gmbr.pro", "manhwaindo", "wp.com", "googleusercontent", "voratoon", "cloudfront", "amazonaws", "kiryuu")
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
    sources = ["ikiru", "ainzscans", "manhwaindo", "shinigami", "voratoon", "kiryuu"]
    return {
        "status": "online",
        "app": "PeanutsToon",
        "version": "1.4.2",
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
    sources.append({"id": "voratoon", "name": "Voratoon"})
    sources.append({"id": "kiryuu", "name": "Kiryuu"})
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
    if source in ("all", "voratoon"):
        tasks.append(_safe(voratoon_latest(page)))
    if source in ("all", "kiryuu"):
        tasks.append(_safe(kiryuu_latest(page)))
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
    if source in ("all", "voratoon"):
        tasks.append(_safe(voratoon_search(q)))
    if source in ("all", "kiryuu"):
        tasks.append(_safe(kiryuu_search(q)))
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
