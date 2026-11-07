# PeanutsToon

Web komik standalone bertema gelap dengan aksen cokelat kacang.

**By: Nat**

## Apa ini?

PeanutsToon adalah pembaca komik di browser: cari judul, buka detail (sinopsis + daftar chapter), baca chapter layar penuh, plus **riwayat** dan **simpan** favorit (tersimpan di perangkatmu).

Fokusnya hanya komik — tanpa downloader, AI, atau tool lain.

## Isi aplikasi

| Bagian | Keterangan |
|--------|------------|
| **Beranda** | Update / daftar komik terbaru |
| **Pencarian** | Cari judul lewat ikon kaca pembesar |
| **Filter source** | Pilih sumber: Semua, Ikiru, AinzScans, ManhwaIndo, Shinigami (opsional) |
| **Detail** | Sampul, sinopsis, genre, daftar chapter |
| **Reader** | Baca gambar chapter fullscreen |
| **Riwayat** | Chapter yang pernah dibuka |
| **Simpan** | Bookmark komik favorit |

## Sumber data

PeanutsToon **tidak menyimpan file komik**. Data judul, sampul, sinopsis, chapter, dan gambar diambil lewat **API sumber** yang terhubung ke backend:

| Source | Jenis | Keterangan |
|--------|--------|------------|
| **Ikiru** | API | Katalog & chapter dari jaringan Ikiru |
| **AinzScans** | API | Katalog & chapter AinzScans |
| **ManhwaIndo** | API | Katalog & chapter ManhwaIndo |
| **Shinigami** | API (opsional) | Aktif jika API Shinigami dikonfigurasi di server |

Tidak ada scraper HTML langsung di aplikasi untuk source di atas; backend memanggil API masing-masing source.

## Catatan

- Konten milik situs sumber masing-masing; PeanutsToon hanya menampilkan ulang lewat API.
- Ketersediaan judul/chapter bergantung pada source (bisa kosong atau berubah sewaktu-waktu).
- Riwayat & simpan hanya di browser (localStorage), tidak diunggah ke server.

## File project

| File | Fungsi |
|------|--------|
| `index.html` | Tampilan & interaksi |
| `main.py` | Backend (FastAPI) + proxy ke API source |
| `requirements.txt` | Dependensi Python |
| `vercel.json` | Konfigurasi hosting |

---

**By: Nat**
