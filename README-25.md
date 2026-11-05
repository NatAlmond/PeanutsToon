# PeanutsToon

Web komik standalone — **By: Nat**

## Source (API only, tanpa scrape fallback)

| Source | API |
|--------|-----|
| Ikiru | `IKIRU_API_BASE` |
| AinzScans | `AINZ_API_BASE` |
| ManhwaIndo | `MANHWAINDO_API_BASE` |
| Shinigami | `SHINIGAMI_API_BASE` (opsional — deploy VernSG dulu) |

## Environment Variables (Vercel → PeanutsToon)

```
IKIRU_API_BASE=https://ikiru-api-by-nat.vercel.app
AINZ_API_BASE=https://ainz-scans-api-by-nat2.vercel.app
MANHWAINDO_API_BASE=https://manhwa-indo-api-by-nat.vercel.app
SHINIGAMI_API_BASE=
PT_TIMEOUT=40
```

## File yang diubah
- main.py
- index.html
- requirements.txt
- README.md

## Deploy
1. Upload/replace file di repo PeanutsToon
2. Set Environment Variables
3. Redeploy Vercel
4. Cek https://peanuts-toon.vercel.app/health → version 1.2.1
