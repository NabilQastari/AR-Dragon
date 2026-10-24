# 📋 SEMI-AUTONOMOUS PRD & PLAYBOOK: AR DRAGON SKY GUARDIAN (v3.0)

> **Catatan Penamaan:** Nama project Unity = `AR Dragon Sky Guardian`, folder Python = `ARDragonSkyGuardian_CV`. Nama kode lama "Dragon Wing AR" / `DragonWingAR` tetap dipakai hanya untuk menu Editor `DragonWingAR/...` dan nama file.

> **Mod Kerja:** Kolaborasi Manusia + Hermes Agent (Semi-Autonomous Human-in-the-Loop)
> **Rujukan Wajib:** Baca `konteks.md` sebelum memulakan sebarang tugas.

---

## 🚨 PERATURAN WAJIB BAGI HERMES AGENT (SEMI-AUTONOMOUS RULES)

Sebagai AI Agent yang bekerjasama dengan pengguna (Manusia), anda **WAJIB** mematuhi 4 peraturan utama ini:

1. **JANGAN LAKUKAN SEMUA SESI SEKALIGUS (SATU SESI SETIAP GILIRAN):**
   Projek ini dibahagikan kepada Tahap 0 (Setup Manual) dan 5 Sesi Pembangunan. Anda hanya dibenarkan melaksanakan **SATU SESI** pada satu masa.

2. **PEMBAHAGIAN TUGAS KOMPLEKS vs TUGAS VISUAL/EDITOR:**
   - **Tugas Anda (Hermes Agent):** Menulis semua kod Python dan C# yang kompleks, algoritma matematik, pengurusan state, serta mencipta skrip pembantu automatik `Assets/Editor/SessionX_AutoSetup.cs` (menggunakan `[MenuItem("DragonWingAR/...")]`) supaya pengguna boleh membina objek Scene/UI hanya dengan 1 klik di menu atas Unity.
   - **Tugas Pengguna (Manusia):** Melakukan tindakan yang tidak dapat diakses oleh Agent (menjalankan ujian kamera fizikal, mengimport fail `.fbx` 3D, menyusun kehalusan visual di Unity Editor, atau menekan menu Auto-Setup).

3. **WAJIB MEMBERIKAN TUTORIAL LENGKAP & JELAS KEPADA PENGGUNA:**
   Setiap kali ada tugas yang perlu diselesaikan pengguna di Unity Editor atau Terminal, anda **DILARANG** sekadar memberi arahan ringkas. Anda **WAJIB** menulis Tutorial Langkah demi Langkah (Klik demi Klik) yang merangkumi:
   - Nama menu atau tetingkap yang perlu dibuka di Unity/Terminal.
   - Nama objek di Hierarchy dan komponen di Inspector yang perlu diubah.
   - Nilai parameter tepat yang perlu dimasukkan.

4. **BERHENTI & TANYA PENGGUNA DI SETIAP AKHIR SESI:**
   Pada penghujung setiap sesi, selepas kod dan tutorial diberikan, anda **WAJIB BERHENTI** dan mengemukakan soalan pengesahan daripada bahagian 🛑 **[SOALAN WAJIB AGENT KEPADA PENGGUNA]**. Jangan masuk ke sesi seterusnya sebelum pengguna menjawab "Sudah selesai / Lanjut".

---

## 🛠️ TAHAP 0: SETUP & INSTALASI AWAL (DILAKUKAN PENGGUNA DENGAN PANDUAN AGENT)

> **Arahan kepada Agent:** Pada permulaan perbualan, **JANGAN** tulis kod projek lagi. Tampilkan panduan ringkas Tahap 0 di bawah kepada pengguna, kemudian terus ajukan Soalan Wajib Tahap 0.

### Senarai Semak Persediaan Pengguna

**1. Pemasangan Unity 2022.3 LTS (URP)**
- Buka Unity Hub → **New Project** → pilih templat **3D (URP - Universal Render Pipeline)** → namakan projek `AR Dragon Sky Guardian`.
- Di Unity Editor: **Edit → Project Settings → Player → Other Settings**
  - Tukar **Api Compatibility Level** kepada `.NET Framework`.
- Di **Resolution and Presentation** (masih di Player Settings):
  - Tandakan **Run In Background** (wajib supaya Unity terus membaca data UDP walaupun tetingkap Python sedang aktif).

**2. Pemasangan Environment Python & Library CV**

Buka terminal (PowerShell / CMD) di folder projek dan jalankan:

```powershell
mkdir ARDragonSkyGuardian_CV
cd ARDragonSkyGuardian_CV
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install opencv-python mediapipe ultralytics
pip uninstall -y onnxruntime onnxruntime-gpu
pip install rtmlib onnxruntime-gpu
pip install nvidia-cuda-runtime-cu12 nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cufft-cu12 nvidia-curand-cu12 nvidia-cuda-nvrtc-cu12
```

> **Catatan:** `mmpose`/`mmcv` tidak dipakai karena tidak ada paket jadi untuk PyTorch 2.7 di Windows. RTMPose dijalankan lewat `rtmlib` (ONNX Runtime). Paket `nvidia-*-cu12` menyediakan library CUDA 12 yang dibutuhkan ONNX Runtime GPU. Di skrip RTMPose, panggil `onnxruntime.preload_dlls()` sebelum membuat model.

### 🛑 [SOALAN WAJIB AGENT KEPADA PENGGUNA — TAHAP 0]

> "Helo! Kita akan membangunkan projek AR Dragon Sky Guardian (Dragon Wing AR) v3.0 secara Semi-Autonomous. Sebelum saya mula menulis kod untuk Sesi 1 (Ujian Computer Vision), boleh sahkan:
> 1. Adakah projek Unity 2022.3 LTS (URP) dan tetapan .NET Framework serta Run In Background sudah selesai anda tetapkan?
> 2. Adakah environment Python beserta pustaka MediaPipe, YOLO-Pose, dan RTMPose sudah berjaya dipasang (atau ada mana-mana pustaka yang memerlukan bantuan/tutorial pemasangan lanjut)?
> 3. Adakah Tahap 0 ini sudah selesai dan saya boleh mulakan Sesi 1 sekarang?"

---

## 🔬 SESI 1: UJIAN & PEMILIHAN MODEL COMPUTER VISION (PYTHON)

> Laksanakan sesi ini **HANYA** selepas pengguna mengesahkan Tahap 0 selesai.

**Matlamat Sesi:** Agent menulis kesemua skrip ujian Computer Vision dan penghantar UDP, manakala Pengguna menjalankan ujian webcam secara langsung untuk memilih model yang paling lancar.

### 🤖 Tugas Hermes Agent (Sesi 1)

1. Bina `ARDragonSkyGuardian_CV/udp_sender.py`:
   - Kelas `PoseUDPSender(ip="127.0.0.1", port=5052)` yang menghantar rentetan CSV 12-float (`LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y`) yang telah dinormalisasikan (0.0000 – 1.0000).
2. Bina 3 skrip ujian webcam (720p @ 30 FPS, `cv2.flip(frame, 1)`), lengkap dengan paparan rangka badan (*skeleton overlay*), bacaan FPS, bacaan Latensi (ms), dan penghantaran UDP:
   - `test_mediapipe.py` (indeks MediaPipe: 11, 12, 15, 16, 23, 24)
   - `test_yolopose.py` (YOLOv8n-pose CUDA, indeks COCO: 5, 6, 9, 10, 11, 12)
   - `test_rtmpose.py` (RTMPose via `rtmlib` + ONNX Runtime GPU, `mode='lightweight'`, indeks COCO: 5, 6, 9, 10, 11, 12)
3. Bina `cv_benchmark_runner.py`:
   - Menguji setiap model selama 15 saat dan menjana jadual perbandingan purata FPS, Latensi (ms), dan Jitter ke dalam `cv_benchmark_report.txt`.

### 👨‍💻 Tutorial Wajib untuk Pengguna (Sesi 1)

Selepas mencipta fail di atas, Agent wajib menulis tutorial jelas tentang:
- Cara mengaktifkan `venv`.
- Cara menjalankan ketiga-tiga skrip di terminal.
- Pergerakan tangan apa yang perlu dicuba di hadapan kamera.
- Cara membaca keputusan di `cv_benchmark_report.txt`.

### 🛑 [SOALAN WAJIB AGENT KEPADA PENGGUNA — AKHIR SESI 1]

> "Saya telah menyiapkan semua skrip ujian CV di folder ARDragonSkyGuardian_CV berserta panduan cara menjalankannya di atas.
> 1. Adakah anda sudah mencuba ketiga-tiga skrip tersebut menggunakan webcam anda?
> 2. Berdasarkan prestasi FPS dan kestabilan titik, model manakah yang paling sesuai untuk kita kunci sebagai penghantar utama (MediaPipe, YOLO-Pose, atau RTMPose)?
> 3. Adakah Sesi 1 ini sudah selesai dan kita boleh beralih ke Sesi 2 (Penerima UDP & Prototaip Mekanik Terbang di Unity)?"

---

## 🕹️ SESI 2: JAMBATAN UDP UNITY & PROTOTAIP MEKANIK (GREYBOXING)

> Laksanakan sesi ini **HANYA** selepas pengguna memilih model CV dan membenarkan masuk ke Sesi 2.

**Matlamat Sesi:** Agent menulis semua skrip C# penerima UDP, kawalan terbang automatik, dan logik 3 zon desa, serta menyediakan Menu Auto-Builder 1-Klik supaya pengguna tidak perlu membina objek prototaip satu demi satu secara manual.

### 🤖 Tugas Hermes Agent (Sesi 2)

1. Cipta `ARDragonSkyGuardian_CV/active_cv_sender.py` menggunakan model CV pilihan pengguna daripada Sesi 1.
2. Di projek Unity, bina skrip C# berikut:
   - `Assets/_Scripts/CV_Receiver/IPoseProvider.cs` & `UDPPoseReceiver.cs`: membaca UDP port 5052 di *background thread*, mem-parsing 12 float CSV (`InvariantCulture`), melakukan *smoothing* `Vector2.Lerp` (speed = 12f), serta menyediakan **Kawalan Papan Kekunci Fallback** (Anak Panah Kiri/Kanan untuk belok, Kekunci 1/2/3 untuk simulasi gestur Desa 1/2/3) supaya pengguna boleh menguji di Unity bila-bila masa walaupun tanpa kamera.
   - `Assets/_Scripts/Controllers/DragonFlightController.cs`: pergerakan maju automatik (`forwardSpeed = 12f`), ketinggian tetap (`fixedY = 15f`), logik belok daripada perbezaan ketinggian tangan (`LeftWrist.y - RightWrist.y`), dan fungsi `SetHoverState(bool hover, Vector3 targetLookAt)`.
   - `Assets/_Scripts/Controllers/VillageZoneController.cs`: mengesan kemasukan naga melalui `OnTriggerEnter`, mengaktifkan Auto-Hover, menyemak matematik gestur mengikut jenis desa (`Pollution_Desa1`, `Wildfire_Desa2`, `Drought_Desa3`), menambah `localProgress` sebanyak `+20f`/saat, dan melepaskan Auto-Hover apabila mencapai 100%.
3. Bina Skrip Pembantu Editor `Assets/Editor/Session2_GreyboxBuilder.cs`:
   - Menu `[MenuItem("DragonWingAR/Sesi 2 - Bina Prototaip Greybox Scene")]` yang apabila diklik akan mencipta dan menyusun:
     - `Island_Root` (Plane berskala besar di (0,0,0)).
     - `Dragon_Player` (Cube di (0, 15, -80)) lengkap dengan `UDPPoseReceiver`, `DragonFlightController`, `Rigidbody` (`IsKinematic = true`), dan `Main Camera`.
     - 3 Silinder Zon Desa (`Village_1_Pollution`, `Village_2_Wildfire`, `Village_3_Drought`) lengkap dengan `SphereCollider` (`IsTrigger = true`, `Radius = 18f`) dan `VillageZoneController` di koordinat piawai.

### 👨‍💻 Tutorial Wajib untuk Pengguna (Sesi 2)

Agent wajib memberikan tutorial langkah demi langkah tentang:
- Cara menunggu Unity selesai *compile* skrip C#.
- Cara menekan menu **DragonWingAR → Sesi 2 - Bina Prototaip Greybox Scene** di bar atas Unity dan menyimpan Scene sebagai `Assets/_Scenes/2_MainIslandScene.unity`.
- Cara menguji Play Mode menggunakan papan kekunci dahulu, diikuti ujian bersama `python active_cv_sender.py`.

### 🛑 [SOALAN WAJIB AGENT KEPADA PENGGUNA — AKHIR SESI 2]

> "Semua skrip C# Sesi 2 dan menu pembina automatik telah siap! Sila ikuti tutorial ringkas di atas untuk menjana Scene prototaip.
> 1. Adakah menu DragonWingAR -> Sesi 2 - Bina Prototaip Greybox Scene berjaya membina objek di Scene anda tanpa sebarang ralat di Console?
> 2. Adakah ujian terbang, belok, dan Auto-Hover di ketiga-tiga zon desa sudah berfungsi dengan baik?
> 3. Adakah Sesi 2 sudah selesai dan kita boleh masuk ke Sesi 3 (Integrasi Model 3D Pulau, Desa, & Animasi Naga)?"

---

## 🐉 SESI 3: INTEGRASI MODEL 3D, LINGKUNGAN PULAU, & ANIMASI NAGA

> Laksanakan sesi ini **HANYA** selepas pengguna mengesahkan Sesi 2 selesai.

**Matlamat Sesi:** Menggantikan objek greybox dengan model 3D `.fbx` sebenar (atau model komposit low-poly jika ada aset yang belum siap) dan memasang sistem animasi Naga. Oleh sebab penyusunan model 3D dan Animator banyak melibatkan antara muka Unity Editor, Agent membina skrip penyambung animasi dan memberikan tutorial penuh pemasangan model 3D kepada pengguna.

### 🤖 Tugas Hermes Agent (Sesi 3)

1. Bina `Assets/_Scripts/Controllers/DragonAnimationBridge.cs`:
   - Menyambungkan status terbang (`turnInput`, `isHovering`, `activeVillageType`) daripada `DragonFlightController` kepada komponen Animator Naga (parameter: `Bool IsHovering`, `Int ActionType`, `Float TurnBlend`).
   - Menyertakan opsyen **Animasi Prosedural** (*Procedural Wing/Body Motion*) sebagai sokongan automatik sekiranya model 3D naga pengguna belum mempunyai klip animasi `.fbx` yang lengkap.
2. Bina skrip pembantu `Assets/Editor/Session3_Animat…`

> ⚠️ **Catatan:** Teks sumber terpotong di sini. Selebihnya Sesi 3 (skrip pembantu Editor, tutorial, dan soalan akhir sesi) serta **Sesi 4 dan Sesi 5** tidak ada dalam dokumen yang diberikan, jadi belum dimasukkan.
