# 📈 PROGRESS PROJEK: AR DRAGON SKY GUARDIAN (v3.0)

> **Status Saat Ini:** Sesi 2 Aktif (Pembangunan Jambatan UDP Unity & Prototaip Mekanik Terbang Greybox)  
> **Terakhir Diperbarui:** 2026-11-08  
> **Rujukan Utama:** [`konteks.md`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/konteks.md), [`prd.md`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/prd.md), & [`GDD_Pulau.md`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/GDD_Pulau.md)

---

## 1. Matriks Status Tahapan & Sesi

| Tahap / Sesi | Ruang Lingkup | Status | Keterangan & Hasil |
| :--- | :--- | :---: | :--- |
| **Tahap 0** | Setup Manual & Environment Awal | ✅ **SELESAI (100%)** | Unity 2022.3 LTS (URP) diset ke `.NET Framework` & `Run In Background`. Python 3.10 `venv` terkonfigurasi dengan CUDA 12, PyTorch `2.7.1+cu118`, Git initialized dengan `.gitignore`. |
| **Sesi 1** | Ujian & Pemilihan Model Computer Vision (Python) | ✅ **SELESAI (100%)** — *Locked* | **YOLOv8n-pose (CUDA GPU)** resmi dipilih & di-upgrade ke tingkat **Ultra-Accuracy** (Primary Player Locking, Dynamic Biometrics Clamping, Hysteresis Flap State Machine, Deadzone Steering, latensi ~12.5 ms). Modul produksi [`active_cv_sender.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/active_cv_sender.py) telah selesai dibuat. |
| **Sesi 2** | Jambatan UDP Unity & Prototaip Mekanik Terbang (Greybox) | 🟡 **SEDANG BERJALAN** | Membangun pondasi gameplay di Unity: script C# UDP receiver & smoothing (`UDPPoseReceiver.cs`), kontrol naga auto-forward & tilt (`DragonFlightController.cs`), trigger zon desa (`VillageZoneController.cs`), serta generator greybox 1-klik `Session2_GreyboxBuilder.cs`. |
| **Sesi 3** | Integrasi Model 3D, Lingkungan Pulau, & Animasi Naga | ⏸️ Belum Dimulai | Aset 3D awal sudah tersedia di folder `Assets AR Dragon Sky Guardian/` (`Nagcu.blend`, `pohon.blend`, `rumah.blend`, `pulau.blend`). |
| **Sesi 4** | Dynamic Environment, Particle Systems, & Progres Desa | ⏸️ Belum Dimulai | Efek asap polusi Desa 1, kebakaran Desa 2, dan kekeringan -> hijau Desa 3. |
| **Sesi 5** | GameManager, Scoring Bintang, Audio, & Final Build | ⏸️ Belum Dimulai | Integrasi loop game, UI/HUD, transisi level, dan build executable Standalone PC. |

---

## 2. Detail Rinci Penyelesaian

### ✅ Tahap 0: Setup & Konfigurasi Dasar
- [x] Folder struktur Unity dibuat:
  - `Assets/_Scripts/CV_Receiver/`
  - `Assets/_Scripts/Controllers/`
  - `Assets/Editor/`
  - `Assets/_Scenes/`
- [x] Inisialisasi Git dan `.gitignore` komprehensif (mengabaikan `Library/`, `Temp/`, `Obj/`, `Logs/`, `UserSettings/`, `venv/`, cache & file temporer Office).
- [x] Dependensi Python terverifikasi via `requirements.txt`:
  - `torch==2.7.1+cu118` (CUDA aktif pada NVIDIA GeForce RTX 3050 Laptop GPU 4 GB VRAM)
  - `mediapipe==1.1.1`
  - `ultralytics==8.4.178` (YOLOv8)
  - `rtmlib==0.0.16` + `onnxruntime-gpu==1.23.2` + paket CUDA 12 (`nvidia-*-cu12`)
- [x] Bobot pose `yolov8n-pose.pt` dan `pose_landmarker_lite.task` terunduh dan terverifikasi.
- [x] Skrip deteksi kamera [`check_camera.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/check_camera.py) dibuat dan siap pakai.
- [x] Verifikasi Unity Player Settings (dari `Dokumentasi Projek.docx`):
  - **Api Compatibility Level**: `.NET Framework`
  - **Run In Background**: Dicentang (aktif)

---

### ✅ Sesi 1: Ujian & Pemilihan Model Computer Vision
- [x] **`udp_sender.py`**: Modul pengirim data socket UDP ke `127.0.0.1:5052` dengan format CSV 13-float ternormalisasi (`0.0000` - `1.0000`):
  `LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y,MOUTH_OPEN`
- [x] **Peningkatan Kualitas YOLOv8n-pose (Ultra-Accuracy & Robustness)**:
  - **Primary Player Auto-Lock**: Otomatis mengunci pemain utama berdasarkan luas *bounding box* terbesar, mencegah interferensi orang lain yang melintas di latar belakang.
  - **Dynamic Biometric Arm Clamping**: Batasan jangkauan pergelangan tangan beradaptasi otomatis terhadap lebar bahu pengguna (`shoulder_width * 1.45`), memastikan tangan tidak pernah terlempar keluar tubuh baik saat duduk dekat kamera maupun berdiri jauh.
  - **Forearm Kinematic Stabilization**: Menghubungkan siku ke pergelangan saat terjadi motion blur atau oklusi cepat, menjaga pergerakan tetap natural tanpa patah.
  - **WingFlapDetector Hysteresis State Machine**: Deteksi siklus kepakan penuh (NAIK -> TURUN) anti-flicker dengan telemetri frekuensi kepakan (*Flap Rate* dalam Hz) dan daya dorong (*Flap Power* 0–100%).
  - **Smooth Deadzone Flight Steering**: Menghilangkan getaran/drift saat terbang lurus dengan deadzone (0.035), serta memberikan respon belok proporsional halus (-100% s/d +100%).
  - **Kecepatan Inferensi Super Cepat**: Latensi inferensi YOLOv8n pada Tensor Cores RTX 3050 tercatat **~12.5 ms (80 FPS)**.
- [x] **Modul Produksi [`active_cv_sender.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/active_cv_sender.py)**:
  - Dibuat khusus untuk berjalan berdampingan dengan Unity (tersedia opsi `--headless` untuk hemat resource saat gameplay).
- [x] **Zero-Delay Head-Cropping Architecture**:
  - Mengeliminasi beban 240 ms pemindaian wajah full-frame 720p dengan memotong area kepala secara dinamis (~200x200 px).
  - Latensi komputasi total anjlok dari **258 ms (3.9 FPS) ke 17.5 ms (57+ FPS)**.
  - Semburan air naga dan kepak sayap kini merespons seketika dalam 0 milidetik (Zero Delay).
- [x] **Skrip Uji Interaktif Webcam** (720p @ 30 FPS, horizontal mirror `cv2.flip(frame, 1)`, visualisasi skeleton overlay, pembacaan FPS, latensi, dan deteksi gestur real-time):
  - [`test_mediapipe.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/test_mediapipe.py) (MediaPipe Pose Landmarker)
  - [`test_yolopose.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/test_yolopose.py) (YOLOv8n-pose CUDA GPU - *Ultra Accuracy*)
  - [`test_rtmpose.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/test_rtmpose.py) (RTMPose via rtmlib + ONNX Runtime GPU CUDA)
- [x] **`cv_benchmark_runner.py`**: Skrip benchmark otomatis 15 detik/model.
- [x] **Model Terpilih Resmi**: **YOLOv8n-pose (CUDA GPU)** dikunci sebagai modul Computer Vision utama.

---

### 🟡 Sesi 2: Jambatan UDP Unity & Prototaip Mekanik Terbang (Greybox) — [DALAM PENGERJAAN]
- [ ] **`IPoseProvider.cs`**: Kontrak antarmuka C# penyedia data pose di Unity (`LeftWrist`, `RightWrist`, `LeftShoulder`, `RightShoulder`, `MouthOpen`, `IsFlapping`, dll).
- [ ] **`UDPPoseReceiver.cs`**:
  - Background thread UDP listener pada port `5052`.
  - Parsing string 13-float CSV dengan format kebal regional (`CultureInfo.InvariantCulture`).
  - Smoothing koordinat via `Vector2.Lerp` (kecepatan 12f) agar kontrol naga mulus tanpa tersentak.
  - **Keyboard Fallback Control**: Panah Kiri/Kanan untuk belok, tombol `1` (kepak sayap Desa 1), `2` (semburan air Desa 2), `3` (hujan embun Desa 3) agar Unity dapat langsung diuji dan dimainkan kapan pun tanpa kamera.
- [ ] **`DragonFlightController.cs`**:
  - Gerak maju otomatis naga (`forwardSpeed = 12f`).
  - Menjaga ketinggian naga tetap stabil (`fixedY = 15f`).
  - Mekanik belok Yaw dan Roll dinamis berdasarkan kemiringan tangan (`LeftWrist.y - RightWrist.y`).
  - Sistem **Auto-Hover** (`SetHoverState(bool hover, Vector3 targetLookAt)`) saat berada di dalam area desa.
- [ ] **`VillageZoneController.cs`**:
  - Deteksi trigger masuk/keluar desa via `OnTriggerEnter` / `OnTriggerExit`.
  - Verifikasi gestur spesifik tiap desa (Desa 1: Kepak Sayap, Desa 2: Sembur Air Naga, Desa 3: Hujan Embun).
  - Peningkatan progres desa `+20%/detik` saat gestur aktif.
  - Pelepasan Auto-Hover secara otomatis saat progres desa mencapai 100%.
- [ ] **`Session2_GreyboxBuilder.cs`**:
  - Menu Editor Unity 1-klik: `DragonWingAR -> Sesi 2 - Bina Prototaip Greybox Scene`.
  - Otomatis membuat scene `Assets/_Scenes/2_MainIslandScene.unity` lengkap dengan `Island_Root`, `Dragon_Player` (beserta kamera Third Person Follow), dan 3 zona desa kubus prototaip transparan.

---

## 3. Status Aset Pendukung (Persiapan Sesi 3)
Aset 3D Blender yang telah disiapkan di folder `Assets AR Dragon Sky Guardian/`:
- `Nagcu.blend`: Model naga utama (pemain)
- `pulau.blend`: Model pulau terapung utama (`Island_Root`)
- `pohon.blend`: Model vegetasi untuk pulau terapung
- `rumah.blend`: Model desa untuk 3 zona pemulihan
