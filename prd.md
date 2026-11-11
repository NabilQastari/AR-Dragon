# 📋 PRODUCT REQUIREMENTS DOCUMENT (PRD) & DEVELOPMENT PLAYBOOK: AR DRAGON SKY GUARDIAN (v5.1)

> **Catatan Penamaan:** Project Unity = `AR Dragon Sky Guardian`, folder Python = `ARDragonSkyGuardian_CV`. Namespace C# = `DragonWingAR.*`.
> **Mod Kerja:** Kolaborasi Manusia (User/Developer) + AI Agent (Hermes / Antigravity Agent).
> **Rujukan Utama:** Dokumen teknis dan rumus matematika merujuk pada [`konteks.md`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/konteks.md).

---

## 🎯 1. VISI & TUJUAN PRODUK

AR Dragon Sky Guardian adalah game *PC exergaming* 3D berbasis input Computer Vision (kamera webcam) yang memadukan kebebasan simulasi penerbangan naga alami ala **Sky Peck** di atas pulau semi-terbuka (*semi-open-world*) dengan gameplay edukatif penyelamatan lingkungan.

### Sasaran Utama:
1. **Zero-Equipment Barrier:** Pemain hanya membutuhkan laptop/PC berkamera standar tanpa memerlukan sensor mahal (seperti Kinect atau VR headset).
2. **Kontrol Tubuh Alami Berbasis Mekanik Sky Peck:**
   - **Flap to Climb (Mengepakkan Tangan):** Menghasilkan daya angkat vertikal halus ($+6.5\text{ m/s}$) + dorongan maju ($+12\text{ m/s}^2$). **Decoupled:** Bebas dari goyangan pitch nodding bolak-balik saat tangan diayun naik-turun.
   - **Glide (Rentangkan Sayap):** Meluncur jelajah santai dengan sink rate alami yang anggun ($-1.0\text{ m/s}$) pada kecepatan $14\text{ m/s}$.
   - **Tuck to Dive (Pose Foto Pengguna):** Tangan mengepal di dada atas, siku mengarah ke bawah di samping badan, memicu terjun menukik tajam (pitch $-45^\circ$) dengan akselerasi tinggi hingga $28\text{ m/s}$.
   - **Swoop Climb Out of Dive:** Membuka sayap setelah dive secara otomatis mengonversi kelebihan kecepatan kinetik menjadi luncuran melambung menanjak (*swoop soaring climb*) yang megah ke angkasa.
   - **Lean to Bank & Turn:** Kemiringan kombinasi torso ($50\%$) dan lengan ($50\%$) membelokkan arah yaw ($65^\circ/\text{s}$) dan memiringkan sayap naga secara visual ($\pm 35^\circ$).
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
| **Sesi 2** | Integrasi Socket UDP & Navigasi Terbang | ✅ **SELESAI** | UDP 5052 (Pose) & 5053 (PIP Video), Ground raycast protection, Keyboard fallback zero-conflict. |
| **Sesi 3** | Integrasi Aset 3D & In-Game HUD | ✅ **SELESAI** | `Dragon_Model.blend` (Skala 5m, URP Lit double-sided), `pulau.blend` (800x800m), InGameFlightHUD lengkap. |
| **Sesi 4 (NEW)** | Mekanik Penerbangan Ala Sky Peck | ✅ **SELESAI** | Flap to Climb (decoupled), Lean to Turn & Bank, Tuck to Dive ($28\text{ m/s}$), Swoop Climb otomatis, HUD Sky Peck. |
| **Sesi 5** | Zona 3 Desa, Mekanik Misi, & VFX | ⏳ **SELANJUTNYA** | `VillageZoneController` di 3 Pad desa, sistem timer, partikel polusi/kebakaran/kekeringan, dan audio ambience. |
| **Sesi 6** | UI Lobby, Sistem Bintang, & Build PC | ⏳ **TERAKHIR** | Menu pemilihan level, skor bintang 1-3, sound effects, dan ekspor executable `.exe` Windows. |

---

## 🛠️ 3. SPESIFIKASI SESI IMPLEMENTASI

---

### 🔬 SESI 1: KOMPUTASI VISION & UDP SENDER (SELESAI ✅)
- **Modul Python:** `ARDragonSkyGuardian_CV/active_cv_sender.py`
  - YOLOv8n-pose dengan primary target locking (bounding box terbesar).
  - Dynamic arm length clamping & One-Euro filter untuk mencegah jitter tangan.
  - Head-cropped mouth openness detection untuk mendeteksi semburan air purba.
  - Dual UDP streaming: port `5052` (telemetri pose) dan port `5053` (JPEG frame preview PIP Unity).

---

### 🕹️ SESI 2: NAVIGASI PENERBANGAN 3D & ELYTRA DYNAMICS (SELESAI ✅)
- **Komponen Unity:**
  - `PythonProcessManager.cs`: Mengelola lifecycle proses `active_cv_sender.py` secara otomatis. Menjalankan Python saat Unity dimainkan (`Play Mode`) dan menghentikannya seketika saat Unity keluar (`OnApplicationQuit` / `ExitingPlayMode`), sehingga pemain tidak perlu lagi membuka terminal terpisah.
  - `UDPPoseReceiver.cs`: Mendengarkan UDP `5052`, mem-parsing data CSV 21-float, mendeteksi gestur Elytra (Tuck Dive, Flapping, T-Pose, Climb), serta menyediakan fallback keyboard zero-conflict yang tidak menimpa data kamera.
  - `DragonFlightController.cs`:
    - **Minecraft Elytra 3D Physics:** Vektor gerak maju searah hadap hidung 3D (`transform.forward * airspeed`).
    - **Pertukaran Energi Kinetik:** Menukik menambah kecepatan via gravitasi ($a = -g \cdot \sin(\theta)$), menanjak mengonversi kecepatan menjadi ketinggian.
    - **Kepakan Sayap (Flapping):** Menghasilkan akselerasi daya dorong maju ($+14\text{ m/s}^2$) dan gaya angkat vertikal ($+3.5\text{ m/s}$).
    - **Tuck Dive (Pose di Foto Pengguna):** Sayap terlipat, drag berkurang ($0.12$), terjun tajam $-45^\circ$ berakselerasi hingga $28\text{ m/s}$.
    - **T-Pose Elytra Glide:** Meluncur ke depan dengan sedikit dive $-5^\circ$ pada kecepatan jelajah $14\text{ m/s}$.
    - **Kemudi Belok:** Putaran Yaw ($65^\circ/\text{s}$) dan Roll banking visual ($\pm 35^\circ$).
    - **Ground Raycast Clearance:** Menjaga naga minimal $3.5\text{ m}$ di atas permukaan bukit pulau dan meratakan hidung naga secara otomatis saat mendekati kontur bukit pulau.

---

### 🐉 SESI 3: INTEGRASI ASET 3D PULAU, NAGA, & HUD (SELESAI ✅)
- **Aset 3D:**
  - **Pulau (`pulau.blend` / `pulau.fbx`):** Ukuran $813\text{ m} \times 800\text{ m}$ dengan terrain, bebatuan bukit, dan 3 danau organik.
  - **Naga (`Dragon_Model.blend` / `Dragon_Model.fbx`):** Dimensi bentang sayap $5.06\text{ m}$, panjang $3.60\text{ m}$, tinggi $1.59\text{ m}$. Shading menggunakan 12 material URP Lit double-sided rendering.
  - **Kamera Follow:** Posisi `(0, 2.5, -6.5)`, sudut $14^\circ$, memberikan sudut pandang sinematik yang proporsional.
- **In-Game Flight HUD (`InGameFlightHUD.cs`):**
  - **Kiri Atas:** Telemetri penerbangan naga (Airspeed, Sudut Pitch, Ketinggian, Status Mode Elytra, Slider Kemudi, Indikator Aksi Gestur).
  - **Kanan Atas:** Kotak Picture-in-Picture (PIP) menampilkan stream kamera langsung dari port 5053, dengan fallback radar kerangka tubuh interaktif lengkap dengan sendi siku.
  - **Bawah Layar:** Panduan kontrol singkat yang jelas.

---

### 🏡 SESI 5: INTERAKSI ZONA 3 DESA, MEKANIK TANTANGAN, & VFX (LANGKAH SELANJUTNYA ⏳)

**Tujuan Sesi:** Memasang *gameplay loop* pemulihan 3 desa di lokasi pad pulau yang sudah tersedia.
- **Desa 1 (Polusi Udara):** Pad `Pad_Desa1_Polusi` (-200, 0.13, 80). Gestur kepakan sayap untuk mengibas kabut asap.
- **Desa 2 (Kebakaran Hutan):** Pad `Pad_Desa2_HutanKebakaran` (10, 0.23, -133). Gestur buka mulut lebar / tangkup tangan untuk semburan air purba.
- **Desa 3 (Kekeringan Tanah):** Pad `Pad_Desa3_Kekeringan` (260, 0.82, 13). Gestur angkat kedua tangan tinggi ke langit untuk panggil hujan embun.
