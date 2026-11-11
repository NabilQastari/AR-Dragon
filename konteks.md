# 🐉 PROJECT CONTEXT & TECHNICAL BIBLE: AR DRAGON SKY GUARDIAN (v5.0 — ELYTRA 3D DYNAMICS & TUCK DIVE)

> **Fungsi Dokumen:** Rujukan teknikal utama (*Single Source of Truth*) bagi kolaborasi antara Manusia (Developer) dan AI Agent (Hermes / Antigravity Agent).
> **Pasangan Dokumen:** Gunakan bersama `prd.md` untuk implementasi alur kerja berperingkat.
> **Status Implementasi:** Dinamika penerbangan Minecraft Elytra 3D Sejati (Orientasi 3D bebas, Pertukaran Energi Kinetik-Gravitasi, Kepakan Sayap Fly Up + Speed Up, Pose Foto Pengguna Tuck Dive -45°, Pose T Glide -5°, dan Pose Y Climb) telah **100% aktif dan terverifikasi di Unity Play Mode**.

---

## 1. RINGKASAN KONSEP & IDENTITAS PROJEK

### 1.1 Identiti Gim
- **Nama Gim / Project Unity:** AR Dragon Sky Guardian (nama kode lama: `Dragon Wing AR`, dipakai pada namespace C# `DragonWingAR.*`)
- **Genre:** Exergaming PC berasaskan Webcam / 3D Semi-Open-World Elytra Flight Action / Edukasi Alam Sekitar
- **Enjin & Stack:**
  - **Unity:** Unity 6 (`6000.3.7f1`) Universal Render Pipeline (URP)
  - **Python:** Python 3.10+ (PyTorch CUDA, YOLOv8n-pose GPU, OpenCV 4.x)
  - **Blender:** Blender 5.1 / 5.2 CLI pipeline
- **Watak Utama:** Naga Penjaga Langit Elemen Air & Embun Purba (`Dragon_Model.blend`)
- **Misi Utama:** Menjelajah pulau daratan besar 800x800m dan memulihkan 3 desa daripada pencemaran udara, kebakaran hutan, dan kemarau menggunakan gestur tubuh interaktif di hadapan webcam.

### 1.2 Matriks Pembahagian Tugas (Semi-Autonomous Workflow)

| Kategori Tugas | Pelaksana Utama | Tanggungjawab |
| :--- | :--- | :--- |
| **Skrip Python CV & UDP Streaming (5052 & 5053)** | 🤖 **AI Agent** | Menulis modul inferensi YOLOv8n-pose, One-Euro filter, detektor Tuck Dive geometri siku, Flap detector, dan streaming JPEG PIP. |
| **Skrip C# Unity (Navigasi Elytra 3D, HUD, UI)** | 🤖 **AI Agent** | Menulis keseluruhan kod C# bebas ralat (*0 Compiler Errors*), dinamika fisika Elytra, penyesuaian URP Lit, dan proteksi raycast tanah. |
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

## 3. DINAMIKA PENERBANGAN 3D ELYTRA (MINECRAFT FLIGHT PHYSICS)

Sistem penerbangan dirancang bebas dari kunci orientasi (*non-locked 3D freedom*), mengikuti model dinamika **Minecraft Elytra**:

```
        \   /                 — o —                    | o |
         \o/                    |                     /  |  \
        POSE Y                POSE T                 TUCK DIVE
    (CLIMB SOARING)       (ELYTRA GLIDE)         (TERJUN CEPAT ↓↓)
   Pitch: +25° ~ +35°     Pitch: ~ -5° (Glide)      Pitch: -45° (Dive)
   Konversi Kecepatan    Kecepatan Jelajah 14 m/s   Akselerasi Gravitasi
     -> Ketinggian         Glide Slope Halus         Hingga 28 m/s!
```

### 3.1 Vektor Gerak 3D & Prinsip Non-Locking
- **Arah Gerak Sejati:**
  $$\vec{v} = \text{transform.forward} \times v_{\text{airspeed}}$$
  Naga terbang persis ke arah hadap moncong badannya. Ketika hidung mendongak ke atas, dorongan maju langsung membawanya terbang menanjak ke langit 3D.
- **Rotasi 3D Dinamis:**
  $$\text{rotation} = \text{Quaternion.Euler}(-\theta_{\text{pitch}}, \psi_{\text{yaw}}, \phi_{\text{roll}})$$

### 3.2 Pertukaran Energi Kinetik & Gravitasi (Gravity Energy Exchange)
1. **Saat Menukik ($\theta < 0$):**
   - Komponen gravitasi searah lintasan mempercepat laju naga:
     $$\Delta v = -g_{\text{accel}} \cdot \sin(\theta) \cdot \Delta t \quad (g_{\text{accel}} = 18\text{ m/s}^2)$$
   - Kecepatan melonjak cepat dari kecepatan jelajah ($14\text{ m/s}$) hingga batas terminal dive ($28\text{ m/s}$).
2. **Saat Menanjak ($\theta > 0$):**
   - Gravitasi memperlambat laju maju, mengonversi energi kinetik hasil dive menjadi kenaikan ketinggian tajam (*zoom climb soaring*).
   - Batas stall minimum dijaga pada $7.0\text{ m/s}$ agar naga tidak kehilangan kontrol.
3. **Aerodynamic Drag:**
   - Saat meluncur jelajah (T-Pose): Drag normal menstabilkan kecepatan di $14\text{ m/s}$.
   - Saat Tuck Dive: Sayap terlipat aerodinamis rapat, koefisien drag berkurang drastis ($0.12$), memungkinkan terjun bebas berkecepatan tinggi.

### 3.3 Gestur Kontrol Utama

| Gestur Tubuh | Sikap Fisik Pemain | Respon & Fisika Naga |
| :--- | :--- | :--- |
| **Mengepakkan Tangan (Wing Flapping)** | Gerakan kedua tangan naik-turun cepat melintasi bahu | **Fly Up + Speed Up:** Akselerasi dorongan maju kinetik ($+14\text{ m/s}^2$) + gaya angkat vertikal langsung ($+3.5\text{ m/s}$). Memberikan sensasi roket pendorong naga! |
| **Pose T (Elytra Glide)** | Kedua tangan direntangkan mendatar sejajar bahu | **Meluncur Maju dengan Sedikit Dive:** Pitch otomatis diatur $\approx -5^\circ$, meluncur mulus dengan kecepatan jelajah stabil $14\text{ m/s}$. |
| **Tuck Dive (Pose di Foto Pengguna)** | Tangan mengepal rapat di dada atas / leher, siku mengarah ke bawah di samping badan | **Dive Terjun Cepat:** Pitch menukik curam $-45^\circ$, hambatan udara berkurang, naga terjun bebas berakselerasi kencang hingga $24-28\text{ m/s}$. |
| **Pose Y / Angkat Badan** | Kedua tangan diangkat ke atas diagonal | **Arah Badan ke Atas (Climb):** Pitch mendongak $+25^\circ \sim +35^\circ$, mengonversi kecepatan dive menjadi pendakian tinggi ke awan. |
| **Kemudi Kemiringan (Tilt)** | Miringkan satu tangan lebih tinggi dari tangan lain | **Yaw Turn & Banking Roll:** Putaran kemudi horizontal ($65^\circ/\text{s}$) dan kemiringan visual sayap ($\pm 35^\circ$). |

### 3.4 Proteksi Ketinggian Daratan (Terrain Clearance Protection)
- Naga dilengkapi sensor raycast otomatis ke bawah sejauh 500 meter.
- **Plafon Minimum Dinamis:** `safeMinAltitude = terrainHeight + 3.5f`.
- Jika jarak ke daratan $< 8.0\text{ m}$, hidung naga secara otomatis diratakan (pitch dibatasi tidak boleh menukik ke bawah), dan jika jarak $< 3.5\text{ m}$, naga secara mulus menyusuri lereng bukit pulau tanpa pernah menembus geometri.
- **Plafon Maksimum:** `maxAltitude = 160f` (memungkinkan naga terbang bebas melintasi puncak gunung tertinggi $118.9\text{ m}$).

---

## 4. PROTOKOL JARINGAN UDP GANDA (DUAL-PORT UDP v5.0)

Modul Python dan Unity berkomunikasi melalui 2 port socket UDP terpisah berkecepatan tinggi:

```
[Python CV Sender]
   ├── UDP 127.0.0.1:5052 (Pose CSV Telemetri 21 Float) ──> [UDPPoseReceiver.cs]
   └── UDP 127.0.0.1:5053 (JPEG Frame PIP Video) ──────────> [InGameFlightHUD.cs]
```

### 4.1 Port 5052: Telemetri Pose Tubuh (21-Float CSV)
- **Host & Port:** `127.0.0.1:5052`
- **Frekuensi:** $\ge 30\text{ FPS}$ (latensi AI $\approx 10-15\text{ ms}$ pada CUDA GPU)
- **Format String CSV (21 nilai):**
  ```text
  LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y,MOUTH_OPEN,LE_X,LE_Y,RE_X,RE_Y,IS_DIVE,IS_FLAP,FLAP_FREQ,FLAP_POWER
  ```
  - `0..1` = Bahu Kiri (LS)
  - `2..3` = Bahu Kanan (RS)
  - `4..5` = Pergelangan Tangan Kiri (LW)
  - `6..7` = Pergelangan Tangan Kanan (RW)
  - `8..9` = Pinggul Kiri (LH)
  - `10..11` = Pinggul Kanan (RH)
  - `12` = Nilai Bukaan Mulut `MOUTH_OPEN` ($0.0 = \text{Tutup}, 1.0 = \text{Buka Lebar}$)
  - `13..14` = Siku Kiri (LE)
  - `15..16` = Siku Kanan (RE)
  - `17` = Flag Gestur Tuck Dive (`IS_DIVE`: $1.0$ jika aktif)
  - `18` = Flag Gestur Kepakan Sayap (`IS_FLAP`: $1.0$ jika aktif)
  - `19` = Frekuensi Kepakan (`FLAP_FREQ` dalam Hz)
  - `20` = Daya Dorong Kepakan (`FLAP_POWER`: $0.0 - 1.0$)

### 4.2 Port 5053: Streaming Video Webcam PIP (Picture-in-Picture)
- **Host & Port:** `127.0.0.1:5053`
- **Format Paket:** Raw byte buffer gambar JPEG terkompresi ($320 \times 180$ piksel, *quality* 48, ukuran paket $\approx 3-4\text{ KB} < 65\text{ KB}$ MTU UDP).
- **Fungsi di Unity:** Didekodekan langsung oleh `InGameFlightHUD.cs` menggunakan `Texture2D.LoadImage(bytes)` dan ditampilkan di kotak preview kanan atas layar.
- **Fallback Otomatis:** Jika Python video stream belum aktif, kotak PIP secara otomatis menampilkan radar kerangka (*interactive skeleton wireframe*) lengkap dengan sendi siku dan indikator mode Elytra.

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
- **Pemetaan Tombol Keyboard Elytra:**
  - **Kepakan Sayap (Fly Up + Speed Up):** `Spasi` atau `W`
  - **Tuck Dive (Terjun Menukik Tajam -45°):** `S`
  - **Meluncur Mendatar Elytra (-5° Glide):** `T` (atau lepas tombol)
  - **Arahkan Badan ke Atas (Climb):** `Panah Atas` atau `Y`
  - **Pitch Down Moderat:** `Panah Bawah`
  - **Kemudi Belok:** `Panah Kiri / Kanan` atau `A / D`
  - **Simulasi Aksi Desa:** Tombol `1` (Kepak Sayap), `2` / `F` (Semburan Air), `3` / `R` (Panggil Hujan)

---

## 7. STRUKTUR SCENE & FILE UTAMA

- **Scene Utama:** `Assets/_Scenes/Test_Dragon_Flight.unity` (Build Settings Index `0`).
- **Skrip C#:**
  - `Assets/_Scripts/Controllers/DragonFlightController.cs`: Pengendali penerbangan Minecraft Elytra 3D sejati, gravitasi, pertukaran energi kinetik, kepakan sayap, tuck dive, pitch/yaw/roll, dan auto-hover.
  - `Assets/_Scripts/CV_Receiver/IPoseProvider.cs`: Interface abstraksi penyedia pose (termasuk Tuck Dive, Flapping, dan Siku).
  - `Assets/_Scripts/CV_Receiver/UDPPoseReceiver.cs`: Penerima data pose UDP 5052 (21 float), smoothing, deteksi gestur Elytra, dan keyboard fallback zero-conflict.
  - `Assets/_Scripts/UI/InGameFlightHUD.cs`: GUI telemetri kiri atas (Airspeed, Pitch, Alt, Elytra Mode), kotak preview webcam PIP kanan atas (port 5053), radar kerangka bersiku, dan panduan kontrol bawah.
- **Skrip Python:**
  - `ARDragonSkyGuardian_CV/active_cv_sender.py`: Pengirim pose resmi YOLOv8n-pose CUDA GPU + deteksi geometri Tuck Dive foto pengguna + streaming video JPEG PIP.
  - `ARDragonSkyGuardian_CV/udp_sender.py`: Helper socket UDP data pose 21-float & video JPEG.
  - `ARDragonSkyGuardian_CV/test_send_dummy_udp.py`: Bench pengujian sintetis 4-fase Elytra (T-Pose -> Flap -> Tuck Dive -> Climb) tanpa kamera.
