# 🐉 PROJECT CONTEXT & TECHNICAL BIBLE: AR DRAGON SKY GUARDIAN (v3.0 — SEMI-AUTONOMOUS)

> **Fungsi Dokumen:** Rujukan teknikal utama (*Single Source of Truth*) bagi kolaborasi antara Manusia (Developer) dan AI Agent (Hermes Agent).
> **Pasangan Dokumen:** Gunakan bersama `prd.md` untuk aliran kerja berperingkat.

---

## 1. RINGKASAN KONSEP & PEMBAHAGIAN PERANAN (HUMAN vs AI AGENT)

### 1.1 Identiti Gim
- **Nama Gim / Project Unity:** AR Dragon Sky Guardian (nama kode lama: Dragon Wing AR, dipakai pada menu Editor `DragonWingAR/...`)
- **Genre:** Exergaming PC berasaskan Webcam / 3D Flight Action / Pendidikan Alam Sekitar
- **Enjin & Stack:** Unity 2022.3 LTS (URP), Python 3.10+ (MediaPipe / YOLO-Pose / RTMPose), Blender 3.x/4.x
- **Watak Utama:** Naga Elemen Air & Embun Purba
- **Misi Utama:** Memulihkan 3 desa di sebuah pulau terapung daripada pencemaran udara, kebakaran hutan, dan kemarau sebelum masa tamat, menggunakan gerakan anggota badan bahagian atas di hadapan webcam.

### 1.2 Matriks Pembahagian Tugas (Semi-Autonomous Workflow)

| Kategori Tugas | Pelaksana Utama | Kewajiban Kolaborasi |
| :--- | :--- | :--- |
| **Skrip Python CV & Benchmark UDP** | 🤖 **Hermes Agent** | Agent menulis kod penuh; Manusia menjalankan ujian webcam & memilih model terbaik. |
| **Skrip C# Unity (UDP, Terbang, Gestur, UI, GameManager)** | 🤖 **Hermes Agent** | Agent menulis keseluruhan kod C# bebas ralat (*0 Compiler Errors*). |
| **Skrip Pembantu Editor (`[MenuItem]`)** | 🤖 **Hermes Agent** | Untuk tugas penyusunan komponen yang sukar diakses terus oleh Agent, Agent menyediakan menu automatik di bar atas Unity (`DragonWingAR -> Setup...`) atau memberi tutorial lengkap. |
| **Import Aset 3D (`.fbx`), Rigging, & Penataan Visual Scene** | 👨‍💻 **Manusia (User)** | Agent **WAJIB** memberikan tutorial langkah demi langkah (klik menu apa, letak di folder mana, ubah tetapan Inspector apa). |
| **Ujian Play Mode, Kalibrasi Webcam, & Build Akhir** | 👨‍💻 **Manusia (User)** | Manusia menguji permainan secara langsung dan memberi maklum balas kepada Agent. |

---

## 2. PRINSIP "PRODUKSI MUDAH & ANTI-BUG"

1. **Satu Scene Pulau untuk Semua Level (`2_MainIslandScene.unity`):**
   - Hanya 1 Scene pulau utama yang mengandungi Desa 1, Desa 2, dan Desa 3.
   - `GameManager.cs` mengawal status aktif desa (`SetActive(true/false)`) berdasarkan level yang dipilih dari `1_LobbyScene.unity`.
2. **Tiada Aset 3D Berganda (Rosak vs Pulih):** Gunakan 1 set model 3D bagi setiap desa, dan ubah keadaannya melalui kod C#:
   - **Desa 1 (Polusi Udara):** Kurangkan `emission.rateOverTime` pada *Particle System* asap hitam daripada `50f` kepada `0f` mengikut peratusan progres desa (`0% -> 100%`).
   - **Desa 2 (Kebakaran Hutan):** Kecilkan `transform.localScale` pada *Particle System* api daripada `Vector3.one` kepada `Vector3.zero` mengikut progres desa.
   - **Desa 3 (Kekeringan Tanah):** Tukar warna *Material* tanah dan pokok daripada coklat kering (`#8B5A2B`) kepada hijau subur (`#2E8B57`) menggunakan `Color.Lerp(dryColor, lushColor, localProgress / 100f)`.
3. **Penerbangan Semi-Automatik (*Auto-Forward & Fixed Altitude*):**
   - Naga terbang ke hadapan secara automatik (`forwardSpeed = 12f`) pada ketinggian tetap (`fixedY = 15f`).
   - Pemain hanya mengawal belok kiri/kanan di luar zon desa.
   - Apabila masuk ke *Trigger Collider* desa yang belum selesai (`localProgress < 100f`), naga automatik berhenti bergerak ke hadapan (**Auto-Hover**) dan menghadap ke pusat desa supaya pemain fokus melakukan gestur tangan.

---

## 3. SPESIFIKASI JARINGAN UDP & PEMETAAN TITIK TUBUH (COMPUTER VISION)

### 3.1 Protokol Paket Data UDP
- **Host & Port:** `127.0.0.1` (Localhost), Port **`5052`**
- **Kadar Penghantaran:** >= 30 FPS
- **Format String CSV (13 nilai float ternormalisasi `0.0000` hingga `1.0000`):**

```text
LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y,MOUTH_OPEN
```

- `parts[0..1]` = Bahu Kiri (LS.x, LS.y) | `parts[2..3]` = Bahu Kanan (RS.x, RS.y)
- `parts[4..5]` = Pergelangan Tangan Kiri (LW.x, LW.y) | `parts[6..7]` = Pergelangan Tangan Kanan (RW.x, RW.y)
- `parts[8..9]` = Pinggul Kiri (LH.x, LH.y) | `parts[10..11]` = Pinggul Kanan (RH.x, RH.y)
- `parts[12]` = Status Mulut Terbuka (`0.0000` = tertutup rapat, `1.0000` = terbuka lebar / `jawOpen`)

### 3.2 Konvensi Koordinat Skrin (Wajib Seragam)
- Imej webcam di Python wajib diterbalikkan secara mendatar (`cv2.flip(frame, 1)`).
- **Paksi X:** 0.0 (Kiri Skrin) hingga 1.0 (Kanan Skrin).
- **Paksi Y:** 0.0 (Atas Skrin) hingga 1.0 (Bawah Skrin). Semakin tinggi tangan diangkat ke atas kepala, semakin **KECIL** nilai Y.

### 3.3 Indeks Keypoint Mengikut Framework CV
| Framework | LS | RS | LW | RW | LH | RH |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: |
| MediaPipe Pose (33 titik) | 11 | 12 | 15 | 16 | 23 | 24 |
| YOLO-Pose / YOLOv8n-pose (17 titik COCO) | 5 | 6 | 9 | 10 | 11 | 12 |
| RTMPose via rtmlib (17 titik COCO) | 5 | 6 | 9 | 10 | 11 | 12 |

---

## 4. RUMUS MATEMATIK GESTUR & PROGRES PERMAINAN DI UNITY

Semua titik yang diterima melalui `UDPPoseReceiver.cs` wajib dilicinkan (*smoothing*) setiap frame:

```csharp
smoothedPoint = Vector2.Lerp(smoothedPoint, rawPoint, Time.deltaTime * 12f);
```

### 4.1 Kawalan Terbang (Di Luar Zon Desa)
- Kira perbezaan ketinggian tangan: `float tiltDelta = LeftWrist.y - RightWrist.y;`
- **Meluncur Lurus (Pose T):** jika `Mathf.Abs(tiltDelta) < 0.08f`, maka `turnInput = 0f`.
- **Belok Kiri / Kanan:** jika `Mathf.Abs(tiltDelta) >= 0.08f`, maka `turnInput = Mathf.Clamp(tiltDelta * 2.5f, -1f, 1f)`.
  - Putaran arah (Yaw): `transform.Rotate(Vector3.up * turnInput * 65f * Time.deltaTime)`.
  - Condong badan visual (Roll): `visualModel.localRotation` dicondongkan pada paksi Z sebanyak `-turnInput * 35f`.

### 4.2 Kawalan Aksi Pemulihan (Di Dalam Trigger Collider Desa — Auto-Hover)
Kadar kenaikan progres lokal desa apabila gestur sah: `+20f * Time.deltaTime` (5 saat aksi penuh = 100% selesai).

| Desa & Masalah | Aksi Naga | Gestur Pemain | Logik Pengesanan C# |
| :--- | :--- | :--- | :--- |
| **Desa 1 (Pollution)** | Mengipas Asap | Kepakkan kedua-dua tangan naik-turun merentasi paras bahu | `bool isAbove = (LW.y < LS.y) && (RW.y < RS.y);` Setiap kali `isAbove != prevIsAbove`, tetapkan `flapTimer = 0.6f`. Gestur sah selagi `flapTimer > 0f`. |
| **Desa 2 (Wildfire)** | Sembur Air | Buka Mulut Lebar (Naga Mengaum) ATAU Rapatkan pergelangan tangan di dada | Sah jika `mouthOpen >= 0.35f` ATAU (`Vector2.Distance(LW, RW) < 0.14f` dan tangan di antara paras bahu dan pinggul). Partikel semburan air aktif di mulut naga. |
| **Desa 3 (Drought)** | Panggil Hujan Embun | Angkat kedua-dua tangan tinggi di atas kepala (huruf V / Y) | Sah jika kedua-dua pergelangan tangan jauh di atas bahu (`LW.y < LS.y - 0.12f && RW.y < RS.y - 0.12f`). |

### 4.3 Struktur Level, Masa, & Bintang

| Level | Desa Aktif | Masa | Pemberat Progres Global | Syarat Buka Kunci |
| :--- | :--- | :-: | :-: | :--- |
| Level 1 | Desa 1 | 90 saat | 100% setiap desa | Terbuka sejak mula |
| Level 2 | Desa 1 + Desa 2 | 150 saat | 50% setiap desa | Bintang Level 1 >= 1 |
| Level 3 | Desa 1 + Desa 2 + Desa 3 | 210 saat | 33.33% setiap desa | Bintang Level 2 >= 1 |

**Penilaian Bintang:**
- `GlobalProgress >= 100%` (sebelum masa tamat) = **3 Bintang** (buka level seterusnya).
- Masa tamat & `GlobalProgress >= 67%` = **2 Bintang** (buka level seterusnya).
- Masa tamat & `GlobalProgress >= 34%` = **1 Bintang** (buka level seterusnya).
- Masa tamat & `GlobalProgress < 34%` = **0 Bintang / Gagal** (level seterusnya kekal terkunci).

---

## 5. KOORDINAT PIAWAI OBJEK DI `2_MainIslandScene.unity`

- **Pulau Utama (`Island_Root`):** Posisi (0, 0, 0), Skala (1, 1, 1).
- **Naga Pemain (`Dragon_Player`):** Posisi mula (0, 15, -80), Rotasi (0, 0, 0).
  - `Main Camera` sebagai child kepada `Dragon_Player` pada `localPosition` (0, 4, -12) dan `localEulerAngles` (12, 0, 0).
- **Lokasi 3 Desa** (`SphereCollider`, `IsTrigger = true`, `Radius = 18f`):
  - `Village_1_Pollution`: Posisi (-35, 2, -10)
  - `Village_2_Wildfire`: Posisi (40, 2, 20)
  - `Village_3_Drought`: Posisi (0, 2, 65)
