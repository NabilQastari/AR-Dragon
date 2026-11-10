# 🐉 PROJECT CONTEXT & TECHNICAL BIBLE: AR DRAGON SKY GUARDIAN (v4.0 — PRODUCTION READY)

> **Fungsi Dokumen:** Rujukan teknikal utama (*Single Source of Truth*) bagi kolaborasi antara Manusia (Developer) dan AI Agent (Hermes / Antigravity Agent).
> **Pasangan Dokumen:** Gunakan bersama `prd.md` untuk implementasi alur kerja berperingkat.
> **Status Implementasi:** Sistem navigasi penerbangan naga 3D (Y-T-A), integrasi model 3D pulau 800x800m, integrasi model naga `Dragon_Model.blend`, GUI HUD telemetri, dan streaming PIP webcam port 5053 telah **100% aktif dan terverifikasi**.

---

## 1. RINGKASAN KONSEP & IDENTITAS PROJEK

### 1.1 Identiti Gim
- **Nama Gim / Project Unity:** AR Dragon Sky Guardian (nama kode lama: `Dragon Wing AR`, dipakai pada namespace C# `DragonWingAR.*`)
- **Genre:** Exergaming PC berasaskan Webcam / 3D Semi-Open-World Flight Action / Edukasi Alam Sekitar
- **Enjin & Stack:**
  - **Unity:** Unity 6 (`6000.3.7f1`) Universal Render Pipeline (URP)
  - **Python:** Python 3.10+ (PyTorch CUDA, YOLOv8n-pose GPU, OpenCV 4.x)
  - **Blender:** Blender 5.1 / 5.2 CLI pipeline
- **Watak Utama:** Naga Penjaga Langit Elemen Air & Embun Purba (`Dragon_Model.blend`)
- **Misi Utama:** Menjelajah pulau daratan besar 800x800m dan memulihkan 3 desa daripada pencemaran udara, kebakaran hutan, dan kemarau menggunakan gestur tubuh interaktif di hadapan webcam.

### 1.2 Matriks Pembahagian Tugas (Semi-Autonomous Workflow)

| Kategori Tugas | Pelaksana Utama | Tanggungjawab |
| :--- | :--- | :--- |
| **Skrip Python CV & UDP Streaming (5052 & 5053)** | 🤖 **AI Agent** | Menulis modul inferensi YOLOv8n-pose, One-Euro filter, head-crop mouth tracker, dan streaming JPEG PIP. |
| **Skrip C# Unity (Navigasi 3D, Pose Y-T-A, HUD, UI)** | 🤖 **AI Agent** | Menulis keseluruhan kod C# bebas ralat (*0 Compiler Errors*), penyesuaian URP Lit, dan proteksi raycast tanah. |
| **Integrasi & Skala Aset 3D (`.blend` & `.fbx`)** | 🤖 **AI Agent + User** | Ekspor Blender CLI dengan bake transforms, pengaturan skala naga 5m dan pulau 800m di scene Unity. |
| **Ujian Play Mode & Kalibrasi Webcam Nyata** | 👨‍💻 **Manusia (User)** | Menguji gerakan tubuh di depan webcam, validasi responsivitas gameplay, dan evaluasi pengalaman bermain. |

---

## 2. PRINSIP DESAIN & ARSITEKTUR TEKNIS

### 2.1 Spesifikasi Karakter Naga (`Dragon_Model.blend` / `Dragon_Model.fbx`)
- **Aset 3D:** Model naga resmi menggunakan `Dragon_Model.blend` yang diekspor menjadi `Dragon_Model.fbx` di folder `Assets/Assets 3D/`.
- **Dimensi Fisik Nyata (1 Unity unit = 1 meter):**
  - **Bentang Sayap (X):** $5.06\text{ meter}$
  - **Panjang Tubuh (Z):** $3.60\text{ meter}$ (dari moncong kepala ke ujung ekor)
  - **Tinggi (Y):** $1.59\text{ meter}$
  - **Pusat Pivot:** Di-center tepat pada titik `(0, 0, 0)` koordinat lokal pemain.
- **Material & Shading:**
  - 12 Material **URP Lit** dengan mode *Double-Sided Rendering* (`_Cull = 0`) agar membran sayap dan sirip ekor tampak solid dari kedua sisi.
  - Palet warna: Teal body (`M_Dragon_Body_Teal`), turquoise wings (`M_Dragon_Wing_Membrane`), cream belly (`M_Dragon_Belly_Cream`), amber eyes (`M_Dragon_Eye_Amber`), dark dorsal ridges (`M_Dragon_Dorsal_DarkTeal`), and crystal chest (`M_Dragon_Chest_Crystal`).
- **Kamera Follow (Third-Person Cinematic):**
  - Parent: Child kepada `Dragon_Player`
  - `localPosition`: `(0.00, 2.50, -6.50)`
  - `localEulerAngles`: `(14.00, 0.00, 0.00)`
  - FOV: $60^\circ$ | Far Clip Plane: $1500\text{ m}$

### 2.2 Desain Daratan Pulau (`pulau.blend` / `pulau.fbx`)
- **Bentuk:** Daratan besar berkarakter *grounded cutaway slab* dengan 3 danau organik, bukit terjal, padang rumput, dan bukit vulkanik tinggi di sisi barat.
- **Dimensi Bounding Box:**
  - Panjang x Lebar: **$813.19\text{ m} \times 800.00\text{ m}$** (Skala $800 \times 800\text{ m}$, rasio 1:1, pusat di `(0, 0, 0)`).
  - Ketebalan Blok Medan: Dasar permukaan air $Y \approx -0.8\text{ m}$ hingga $-20\text{ m}$.
  - Ketinggian Puncak Gunung: Puncak tertinggi di $Y = 118.9\text{ m}$ pada koordinat `(-337, 119, -31)`.
- **Submesh & Kolisi:**
  - `Island_Terrain` (MeshCollider aktif)
  - `Island_Rocks` (MeshCollider aktif)
  - `Island_Water_01`, `Island_Water_02`, `Island_Water_03` (Renderer air danau URP Lit)
- **Titik Marker Lokasi 3 Desa (Pad Markers):**
  - **Desa 1 (Polusi Udara):** `Pad_Desa1_Polusi` di koordinat `(-200.00, 0.13, 80.00)`
  - **Desa 2 (Kebakaran Hutan):** `Pad_Desa2_HutanKebakaran` di koordinat `(10.00, 0.23, -133.00)`
  - **Desa 3 (Kekeringan Tanah):** `Pad_Desa3_Kekeringan` di koordinat `(260.00, 0.82, 13.00)`

---

## 3. SISTEM NAVIGASI TERBANG DINAMIS & GESTUR ALFABET (Y - T - A)

Penerbangan naga telah ditingkatkan dari *fixed altitude* menjadi **Sistem Navigasi 3D Penuh** berbasis gestur alfabet:

```
      \   /               — o —              /   \
       \o/                  |               /  o  \
     POSE Y               POSE T            POSE A
    (NAIK ↑)          (LURUS MENDATAR)     (TURUN ↓)
  Pitch Input > 0      Pitch Input = 0   Pitch Input < 0
   +8 ~ +10 m/s           0.0 m/s         -10 ~ -12 m/s
```

### 3.1 Detail Tiga Sikap Pose Alfabet
1. **Pose Y (Naik Menanjak $\uparrow$):**
   - **Bentuk Gestur:** Kedua tangan diangkat ke atas membentuk huruf **Y** (pergelangan tangan di atas bahu).
   - **Logika Deteksi:** `(dyL < -0.025f && dyR < -0.025f) || avgDeltaY < -0.035f || dyL < -0.06f || dyR < -0.06f`.
   - **Aksi Naga:** Ketinggian bertambah secara mulus (`climbSpeed = 10f`), kepala naga mendongak visual (Pitch $-18^\circ$ hingga $-22^\circ$), kecepatan maju sedikit berkurang (efek hambatan gravitasi).
2. **Pose T (Meluncur Lurus Mendatar $\rightarrow$):**
   - **Bentuk Gestur:** Kedua tangan direntangkan mendatar sejajar bahu membentuk huruf **T**.
   - **Logika Deteksi:** Tangan berada dalam *deadzone* bahu (antara $-0.03f$ dan $+0.04f$).
   - **Aksi Naga:** Naga meluncur mendatar pada ketinggian jelajah saat ini (`0.0 m/s` vertikal), kecepatan maju stabil $12.0\text{ m/s}$, kepala mendatar rata ($0^\circ$).
3. **Pose A (Menukik Turun $\downarrow$):**
   - **Bentuk Gestur:** Kedua tangan diarahkan serong ke bawah ke sisi paha membentuk huruf **A**.
   - **Logika Deteksi:** `(dyL > 0.035f && dyR > 0.035f) || avgDeltaY > 0.045f || dyL > 0.06f || dyR > 0.06f`.
   - **Aksi Naga:** Naga menukik tajam (`diveSpeed = 12f`), kepala naga menunduk visual (Pitch $+18^\circ$ hingga $+22^\circ$), akselerasi *Dive Speed Boost* otomatis aktif (kecepatan maju meningkat hingga $16.2\text{ m/s}$).

### 3.2 Kemudi Belok & Kemiringan Tubuh (Yaw Turn & Roll Banking)
- **Kemudi Belok:** Berdasarkan selisih ketinggian tangan: `float tiltDelta = LeftWrist.y - RightWrist.y;`
- **Deadzone:** Jika `Mathf.Abs(tiltDelta) < 0.08f` $\rightarrow$ Kemudi lurus.
- **Sensitivitas:** `turnInput = Mathf.Clamp(tiltDelta * 2.5f, -1f, 1f)`.
- **Putaran Yaw:** $65^\circ/\text{detik}$ di bidang horizontal.
- **Roll Banking Visual:** Model naga miring secara visual pada sumbu Z sebesar `-turnInput * 35f` derajat.

### 3.3 Proteksi Ketinggian Daratan (Raycast Ground Clearance Protection)
- Naga dilengkapi sensor raycast otomatis ke bawah sejauh 500 meter.
- **Plafon Minimum Dinamis:** `safeMinAltitude = Mathf.Max(5f, terrainHeight + 2.5f)`.
- Naga tidak akan pernah tembus atau tertimbun ke dalam tanah bukit pulau saat melakukan aksi menukik Pose A.
- **Plafon Maksimum:** `maxAltitude = 140f` (memungkinkan naga terbang bebas melintasi puncak gunung tertinggi $118.9\text{ m}$).

---

## 4. PROTOKOL JARINGAN UDP GANDA (DUAL-PORT UDP)

Modul Python dan Unity berkomunikasi melalui 2 port socket UDP terpisah berkecepatan tinggi:

```
[Python CV Sender]
   ├── UDP 127.0.0.1:5052 (Pose CSV Telemetri)  ───────> [UDPPoseReceiver.cs]
   └── UDP 127.0.0.1:5053 (JPEG Frame PIP Video) ──────> [InGameFlightHUD.cs]
```

### 4.1 Port 5052: Telemetri Pose Tubuh (13-Float CSV)
- **Host & Port:** `127.0.0.1:5052`
- **Frekuensi:** $\ge 30\text{ FPS}$ (latensi AI $\approx 10-15\text{ ms}$ pada CUDA GPU)
- **Format String CSV (13 nilai float ternormalisasi `0.0000` s/d `1.0000`):**
  ```text
  LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y,MOUTH_OPEN
  ```
  - `0..1` = Bahu Kiri (LS)
  - `2..3` = Bahu Kanan (RS)
  - `4..5` = Pergelangan Tangan Kiri (LW)
  - `6..7` = Pergelangan Tangan Kanan (RW)
  - `8..9` = Pinggul Kiri (LH)
  - `10..11` = Pinggul Kanan (RH)
  - `12` = Nilai Bukaan Mulut `MOUTH_OPEN` ($0.0 = \text{Tutup}, 1.0 = \text{Buka Lebar}$)

### 4.2 Port 5053: Streaming Video Webcam PIP (Picture-in-Picture)
- **Host & Port:** `127.0.0.1:5053`
- **Format Paket:** Raw byte buffer gambar JPEG terkompresi ($320 \times 180$ piksel, *quality* 48, ukuran paket $\approx 3-4\text{ KB} < 65\text{ KB}$ MTU UDP).
- **Fungsi di Unity:** Didekodekan langsung oleh `InGameFlightHUD.cs` menggunakan `Texture2D.LoadImage(bytes)` dan ditampilkan di kotak preview kanan atas layar.
- **Fallback Otomatis:** Jika Python video stream belum aktif, kotak PIP secara otomatis menampilkan radar kerangka (*interactive skeleton wireframe*) dengan badge status pose Y-T-A.

---

## 5. KONTROL AKSI DESA & AUTO-HOVER

Ketika naga terbang mendekati dan memasuki area *Trigger Collider* desa (`SphereCollider`, radius 25-35m):
1. **Auto-Hover:** Naga berhenti maju otomatis dan memutar badan secara anggun menghadap pusat desa dengan osilasi mengambang (*hover bobbing* $\pm 0.4\text{ m}$).
2. **Eksekusi Gestur Interaktif (5 detik = 100% Selesai):**

| Desa & Masalah | Aksi Naga | Gestur Pemain | Logika Pengesanan C# |
| :--- | :--- | :--- | :--- |
| **Desa 1 (Polusi Udara)** | Mengibas Kabut Asap | Kepakkan kedua tangan naik-turun melewati bahu | Status `IsFlapping` aktif saat tangan berganti posisi di atas dan bawah bahu. |
| **Desa 2 (Kebakaran Hutan)** | Semburan Air Purba | Buka mulut lebar (`MouthOpen > 0.45`) ATAU tangkupkan kedua tangan di dada | Status `IsWaterBreathing` aktif, mematikan partikel api desa. |
| **Desa 3 (Kekeringan Tanah)** | Memanggil Hujan Embun | Angkat kedua tangan tinggi ke angkasa di atas kepala | `IsHandsHighUp` aktif saat `LW.y < LS.y - 0.14f` dan `RW.y < RS.y - 0.14f`. |

3. **Penyelesaian:** Begitu progres desa mencapai 100%, status Auto-Hover dilepaskan dan naga kembali dapat terbang menjelajah ke desa berikutnya.

---

## 6. SISTEM KONTROL KEYBOARD HYBRID (*ZERO-CONFLICT*)

Untuk menjamin kelancaran pengujian kapan pun tanpa kamera, sistem keyboard fallback dirancang dengan aturan isolasi ketat:

- **Aturan Isolasi:** Jika data kamera UDP terhubung dan pengguna tidak menekan tombol fisik, keyboard **dilarang keras menimpa data gestur kamera**.
- **Pemetaan Tombol Keyboard:**
  - **Naik $\uparrow$ (Pose Y):** `W`, `Y`, `Panah Atas`, `Spasi`
  - **Turun $\downarrow$ (Pose A):** `S`, `A`, `Panah Bawah`
  - **Lurus Mendatar (Pose T):** `T` (atau lepas tombol)
  - **Kemudi Belok:** `Panah Kiri / Kanan`, `D`, `Q / E`
  - **Simulasi Aksi Desa:** Tombol `1` (Kepak Sayap), `2` / `F` (Semburan Air), `3` / `R` (Panggil Hujan)

---

## 7. STRUKTUR SCENE & FILE UTAMA

- **Scene Utama:** `Assets/_Scenes/Test_Dragon_Flight.unity` (Build Settings Index `0`).
- **Skrip C#:**
  - `Assets/_Scripts/Controllers/DragonFlightController.cs`: Pengendali penerbangan 3D, manuver Y-T-A, dive boost, attitude roll/pitch, ground raycast, dan auto-hover.
  - `Assets/_Scripts/CV_Receiver/IPoseProvider.cs`: Interface abstraksi penyedia pose.
  - `Assets/_Scripts/CV_Receiver/UDPPoseReceiver.cs`: Penerima data pose UDP 5052, smoothing, deteksi Y-T-A, dan keyboard fallback zero-conflict.
  - `Assets/_Scripts/UI/InGameFlightHUD.cs`: GUI telemetri kiri atas, kotak preview webcam PIP kanan atas (port 5053), radar kerangka, dan panduan kontrol bawah.
- **Skrip Python:**
  - `ARDragonSkyGuardian_CV/active_cv_sender.py`: Pengirim pose resmi YOLOv8n-pose CUDA GPU + streaming video JPEG PIP.
  - `ARDragonSkyGuardian_CV/udp_sender.py`: Helper socket UDP data pose & video.
  - `ARDragonSkyGuardian_CV/test_send_dummy_udp.py`: Bench pengujian sintetis siklus Y-T-A tanpa kamera.
