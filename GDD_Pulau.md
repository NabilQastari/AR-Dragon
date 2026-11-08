# 🗺️ GDD PETA PULAU: AR DRAGON SKY GUARDIAN

> **Versi:** 1.1 (revisi: rasio peta 1:1, hanya danau dan bukit besar yang dihitung)
> **Cakupan:** Hanya peta daratan (pulau). Desain desa, hutan detail, dan gameplay lanjutan dibahas terpisah.
> **Engine akhir:** Unity (URP). **Alur model:** Roblox Studio (bentuk) → Blender (rapikan) → Unity.
> **Dokumen terkait:** `prd.md`, `konteks.md` (bagian 2.4, 2.5, 5), `prompt.md` (Blender). Jika ada selisih, **dokumen ini yang berlaku** untuk peta.

---

## 1. RINGKASAN DAN VISI

- Peta adalah **daratan besar yang grounded** (bukan pulau terapung), tanpa laut di sekelilingnya, berbentuk blok terrain dengan tepi potongan rata di atas latar polos.
- Isi peta: padang rumput luas, **3 danau besar**, beberapa bukit besar berbatu, bercak tanah kering, dan batu-batu kecil. Danau dan bukit kecil sengaja **tidak dipakai** (peta dibuat sederhana dan mudah dibaca). Hutan menyusul (bagian 4.5).
- Skalanya **besar**: pohon dan desa tampak kecil, sehingga naga bisa terbang jauh (semi-open-world).
- Di atas peta ada **3 zona tantangan**: Desa 1 (polusi udara), Desa 2 (hutan kebakaran), Desa 3 (kekeringan). Peta hanya menyediakan **area datar** untuk ketiganya (bagian 5).
- Pemain mengendalikan **naga** yang terbang pada ketinggian tetap `fixedY = 15 m` dengan `forwardSpeed = 12 m/s` (sesuai `konteks.md`).

## 2. REFERENSI DAN GAYA VISUAL

- **Referensi utama:** gambar daratan isometrik low-poly (file `Referensi Pulau.jpg`, sebelumnya `1794021677975.jpg`). Gambar kedua (bukit abu-abu berbentuk slab) **bukan** referensi.
- **Gaya:** stylized low-poly, flat shading, warna cerah, siang hari, tata letak bersih dan mudah dibaca, padang tengah luas dan kosong.
- **Tepi peta:** potongan blok terrain rata dengan lapisan tanah cokelat di sisi, bibir rumput hijau gelap tipis di atasnya.
- **Roblox Studio hanya dipakai untuk bentuk**, jadi gaya akhir (flat shading, warna) dibentuk di Blender.

## 3. ALUR KERJA (PIPELINE)

```text
[Roblox Studio]  Terrain: bentuk, cekungan danau, bukit        (geometri saja)
      │ klik kanan Terrain → Export Selection → .obj
      ▼
[Blender]        skala ÷2, rapikan mesh, flat shading, sisi blok, material,
                 air terpisah, batu, bercak tanah, pad desa
      │ FBX (Forward -Z, Up Y, Apply Transform)
      ▼
[Unity]          Island_Root, MeshCollider, material URP, uji terbang
```

**Aturan penting alur ini:**
- Ekspor `.obj` dari Terrain hanya membawa **bentuk**. Warna dan material **hilang** dan dibuat ulang di Blender. Karena itu tabel posisi dan ukuran di dokumen ini adalah **sumber kebenaran**, bukan screenshot.
- Resolusi voxel Terrain Roblox adalah 4 studs, jadi relief kecil akan tampak kasar. Blender wajib melakukan penghalusan dan decimate sebelum flat shading.
- **Tahap 0 (uji ekspor)** wajib selesai sebelum membangun peta penuh, untuk memastikan skala satuan dan perilaku air.

### 3.1 Sistem koordinat (satu aturan untuk semua alat)

| Alat | Sumbu horizontal | Ketinggian | Satuan |
| :--- | :--- | :--- | :--- |
| **Unity (acuan GDD)** | X = timur, Z = utara | Y | 1 unit = 1 m |
| Blender | X = timur, Y = utara | Z | 1 unit = 1 m |
| Roblox | X = timur, **Z = selatan** (utara = -Z) | Y | 1 m = 2 studs |

Konversi dari tabel GDD (koordinat Unity `(X, Z)`):
- **Blender:** `(x, y) = (X, Z)`; tinggi tetap.
- **Roblox:** `studs_X = 2 x X`, `studs_Z = -2 x Z`, `studs_Y = 2 x tinggi`.
- Parameter eksperimen: `VEXAG = 1` (tanpa pelebaran tinggi). Jika tinggi di Roblox dilebihkan, Blender membagi tinggi dengan `VEXAG`.
- Faktor skala impor Blender (kemungkinan 0.5) **dipastikan lewat Tahap 0**, bukan diasumsikan.

## 4. SPESIFIKASI PETA (SUMBER KEBENARAN)

### 4.1 Dimensi total

| Parameter | Nilai |
| :--- | :--- |
| Bounding box | **800 m (X) x 800 m (Z), rasio 1:1**, pusat (0, 0, 0) |
| Luas | ±640.000 m² (±0,64 km²) |
| Tebal blok | 20 m (dasar rata di Y = -20), tepi samping vertikal |
| Permukaan acuan | Y = 0 |
| Tinggi puncak maksimum | **12 m** (naga terbang di 15 m, jadi tidak boleh ada bukit lebih tinggi) |
| Tepi belakang (utara, timur laut) | Naik halus 4-8 m agar siluet bergelombang seperti referensi |
| Tepi depan (selatan, barat daya) | Hampir rata |
| Padang tengah | Paling datar dan kosong |

### 4.2 Danau (hanya 3 yang besar/sedang, total ±6-8% luas)

Posisi dari referensi, toleransi ±50 m. Bentuk organik. Kedalaman visual 2,5-3 m. Permukaan air ±0,5 m di bawah tanah sekitar. Pantai pasir lebar 6-10 m. **Danau kecil pada referensi tidak dihitung dan tidak dibuat.**

| ID | Pusat (X, Z) | Ukuran | Kategori | Bentuk |
| :-: | :-: | :-: | :-: | :--- |
| L1 | (-180, +227) | 190 x 110 m | Besar | Memanjang, agak berlekuk |
| L2 | (+115, +227) | 110 x 60 m | Sedang | Seperti kacang |
| L3 | (+25, -233) | 150 x 80 m | Besar | Memanjang, melengkung |

### 4.3 Bukit dan punggungan (hanya bukit besar, diameter alas ≥ 90 m)

**Bukit kecil pada referensi tidak dihitung dan tidak dibuat** (tanpa bukit pengisi acak).

| ID | Pusat (X, Z) | Diameter alas | Tinggi (HEIGHT_MULT = 1) | Karakter |
| :-: | :-: | :-: | :-: | :--- |
| H1a | (-330, +340) | 100 m | 10 m | Punggungan barat laut, puncak berbatu |
| H1b | (-220, +350) | 110 m | 12 m | Punggungan barat laut, puncak berbatu **gelap** |
| H1c | (-110, +355) | 90 m | 8 m | Punggungan barat laut, berbatu |
| H2 | (+250, +173) | 120 m | 12 m | Puncak berbatu **gelap**, paling mencolok |
| H3a | (+190, +80) | 150 m | 9-10 m | Gugusan timur, berbatu |
| H5 | (-130, -360) | 140 m | 7-8 m | Gugusan tepi depan, ada bercak tanah |
| H6 | (+10, -320) | 100 m | 6 m | Di sisi selatan L3 |

Aturan: kemiringan > ±42° atau area berbatu menjadi batu; puncak teratas H1b dan H2 menjadi batu gelap. Jika `HEIGHT_MULT` dinaikkan (lihat `prompt_v2.md`), semua tinggi dikalikan angka itu dan `fixedY` naga harus dinaikkan.

### 4.4 Bercak tanah dan batu
- **Bercak tanah kering (organik, 40-90 m):** D1 (+140, -127), D2 (-260, -13; berada di pad Desa 3), D3 (-130, -360), D4 (+170, -280), D5 (+330, +333).
- **Batu:** ±40 batu low-poly (2-6 m), dikelompokkan 3-8 batu di sekitar bercak tanah, kaki bukit, dan tepi danau. Padang tengah dikosongkan.

### 4.5 Hutan (tahap lanjutan, belum dikerjakan)
- 6-8 petak: 1-2 besar (180-220 m, jarak pohon 4-6 m), 2-3 sedang (100-150 m, 6-10 m), 3 kecil (40-70 m, 12-20 m).
- Pinus tinggi 8-10 m, ek 6-8 m; ±30-50 pohon tunggal. Posisi **acak**, hanya di rumput, tidak di tepi.
- Satu petak sedang (60-100 m) disiapkan sebagai Zona Desa 2.

## 5. ZONA GAMEPLAY DAN KORIDOR TERBANG

### 5.1 Tiga pad zona (area datar)

| Zona | Tema | Kandidat pusat (X, Z) | Catatan |
| :--- | :--- | :-: | :--- |
| Desa 1 | Polusi udara | (+200, -80) | Area timur-tengah, rumput datar |
| Desa 2 | Hutan kebakaran | (-10, +133) | Area utara-tengah, di tengah petak hutan sedang |
| Desa 3 | Kekeringan | (-260, -13) | Area barat; bercak tanah D2 digeser ke pad ini |

**Aturan pad (berlaku untuk posisi final):**
- Diameter ±40-50 m (trigger `SphereCollider` radius 18 m di Unity), kemiringan datar (selisih tinggi ≤ 0,5 m).
- Jarak antar-pad **minimal 250 m**; jarak ke tepi daratan **minimal 100 m**; tidak di atas danau, pantai, atau lereng batu.
- Posisi boleh **diacak** per build selama memenuhi aturan di atas. Koordinat di tabel adalah **kandidat sementara**, final setelah pembahasan desain desa.
- Isi desa (rumah, cerobong, api) **tidak** termasuk GDD peta ini.

### 5.2 Koridor terbang
- Titik mulai naga sementara di padang tengah sekitar (0, -80) (selaraskan dengan `prd.md`).
- Rute uji: mulai → Desa 1 → Desa 2 → Desa 3 ≈ 790 m ≈ 65-70 detik pada 12 m/s. Level 3 (210 detik) masih longgar.
- Semua bukit ≤ 12 m, sehingga naga tidak menembus medan pada `fixedY = 15`.

## 6. MATERIAL DAN WARNA

| Material Blender/Unity | Hex | Roblox Terrain (blockout) | Dipakai untuk |
| :--- | :-: | :--- | :--- |
| `M_Grass` | `#8CB44B` | Grass | Rumput |
| `M_GrassDark` | `#4F6B2E` | (tidak ada) | Bibir tepi blok |
| `M_Rock` | `#8A7F73` | Rock | Batu dan lereng curam |
| `M_RockDark` | `#4A4540` | Slate | Puncak berbatu gelap |
| `M_Sand` | `#C9A97A` | Sand | Pantai danau |
| `M_Dirt` | `#8B7355` | Ground | Bercak tanah kering |
| `M_SoilSide` | `#6B4A32` | Mud | Sisi dan dasar blok |
| `M_Water` | `#5B8FB0` | Water | Air danau (agak transparan) |

Material di Roblox hanya untuk acuan visual/screenshot; material final dibuat ulang di Blender.

## 7. SPESIFIKASI TEKNIS

| Parameter | Nilai |
| :--- | :--- |
| Anggaran poligon | Terrain ≤ ±40.000 segitiga; total scene ≤ ±80.000 |
| Shading | Flat shading, tanpa tekstur gambar |
| Nama objek | `Island_Terrain`, `Island_Water_01`..`08`, `Island_Rocks` |
| FBX | Apply Transform, Forward -Z, Up Y, Mesh saja, Triangulate |
| Unity | `MeshCollider` pada `Island_Terrain` (air tanpa collider), material URP Lit |
| Seed acak | 42 (supaya hasil bisa diulang) |
| Roblox Terrain | VOXEL = 4 studs, ukuran 1600 x 1600 studs, dasar di -40 studs |

## 8. TAHAP EKSEKUSI DAN KRITERIA SELESAI

Setiap tahap berhenti untuk konfirmasi sebelum lanjut. Prompt per tahap dibuat setelah GDD ini disetujui.

| Tahap | Pekerjaan | Kriteria selesai |
| :-: | :--- | :--- |
| **0** | **Uji ekspor:** kubus 100 studs dan terrain kecil (200 x 200 studs) → `.obj` → Blender | Skala impor terbukti (angka faktor dicatat), perilaku air diketahui, jumlah poligon wajar |
| **1** | **Roblox blockout:** bentuk terrain, cekungan 3 danau, bukit besar, air; tanpa objek lain | 1600 x 1600 studs, tinggi maks 24 studs, danau sesuai tabel ±100 studs, cek top-down |
| **2** | **Blender:** impor `.obj`, skala, rapikan, flat shading, sisi blok, material, air terpisah, batu, bercak tanah | 800 x 800 m, Z maksimum ≤ 12 m, segitiga sesuai anggaran, manifold, mirip referensi |
| **3** | **Desain desa dan hutan** (diskusi terpisah), lalu pad dan petak hutan final | Koordinat pad final, GDD diperbarui |
| **4** | **Unity:** impor FBX, collider, material URP, uji terbang | Naga tidak menembus medan, 3 pad terjangkau, waktu rute sesuai level |

## 9. RISIKO DAN KEPUTUSAN TERBUKA

| # | Risiko / pertanyaan | Rencana |
| :-: | :--- | :--- |
| 1 | Material Terrain tidak ikut terekspor | Material dibuat ulang di Blender (sudah dalam alur) |
| 2 | Skala satuan `.obj` belum pasti | Dipastikan di Tahap 0 |
| 3 | Voxel 4 studs membuat bukit bergerigi | Smoothing dan decimate di Blender; jika masih kasar, naikkan `VEXAG` |
| 4 | Air Roblox mungkin tidak terekspor sebagai mesh yang baik | Air dibuat ulang sebagai bidang terpisah di Blender |
| 5 | Poligon hasil ekspor sangat banyak | Decimate dan remesh di Blender sebelum Unity |
| 6 | Bentuk referensi hampir persegi, sedangkan `konteks.md` menyebut outline abstrak | **Diputuskan rasio 1:1 (800 x 800 m)** dengan tepi bergelombang halus. Koordinat Y dari tabel lama (800 x 600) dikali 4/3 agar komposisi referensi tetap sama |
| 7 | Tinggi bukit dibatasi 12 m oleh `fixedY = 15` | Jika ingin gunung lebih tinggi, naikkan `fixedY` atau tambahkan penyesuaian medan |
| 8 | `konteks.md` lama menulis 6 danau dan 21 bukit | Sudah disamakan: 3 danau dan 7 bukit besar |
| 9 | Koordinat pad desa masih sementara | Dikunci di Tahap 3 |

## 10. DOKUMEN LAMA YANG PERLU DISESUAIKAN

- `konteks.md` bagian 2.5: danau dan bukit disederhanakan (3 danau, 7 bukit besar); koordinat desa mengacu ke bagian 5 dokumen ini.
- `prompt.md` (Blender): Tahap A dibuat dari nol; perlu versi baru yang mengimpor `.obj` dari Roblox lalu merapikannya.
- Prompt Roblox lama: tinggi ×7 dan gaya "khas Roblox" diganti dengan skala seragam 1 m = 2 studs dan tujuan hanya bentuk (tanpa dinding batas, spawn, atau pencahayaan permainan).
