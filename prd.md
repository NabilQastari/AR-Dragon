# 📋 PRODUCT REQUIREMENTS DOCUMENT (PRD) & DEVELOPMENT PLAYBOOK: AR DRAGON SKY GUARDIAN (v4.0)

> **Catatan Penamaan:** Project Unity = `AR Dragon Sky Guardian`, folder Python = `ARDragonSkyGuardian_CV`. Namespace C# = `DragonWingAR.*`.
> **Mod Kerja:** Kolaborasi Manusia (User/Developer) + AI Agent (Hermes / Antigravity Agent).
> **Rujukan Utama:** Dokumen teknis dan rumus matematika merujuk pada [`konteks.md`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/konteks.md).

---

## 🎯 1. VISI & TUJUAN PRODUK

AR Dragon Sky Guardian adalah game *PC exergaming* 3D berbasis input Computer Vision (kamera webcam) yang memadukan kebebasan simulasi penerbangan naga di atas pulau semi-terbuka (*semi-open-world*) dengan gameplay edukatif penyelamatan lingkungan.

### Sasaran Utama:
1. **Zero-Equipment Barrier:** Pemain hanya membutuhkan laptop/PC berkamera standar tanpa memerlukan sensor mahal (seperti Kinect atau VR headset).
2. **Kontrol Tubuh Alami (Intuitive Body Flight):**
   - Mengemudikan arah naga melalui kemiringan tubuh.
   - Mengendalikan elevasi ketinggian dengan pose alfabetik: **Pose Y (Naik $\uparrow$)**, **Pose T (Lurus Mendatar $\rightarrow$)**, dan **Pose A (Menukik $\downarrow$)**.
   - Melakukan aksi pemulihan desa (mengibas asap, menyemburkan air, memanggil hujan) melalui gestur tubuh interaktif dan bukaan mulut.
3. **Performa Tinggi & Bebas Lag:**
   - Inferensi AI YOLOv8n-pose $\le 15\text{ ms}$ di GPU CUDA.
   - Komunikasi UDP lokal tanpa jeda input (*instant response*).
   - Tampilan visual pulau dan naga stabil pada 60 FPS di Unity 6 URP.

---

## 🗺️ 2. STATUS ROADMAP PENGEMBANGAN

| Tahap / Sesi | Fokus Utama | Status | Hasil Utama |
| :--- | :--- | :---: | :--- |
| **Tahap 0** | Setup Environment Unity & Python | ✅ **SELESAI** | Unity 6 URP, venv Python, PyTorch CUDA, OpenCV. |
| **Sesi 1** | Evaluasi & Penguncian Model CV | ✅ **SELESAI** | Model YOLOv8n-pose terpilih, stabilisasi One-Euro filter, head-crop mouth tracker. |
| **Sesi 2** | Integrasi Socket UDP & Navigasi Terbang | ✅ **SELESAI** | UDP 5052 (Pose) & 5053 (PIP Video), Sistem Alfabet Y-T-A, Ground raycast protection, Keyboard fallback zero-conflict. |
| **Sesi 3** | Integrasi Aset 3D & In-Game HUD | ✅ **SELESAI** | `Dragon_Model.blend` (Skala 5m, URP Lit double-sided), `pulau.blend` (800x800m), InGameFlightHUD lengkap. |
| **Sesi 4** | Zona 3 Desa, Mekanik Misi, & VFX | ⏳ **SELANJUTNYA** | `VillageZoneController` di 3 Pad desa, sistem timer, partikel polusi/kebakaran/kekeringan, dan audio ambience. |
| **Sesi 5** | UI Lobby, Sistem Bintang, & Build PC | ⏳ **TERAKHIR** | Menu pemilihan level, skor bintang 1-3, sound effects, dan ekspor executable `.exe` Windows. |

---

## 🛠️ 3. SPESIFIKASI SESI IMPLEMENTASI

---

### 🔬 SESI 1: KOMPUTASI VISION & UDP SENDER (SELESAI ✅)
- **Modul Python:** `ARDragonSkyGuardian_CV/active_cv_sender.py`
  - YOLOv8n-pose dengan primary target locking (bounding box terbesar).
  - Dynamic arm length clamping & One-Euro filter untuk mencegah jitter tangan.
  - Head-cropped mouth openness detection untuk mendeteksi semburan air purba.
  - Dual UDP streaming: port `5052` (13-float CSV pose) dan port `5053` (JPEG frame 320x180 untuk preview PIP Unity).

---

### 🕹️ SESI 2: NAVIGASI PENERBANGAN 3D & SISTEM POSE Y-T-A (SELESAI ✅)
- **Komponen Unity:**
  - `UDPPoseReceiver.cs`: Mendengarkan UDP `5052`, mem-parsing data CSV secara thread-safe, menghitung pose Y-T-A, serta menyediakan fallback keyboard zero-conflict yang tidak menimpa data kamera.
  - `DragonFlightController.cs`:
    - **Auto-Forward:** Kecepatan jelajah $12\text{ m/s}$ dengan akselerasi menukik (*Dive Boost*) hingga $16.2\text{ m/s}$.
    - **Sistem Elevasi Y-T-A:**
      - **Pose Y:** Naik menanjak ($+10\text{ m/s}$, visual pitch mendongak).
      - **Pose T:** Meluncur mendatar ($0\text{ m/s}$ vertikal, mempertahankan ketinggian saat ini).
      - **Pose A:** Menukik turun ($-12\text{ m/s}$, visual pitch menunduk tajam).
    - **Kemudi Belok:** Putaran Yaw ($65^\circ/\text{s}$) dan Roll banking visual ($-35^\circ$ s/d $+35^\circ$).
    - **Ground Raycast Clearance:** Menjaga naga minimal $2.5\text{ m}$ di atas permukaan bukit pulau (bebas tembus tanah).

---

### 🐉 SESI 3: INTEGRASI ASET 3D PULAU, NAGA, & HUD (SELESAI ✅)
- **Aset 3D:**
  - **Pulau (`pulau.blend` / `pulau.fbx`):** Ukuran $813\text{ m} \times 800\text{ m}$ dengan terrain, bebatuan bukit, dan 3 danau organik.
  - **Naga (`Dragon_Model.blend` / `Dragon_Model.fbx`):** Dimensi bentang sayap $5.06\text{ m}$, panjang $3.60\text{ m}$, tinggi $1.59\text{ m}$. Shading menggunakan 12 material URP Lit double-sided rendering.
  - **Kamera Follow:** Posisi `(0, 2.5, -6.5)`, sudut $14^\circ$, memberikan sudut pandang sinematik yang proporsional.
- **In-Game Flight HUD (`InGameFlightHUD.cs`):**
  - **Kiri Atas:** Telemetri penerbangan naga (Kecepatan, Ketinggian, Status Pose Y/T/A, Slider Kemudi, Indikator Aksi Gestur).
  - **Kanan Atas:** Kotak Picture-in-Picture (PIP) menampilkan stream kamera langsung dari port 5053, dengan fallback radar kerangka tubuh interaktif.
  - **Bawah Layar:** Panduan kontrol singkat yang jelas.

---

### 🏡 SESI 4: INTERAKSI ZONA 3 DESA, MEKANIK TANTANGAN, & VFX (LANGKAH SELANJUTNYA ⏳)

**Tujuan Sesi:** Memasang *gameplay loop* pemulihan 3 desa di lokasi pad pulau yang sudah tersedia.

#### A. Penempatan Zona Desa di Pad Pulau:
1. **Desa 1 (Polusi Asap):**
   - Posisi Pad: `(-200.00, 0.13, 80.00)`
   - Trigger: `SphereCollider` (Radius $28\text{ m}$, `isTrigger = true`).
   - Masalah: Asap hitam pekat menyelimuti desa.
   - Partikel: `VFX_BlackSmoke` (*Particle System* laju emisi 50 $\rightarrow$ berkurang ke 0 seiring progres).
   - Gestur Penyelesaian: **Mengepakkan Sayap** (gerakan tangan naik-turun melewati bahu secara berulang).
2. **Desa 2 (Kebakaran Hutan):**
   - Posisi Pad: `(10.00, 0.23, -133.00)`
   - Trigger: `SphereCollider` (Radius $32\text{ m}$, `isTrigger = true`).
   - Masalah: Pohon dan perumahan terbakar api.
   - Partikel: `VFX_Fire` (Skala api menyusut dari 1.0 ke 0.0) + `VFX_WaterBreath` (Semburan partikel air dari mulut naga).
   - Gestur Penyelesaian: **Membuka Mulut Lebar** (`MouthOpen > 0.45`) atau menangkupkan kedua tangan di depan dada.
3. **Desa 3 (Kekeringan Tanah):**
   - Posisi Pad: `(260.00, 0.82, 13.00)`
   - Trigger: `SphereCollider` (Radius $30\text{ m}$, `isTrigger = true`).
   - Masalah: Tanah retak tandus dan pepohonan kering kecoklatan.
   - Partikel: `VFX_DewRain` (Hujan embun keemasan dari langit) + perubahan warna material tanah/pohon dari coklat ke hijau subur via `Color.Lerp`.
   - Gestur Penyelesaian: **Mengangkat Kedua Tangan Tinggi** di atas kepala (Pose V/Y tinggi).

#### B. Mekanik Auto-Hovering:
- Saat naga masuk ke zona desa yang belum pulih, naga secara otomatis berhenti maju dan mengambang halus (*hover bobbing* $\pm 0.4\text{ m}$) sambil menghadap ke pusat desa.
- Kecepatan pemulihan: $+20\%$ per detik aksi sah (5 detik aksi konsisten = 100% pulih).
- Begitu mencapai 100%, naga dilepaskan dari status hover dan dapat terbang menuju desa berikutnya.

---

### 🏆 SESI 5: GAME MANAGER, SISTEM LEVEL, & FINAL POLISH (TAHAP TERAKHIR ⏳)

**Tujuan Sesi:** Menyelesaikan alur permainan menyeluruh dari menu lobby hingga kemenangan.

1. **Struktur Level & Waktu:**
   - **Level 1 (Pemula):** Hanya Desa 1 aktif. Batas waktu: 90 detik.
   - **Level 2 (Menengah):** Desa 1 + Desa 2 aktif. Batas waktu: 150 detik.
   - **Level 3 (Ahli):** Ketiga Desa aktif. Batas waktu: 210 detik.
2. **Sistem Penilaian Bintang:**
   - Selesai sebelum waktu habis & Progres 100% $\rightarrow$ **3 Bintang** ⭐⭐⭐
   - Waktu habis & Progres $\ge 67\%$ $\rightarrow$ **2 Bintang** ⭐⭐
   - Waktu habis & Progres $\ge 34\%$ $\rightarrow$ **1 Bintang** ⭐
   - Progres $< 34\%$ $\rightarrow$ **Gagal / Mengulang**
3. **Audio & Sound Effects:**
   - BGM tema penerbangan orkestra fantasi.
   - SFX kepakan sayap naga saat pose Y.
   - SFX angin mendesing saat pose A menukik tajam (*dive boost*).
   - SFX semburan air dan lonceng kemenangan desa pulih.
4. **Final Standalone Build:**
   - Ekspor standalone Windows executable (`AR_Dragon_Sky_Guardian.exe`).
   - Skrip *one-click batch launcher* (`start_game.bat`) yang otomatis menyalakan background Python sender dan game Unity secara bersamaan.

---

## 🎮 4. PANDUAN PENGUJIAN CEPAT (TESTING PLAYBOOK)

### Cara Menjalankan Sesi Pengujian Saat Ini:

1. **Menjalankan Game di Unity:**
   - Buka project di Unity 6.
   - Buka scene: `Assets/_Scenes/Test_Dragon_Flight.unity`.
   - Tekan tombol **Play (▶️)**.
2. **Menjalankan Pengirim Pose Python:**
   - Buka terminal PowerShell di folder `ARDragonSkyGuardian_CV`:
     ```powershell
     cd ARDragonSkyGuardian_CV
     venv\Scripts\activate
     python active_cv_sender.py
     ```
   - Berdiri atau duduk di depan webcam dengan pencahayaan yang cukup.
3. **Uji Coba Kontrol:**
   - Angkat tangan membentuk **Y** $\rightarrow$ Naga menanjak naik $\uparrow$.
   - Rentangkan tangan membentuk **T** $\rightarrow$ Naga meluncur lurus mendatar $\rightarrow$.
   - Arahkan tangan ke bawah membentuk **A** $\rightarrow$ Naga menukik tajam dengan kecepatan bertambah $\downarrow$.
   - Miringkan tangan $\rightarrow$ Naga berbelok kiri/kanan dengan kemiringan tubuh (*banking roll*).
4. **Uji Coba Keyboard (Tanpa Kamera):**
   - Tekan `W` atau `Y` $\rightarrow$ Naik.
   - Tekan `S` atau `A` $\rightarrow$ Turun.
   - Tekan `T` atau lepas tombol $\rightarrow$ Lurus.
   - Tekan `Panah Kiri/Kanan` atau `D` $\rightarrow$ Belok.
