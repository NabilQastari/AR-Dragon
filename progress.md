# 📈 PROGRESS PROJEK: AR DRAGON SKY GUARDIAN (v3.0)

> **Status Saat Ini:** Sesi 1 Selesai (Benchmark Berhasil Dijalankan), Menunggu Pemilihan Model CV untuk Masuk ke Sesi 2  
> **Terakhir Diperbarui:** 2026-10-26  
> **Rujukan Utama:** [`konteks.md`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/konteks.md) & [`prd.md`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/prd.md)

---

## 1. Matriks Status Tahapan & Sesi

| Tahap / Sesi | Ruang Lingkup | Status | Keterangan & Hasil |
| :--- | :--- | :---: | :--- |
| **Tahap 0** | Setup Manual & Environment Awal | ✅ **SELESAI (100%)** | Unity 2022.3 LTS (URP) diset ke `.NET Framework` & `Run In Background`. Python 3.10 `venv` terkonfigurasi dengan CUDA 12, PyTorch `2.7.1+cu118`, Git initialized dengan `.gitignore`. |
| **Sesi 1** | Ujian & Pemilihan Model Computer Vision (Python) | ✅ **SELESAI (100%)** — *Optimized* | Skrip pengujian dan benchmark diperbarui dengan **ThreadedCamera** (MJPG codec, mengeliminasi buffer lag/delay) dan **PoseStabilizer** (Adaptive One-Euro Filter untuk presisi tinggi anti-jitter). |
| **Sesi 2** | Jambatan UDP Unity & Prototaip Mekanik Terbang (Greybox) | ⏳ **BERIKUTNYA** | Siap dikerjakan: pembuatan `active_cv_sender.py`, script C# UDP receiver & smoothing, kontrol naga auto-forward & tilt, serta menu 1-klik `Session2_GreyboxBuilder.cs`. |
| **Sesi 3** | Integrasi Model 3D, Lingkungan Pulau, & Animasi Naga | ⏸️ Belum Dimulai | Aset 3D awal sudah tersedia di folder `Assets AR Dragon Sky Guardian/` (`Nagcu.blend`, `pohon.blend`, `rumah.blend`). |
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
- [x] **Pembaruan 3 Model CV Interaktif (Flap Anti-Glitch & Water Breath)**:
  - `test_mediapipe.py`: MediaPipe Pose FULL + Face Blendshapes
  - `test_yolopose.py`: YOLOv8n-pose CUDA + Face Blendshapes + Kinematic Clamping
  - `test_rtmpose.py`: RTMPose CUDA + Face Blendshapes + Kinematic Clamping
  - Ketiganya memiliki counter flap, deteksi buka mulut (`jawOpen >= 0.35`), efek partikel air, dan transmisi UDP 13 float.
- [x] **Skrip Uji Interaktif Webcam** (720p @ 30 FPS, horizontal mirror `cv2.flip(frame, 1)`, visualisasi skeleton overlay, pembacaan FPS, latensi, dan deteksi gestur real-time):
  - [`test_mediapipe.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/test_mediapipe.py) (MediaPipe Pose Landmarker)
  - [`test_yolopose.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/test_yolopose.py) (YOLOv8n-pose CUDA GPU)
  - [`test_rtmpose.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/test_rtmpose.py) (RTMPose via rtmlib + ONNX Runtime GPU)
- [x] **`cv_benchmark_runner.py`**: Skrip benchmark otomatis 15 detik/model.
- [x] **Hasil Benchmark Pengguna (`cv_benchmark_report.txt` per 2026-10-26):**

| Model | Avg FPS | Min/Max FPS | Latensi (ms) | Jitter (ms) | Analisis Karakteristik |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **MediaPipe Pose (CPU Lite)** | 8.1 | 4 / 21 | **35.6** | 18.02 | Latensi komputasi paling rendah (35.6 ms), namun jitter fluktuatif (18 ms). |
| **YOLOv8n-pose (CUDA GPU)** | 8.0 | 7 / 9 | **39.7** | **7.53** | **Paling stabil!** Jitter terendah (7.53 ms), rentang FPS sangat konsisten (7–9 FPS), latensi cepat (39.7 ms). Sangat direkomendasikan. |
| **RTMPose (rtmlib + ONNX CUDA)** | 8.1 | 6 / 12 | 60.5 | 15.50 | Latensi lebih tinggi (60.5 ms) karena overhead bridging ONNX Runtime. |

> **Rekomendasi Utama:** **YOLOv8n-pose (CUDA GPU)** karena stabilitas titik (*low jitter*) yang sangat konsisten, meminimalkan getaran kendali terbang pada naga di Unity. Alternatif kedua adalah **MediaPipe Pose** jika memprioritaskan latensi komputasi ringan.

---

## 3. Rencana Kerja Selanjutnya: Sesi 2 (Unity UDP Bridge & Greybox)

Segera setelah pengguna mengonfirmasi model yang dipilih:
1. **Python:** Membuat [`active_cv_sender.py`](file:///d:/Fauzih/Kuliah/SEMESTER%20V/Proyek%20Multimedia%20dan%20Game/AR%20Dragon/ARDragonSkyGuardian_CV/active_cv_sender.py) yang mengunci model pilihan agar siap dijalankan berdampingan dengan Unity.
2. **C# Scripting di Unity:**
   - `Assets/_Scripts/CV_Receiver/IPoseProvider.cs` & `UDPPoseReceiver.cs`: Pembaca socket port 5052 di background thread, parsing InvariantCulture, smoothing `Vector2.Lerp` (speed 12f), dan fallback kontrol keyboard (Panah Kiri/Kanan & tombol 1, 2, 3).
   - `Assets/_Scripts/Controllers/DragonFlightController.cs`: Maju otomatis (`speed = 12f`), ketinggian tetap (`Y = 15f`), belok yaw/roll berdasarkan selisih wrist Y (`LeftWrist.y - RightWrist.y`), dan sistem auto-hover saat masuk desa.
   - `Assets/_Scripts/Controllers/VillageZoneController.cs`: Deteksi trigger masuk/keluar desa, verifikasi gestur (Kepak Sayap Desa 1, Sembur Air Desa 2, Hujan Embun Desa 3), kenaikan progres `+20f/s`.
3. **Editor 1-Click Builder:**
   - `Assets/Editor/Session2_GreyboxBuilder.cs` dengan menu `[MenuItem("DragonWingAR/Sesi 2 - Bina Prototaip Greybox Scene")]` untuk instansiasi otomatis `Island_Root`, `Dragon_Player` (beserta Main Camera), dan 3 trigger zon desa di koordinat standar, disimpan ke `Assets/_Scenes/2_MainIslandScene.unity`.

---

## 4. Status Aset Pendukung (Persiapan Sesi 3)
Aset 3D Blender yang telah disiapkan di folder `Assets AR Dragon Sky Guardian/`:
- `Nagcu.blend`: Model naga utama (pemain)
- `pulau.blend`: Model pulau terapung utama (`Island_Root`)
- `pohon.blend`: Model vegetasi untuk pulau terapung
- `rumah.blend`: Model desa untuk 3 zona pemulihan

