# 📋 PRODUCT REQUIREMENTS DOCUMENT (PRD) & DEVELOPMENT PLAYBOOK: AR DRAGON SKY GUARDIAN (v6.0)

> **Catatan Penamaan:** Project Unity = `AR Dragon Sky Guardian`, folder Python = `ARDragonSkyGuardian_CV`. Namespace C# = `DragonWingAR.*`.
> **Mode Kerja:** Kolaborasi Manusia (User/Developer) + AI Agent (Hermes / Antigravity Agent).
> **Rujukan Utama:** Dokumen teknis dan rumus matematika merujuk pada [`konteks.md`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/konteks.md).

---

## 🎯 1. VISI & TUJUAN PRODUK

AR Dragon Sky Guardian adalah game *PC exergaming* 3D berbasis input Computer Vision (kamera webcam) yang memadukan kebebasan simulasi penerbangan naga alami ala **Sky Peck** di atas pulau semi-terbuka (*semi-open-world*) dengan gameplay edukatif penyelamatan lingkungan.

### Sasaran Utama:
1. **Zero-Equipment Barrier:** Pemain hanya membutuhkan laptop/PC berkamera standar tanpa memerlukan sensor mahal (seperti Kinect atau VR headset).
2. **Kontrol Tubuh Alami Berbasis Mekanik Sky Peck:**
   - **Flap to Climb (Mengepakkan Tangan):** Menghasilkan daya angkat vertikal halus ($+6.5\text{ m/s}$) + dorongan maju ($+12\text{ m/s}^2$). **Decoupled:** Bebas dari goyangan pitch nodding bolak-balik saat tangan diayun naik-turun.
   - **Glide (Rentangkan Sayap):** Meluncur jelajah santai dengan sink rate alami yang anggun ($-1.0\text{ m/s}$) pada kecepatan $14\text{ m/s}$.
   - **Tuck to Dive (Pose Foto Pengguna):** Tangan mengepal di dada atas, siku mengarah ke bawah di samping badan, memicu terjun menukik tajam (pitch $-40^\circ \sim -45^\circ$) dengan akselerasi tinggi hingga $28\text{ m/s}$.
   - **Propeller Dash (Dorongan Cepat):** Rotasi lengan melingkar terus-menerus memicu dorongan kecepatan akseleratif hingga $26\text{ m/s}$.
   - **Swoop Climb Out of Dive:** Membuka sayap setelah dive secara otomatis mengonversi kelebihan kecepatan kinetik menjadi luncuran melambung menanjak (*swoop soaring climb*) yang megah ke angkasa.
   - **Continuous Lean to Bank & Turn:** Kemiringan kombinasi torso ($50\%$) dan lengan ($50\%$) membelokkan arah yaw ($65^\circ/\text{s}$) dan memiringkan sayap naga secara visual ($\pm 35^\circ$).
3. **Zero-Manual Python Launch:**
   - Unity mengelola proses Python secara otomatis (`PythonProcessManager.cs`). Pemain cukup menekan tombol Play di Unity dan Python CV langsung aktif serta tertaut otomatis tanpa membuka terminal terpisah.
4. **Arsitektur Input Modular (`IFlightInputProvider`):**
   - Karakter controller terisolasi dari detail sensor mentah kamera melalui antarmuka modular `IFlightInputProvider` dan `DefaultFlightInputMapper`.
5. **Performa Tinggi & Bebas Lag:**
   - Inferensi AI YOLOv8n-pose $\le 18\text{ ms}$ di GPU CUDA (54+ FPS).
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
| **Sesi 4** | Mekanik Sky Peck, Input Mapper & Auto-Launch | ✅ **SELESAI** | Flap Climb (decoupled), Lean Turn, Tuck Dive (28 m/s), Propeller Dash (26 m/s), Swoop Climb, `IFlightInputProvider`, `PythonProcessManager.cs`. |
| **Sesi 5** | Zona 3 Desa, Mekanik Misi, & VFX | ⏳ **SELANJUTNYA** | `VillageZoneController` di 3 Pad desa, sistem timer, partikel polusi/kebakaran/kekeringan, dan audio ambience. |
| **Sesi 6** | UI Lobby, Sistem Bintang, & Build PC | ⏳ **TERAKHIR** | Menu pemilihan level, skor bintang 1-3, sound effects, dan ekspor executable `.exe` Windows. |

---

## 🛠️ 3. SPESIFIKASI SESI IMPLEMENTASI

---

### 🔬 SESI 1: KOMPUTASI VISION & BIOMETRIK TERKUNCI (SELESAI ✅)
- **Modul Python:** `ARDragonSkyGuardian_CV/active_cv_sender.py`
  - YOLOv8n-pose dengan primary target locking (bounding box terbesar).
  - `RobustKeypointTracker`: Dynamic arm length clamping, Adaptive One-Euro filter, dan kinematic velocity gating untuk mencegah jitter tangan.
  - `BiometricNormalizer`: Normalisasi skala, jarak, dan posisi pemain di depan kamera.
  - `MouthTracker`: Head-cropped mouth openness detection untuk mendeteksi semburan air purba.
  - Dual UDP streaming: port `5052` (telemetri pose 39-float) dan port `5053` (JPEG frame preview PIP Unity).

---

### 🕹️ SESI 2: PONDASI SOCKET UDP & KONTROL TERBANG DASAR (SELESAI ✅)
- **Komponen Unity:**
  - `UDPPoseReceiver.cs`: Mendengarkan UDP `5052`, mem-parsing data CSV 39-float, serta menyediakan fallback keyboard zero-conflict yang tidak menimpa data kamera.
  - `DragonFlightController.cs`: Navigasi terbang dasar, kemudi Yaw/Pitch, dan deteksi ground raycast protection.

---

### 🐉 SESI 3: INTEGRASI ASET 3D PULAU, NAGA, & HUD (SELESAI ✅)
- **Aset 3D:**
  - **Pulau (`pulau.blend` / `pulau.fbx`):** Ukuran $813\text{ m} \times 800\text{ m}$ dengan terrain, bebatuan bukit, dan 3 danau organik.
  - **Naga (`Dragon_Model.blend` / `Dragon_Model.fbx`):** Dimensi bentang sayap $5.06\text{ m}$, panjang $3.60\text{ m}$, tinggi $1.59\text{ m}$. Shading menggunakan 12 material URP Lit double-sided rendering.
  - **Kamera Follow:** Posisi `(0, 2.5, -6.5)`, sudut $14^\circ$, memberikan sudut pandang sinematik yang proporsional.
- **In-Game Flight HUD (`InGameFlightHUD.cs`):**
  - **Kiri Atas:** Telemetri penerbangan naga (Airspeed, Sudut Pitch, Ketinggian, Status Mode Sky Peck, Slider Kemudi Lean, Indikator Aksi Gestur, Python CV Status PID).
  - **Kanan Atas:** Kotak Picture-in-Picture (PIP) menampilkan stream kamera langsung dari port 5053, dengan fallback radar kerangka tubuh interaktif lengkap dengan sendi siku.
  - **Bawah Layar:** Panduan kontrol singkat yang jelas.

---

### 🦅 SESI 4: MEKANIK PENERBANGAN ALA SKY PECK, INPUT MAPPER & AUTO-LAUNCH PYTHON (SELESAI ✅)
- **Fisika Penerbangan Sky Peck (`DragonFlightController.cs`):**
  - **Flap to Climb (Mendaki Vertikal Halus):** Mengepakkan tangan memberikan dorongan vertikal $+6.5\text{ m/s}$ dan dorongan akselerasi $+12\text{ m/s}^2$. Pitch tetap stabil ($+8^\circ \sim +12^\circ$), bebas dari nodding/goyangan bolak-balik saat tangan diayun.
  - **Lean to Turn & Bank:** Menggabungkan $50\%$ kemiringan lengan (*arm tilt*) dengan $50\%$ pergeseran sumbu torso (*torso lean*), memungkinkan pemain berbelok lincah dengan memiringkan tangan ataupun mencondongkan badan.
  - **Tuck to Dive (Pose Foto Pengguna):** Tangan dirapatkan mengepal di dada atas dengan siku mengarah ke bawah di samping badan. Sayap melipat aerodinamis rapat, hidung menukik tajam ($-40^\circ \sim -45^\circ$), dan naga meluncur kencang hingga batas $28\text{ m/s}$.
  - **Propeller Dash:** Memutar lengan secara melingkar kontinu menghasilkan dorongan akselerasi impulsif instan hingga $26\text{ m/s}$.
  - **Swoop Climb Out of Dive:** Membuka sayap setelah dive secara otomatis mengonversi kelebihan kecepatan ($> 14\text{ m/s}$) menjadi luncuran melambung naik (*swoop soaring climb*) yang megah, mengangkat ketinggian naga ke awan tanpa perlu mengepakkan tangan.
  - **Glide & Gentle Descent:** Meluncur jelajah santai dengan sink rate alami yang sangat lembut ($-1.0\text{ m/s}$) pada kecepatan $14\text{ m/s}$.
  - **Terrain Safety Protection:** Raycast otomatis ke bawah sejauh $500\text{ m}$ menjaga naga minimal $3.5\text{ m}$ di atas permukaan daratan dan meratakan hidung naga secara otomatis jika jarak $< 8.0\text{ m}$.
- **Arsitektur Input Modular (`IFlightInputProvider.cs` & `DefaultFlightInputMapper.cs`):**
  - Pemisahan data sensor CV dari controller gerak naga.
  - Penyesuaian kurva sensitivitas non-linear ($1.35$) dan anti-fatigue flap multiplier ($1.15$).
- **Peluncur Proses Otomatis (`PythonProcessManager.cs`):**
  - Mengelola lifecycle proses `active_cv_sender.py` secara otomatis.
  - Meluncurkan Python di background saat Play Mode dimulai (`Awake`/`OnEnable`).
  - Menghentikan proses Python beserta child process tree-nya seketika saat Play Mode berhenti (`ExitingPlayMode`/`OnApplicationQuit`), menjamin webcam tidak pernah terkunci (*zero webcam lock*).
  - Terpasang rapi pada GameObject `Dragon_Player` di scene `Test_Dragon_Flight.unity`.

---

### 🏡 SESI 5: INTERAKSI ZONA 3 DESA, MEKANIK TANTANGAN, & VFX (LANGKAH SELANJUTNYA ⏳)

**Tujuan Sesi:** Memasang *gameplay loop* pemulihan 3 desa di lokasi pad pulau yang sudah tersedia.
- **Desa 1 (Polusi Udara):** Pad `Pad_Desa1_Polusi` (-200, 0.13, 80). Gestur kepakan sayap untuk mengibas kabut asap.
- **Desa 2 (Kebakaran Hutan):** Pad `Pad_Desa2_HutanKebakaran` (10, 0.23, -133). Gestur buka mulut lebar / tangkup tangan untuk semburan air purba.
- **Desa 3 (Kekeringan Tanah):** Pad `Pad_Desa3_Kekeringan` (260, 0.82, 13). Gestur angkat kedua tangan tinggi ke langit untuk panggil hujan embun.
- **Implementasi Komponen C#:**
  - `VillageZoneController.cs` pada setiap pad desa dengan radius deteksi trigger 25-35m.
  - Auto-Hover lock dan progress meter 0-100% (5 detik eksekusi gestur).
  - Sistem partikel VFX (Asap partikel, Api partikel, dan Efek Hujan Partikel Embun).

---

### 🏆 SESI 6: POLISH UI, SCORING BINTANG & EXPORT PC BUILD (TERAKHIR ⏳)
- Menu Utama (Lobby, Pengaturan Kamera & Sensitivitas).
- Sistem penilaian 1-3 bintang berdasarkan kecepatan pemulihan 3 desa.
- Sound effects penerbangan (wind rush, flap whoosh, water splash) dan background ambience.
- Build release standalone `.exe` Windows 64-bit.
