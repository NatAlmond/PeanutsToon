# PeanutsToon

Web komik standalone — tema gelap + aksen kulit kacang.

**By: Nat**

## Fitur
- Beranda update (Ikiru)
- Pencarian
- Detail + sinopsis + daftar chapter
- Reader fullscreen
- Riwayat baca & Simpan (localStorage)
- Icon SVG only

## File
| File | Fungsi |
|------|--------|
| `index.html` | UI frontend |
| `main.py` | FastAPI + proxy ke Ikiru API |
| `requirements.txt` | Dependensi Python |
| `vercel.json` | Konfigurasi Vercel |

## Environment (opsional)
| Key | Default |
|-----|---------|
| `IKIRU_API_BASE` | `https://ikiru-api-by-nat.vercel.app` |
| `IKIRU_TIMEOUT` | `45` |

## Deploy Vercel
1. Buat repo GitHub, upload **semua file** di folder ini (root repo)
2. Vercel → Add Project → Import repo
3. Deploy (Framework: Other)
4. Opsional: Environment Variables → `IKIRU_API_BASE`

## Lokal
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Buka http://127.0.0.1:8000

## API (proxy)
- `GET /api/latest?page=1`
- `GET /api/search?q=`
- `GET /api/detail/{slug}`
- `GET /api/chapter?slug=&chapter=`
- `GET /health`

Sumber data: [Ikiru-Api-By-Nat](https://github.com/NatAlmond/Ikiru-Api-By-Nat)
