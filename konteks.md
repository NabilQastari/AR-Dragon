# 🐉 PROJECT CONTEXT & TECHNICAL BIBLE: AR DRAGON SKY GUARDIAN (v3.0 — SEMI-AUTONOMOUS)

> **Fungsi Dokumen:** Rujukan teknikal utama (*Single Source of Truth*) bagi kolaborasi antara Manusia (Developer) dan AI Agent (Hermes Agent).
> **Pasangan Dokumen:** Gunakan bersama `prd.md` untuk aliran kerja berperingkat.
> **Pembaruan Desain Pulau:** Pulau diubah dari pulau terapung menjadi **daratan abstrak besar (grounded)** dengan danau, hutan, dan bukit. Lihat bagian 2.4 dan 5. Penempatan 3 desa **belum final** dan akan dibahas terpisah.

---

## 1. RINGKASAN KONSEP & PEMBAHAGIAN PERANAN (HUMAN vs AI AGENT)

### 1.1 Identiti Gim
- **Nama Gim / Project Unity:** AR Dragon Sky Guardian (nama kode lama: Dragon Wing AR, dipakai pada menu Editor `DragonWingAR/...`)
- **Genre:** Exergaming PC berasaskan Webcam / 3D Flight Action / Pendidikan Alam Sekitar
- **Enjin & Stack:** Unity 2022.3 LTS (URP), Python 3.10+ (MediaPipe / YOLO-Pose / RTMPose), Blender 3.x/4.x
- **Watak Utama:** Naga Elemen Air & Embun Purba
- **Misi Utama:** Memulihkan 3 desa di sebuah pulau daratan besar daripada pencemaran udara, kebakaran hutan, dan kemarau sebelum masa tamat, menggunakan gerakan anggota badan bahagian atas di hadapan webcam.

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
4. **Desain Model Pulau: Daratan Abstrak Besar (Grounded, Semi-Open-World):**
   - **Bentuk:** Daratan besar dengan siluet abstrak (organik, tidak bulat, tidak simetris). Tepinya berupa potongan rata seperti blok *terrain* (cutaway slab) di atas latar polos. **Bukan pulau terapung**, tanpa laut di sekelilingnya, tanpa air terjun, dan tanpa batu satelit melayang.
   - **Skala:** Sangat besar dan terasa luas, sehingga pohon individual tampak kecil seperti dunia miniatur yang dilihat dari ketinggian. Tujuannya agar pemain bisa berpetualang jauh (semi-open-world), bukan area padat dan sempit. Angka ukuran detail ada di bagian 2.5.
   - **Fitur lanskap:**
     - **Danau:** 3 danau besar/sedang dengan bentuk organik, tersebar tidak beraturan (danau kecil tidak dipakai). **Tidak ada sungai** (menggantikan "1 aliran sungai utama" pada versi sebelumnya).
     - **Hutan:** Beberapa petak hutan pinus/ek low-poly dengan ukuran bervariasi, ditempatkan acak (ada yang rapat, ada yang jarang, ditambah pohon tunggal di sela-selanya).
     - **Bukit:** 7 bukit besar dan punggungan berbatu dengan ketinggian berbeda (bukit kecil tidak dipakai).
     - **Padang rumput:** Area terbuka luas di antara semua fitur, dengan sedikit singkapan batu. Ruang lega, tidak penuh sesak.
   - **Penempatan Desa/Zona:** Posisi Desa 1, 2, dan 3 dibuat **lebih acak** dan berada di **bagian dalam daratan**, tidak di tepi. Ukuran desa dan hutan tetap kompak (tidak ikut membesar mengikuti skala daratan). **Desain detail desa dibahas pada tahap berikutnya**; model daratan saat ini dibuat **tanpa desa dan tanpa bangunan**.
   - **Gaya visual:** Stylized low-poly (gaya Unreal Engine), siang cerah, warna cerah, *soft ambient occlusion*, tata letak bersih dan mudah dibaca, minim kekacauan visual.

5. **Spesifikasi Ukuran Daratan (1 Unity unit = 1 meter):**

   **a. Dimensi total daratan**

   | Parameter | Nilai |
   | :--- | :--- |
   | Bounding box (panjang x lebar) | 800 m (X) x 800 m (Z), **rasio 1:1**, pusat di (0, 0, 0) |
   | Luas daratan | ±640.000 m² (±0,64 km²) |
   | Tebal blok terrain (potongan tepi) | ±20 m dari permukaan ke dasar, tepi vertikal rata |
   | Ketinggian dasar permukaan | Y = 0 (permukaan datar acuan) |
   | Jarak zona dari tepi | Minimal 100 m dari tepi daratan |
   | Greybox `Island_Root` | Plane Unity (10x10 unit default) dengan Scale (80, 1, 80) = 800 x 800 m |

   **b. Danau** (hanya yang besar/sedang: 3 danau, total ±6-8% dari luas daratan; danau kecil tidak dipakai)

   | Kategori | Jumlah | Diameter | Kedalaman visual |
   | :--- | :-: | :-: | :-: |
   | Besar | 2 | 150-200 m | ±3 m |
   | Sedang | 1 | 100-120 m | ±2,5 m |

   Bentuk organik (tidak bulat sempurna). Permukaan air sedikit di bawah permukaan tanah. Posisi dan ukuran rinci: `GDD_Pulau.md` bagian 4.2.

   **c. Bukit dan punggungan** (hanya bukit besar: 7 bukit dengan diameter alas ≥ 90 m; bukit kecil tidak dipakai)

   | Kategori | Jumlah | Diameter alas | Tinggi puncak |
   | :--- | :-: | :-: | :-: |
   | Besar (berbatu) | 7 | 90-150 m | 6-12 m |

   Posisi dan ukuran rinci: `GDD_Pulau.md` bagian 4.3.

   > ⚠️ **Batas tinggi bukit:** Naga terbang pada ketinggian tetap `fixedY = 15f` dan belum ada logika menghindari medan. Maka tinggi puncak bukit dibatasi **maksimal 12 m** agar tidak menembus naga. Jika ingin gunung lebih tinggi, naikkan `fixedY` (misalnya 30-40 m) atau tambahkan penyesuaian ketinggian terhadap medan.

   **d. Hutan** (6-8 petak)

   | Kategori | Jumlah | Diameter petak | Kepadatan pohon |
   | :--- | :-: | :-: | :-: |
   | Besar | 1-2 | 180-220 m | Rapat (jarak antar-pohon 4-6 m) |
   | Sedang | 2-3 | 100-150 m | Sedang (6-10 m) |
   | Kecil | 3 | 40-70 m | Jarang (12-20 m) |

   - **Pohon:** pinus tinggi 8-10 m (lebar tajuk 3-4 m), ek tinggi 6-8 m (lebar tajuk 4-5 m). Rasio pohon terhadap lebar daratan ±1:100, sehingga pohon tampak kecil.
   - **Pohon tunggal:** ±30-50 pohon tersebar di padang rumput.

   **e. Desa dan zona tantangan** (ukuran tetap kompak, tidak ikut membesar)

   | Parameter | Nilai |
   | :--- | :--- |
   | Diameter desa / area zona | ±36-50 m (sesuai trigger `SphereCollider` radius 18 m, ditambah area sekitar) |
   | Jarak minimal antar-desa | 250 m |
   | Jarak minimal desa ke tepi daratan | 100 m |
   | Zona Desa 2 (hutan kebakaran) | Petak hutan sedang, diameter 60-100 m, dengan titik pusat api |
   | Estimasi waktu terbang antar-desa | ±20-25 detik (250-300 m pada `forwardSpeed = 12f`) |

   Posisi final desa masih menunggu pembahasan desain desa (lihat bagian 5).

   **f. Jalur dan elemen lain**

   | Elemen | Ukuran |
   | :--- | :--- |
   | Jalan setapak tanah (opsional, jika dipakai) | Lebar 4-6 m, menghubungkan antar-zona |
   | Singkapan batu kecil | 2-6 m, ±40 buah tersebar |
   | Padang rumput | Mengisi sisa luas (±50% daratan), tanpa objek besar |

   **g. Cek kelayakan waktu level:** Level 3 (210 detik) dengan 3 desa membutuhkan ±15 detik aksi pemulihan dan ±55-70 detik terbang (total jalur ±650-800 m), sehingga masih ada ruang untuk belok dan penyesuaian arah. Jika terasa terlalu longgar atau terlalu sempit saat uji, ubah jarak antar-desa atau `forwardSpeed`, bukan ukuran desa.

---

## 3. SPESIFIKASI JARINGAN UDP & PEMETAAN TITIK TUBUH (COMPUTER VISION)

### 3.1 Protokol Paket Data UDP
- **Host & Port:** `127.0.0.1` (Localhost), Port **`5052`**
- **Kadar Penghantaran:** >= 30 FPS
- **Format String CSV (12 nilai float ternormalisasi `0.0000` hingga `1.0000`):**

```text
LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y
```

- `parts[0..1]` = Bahu Kiri (LS.x, LS.y) | `parts[2..3]` = Bahu Kanan (RS.x, RS.y)
- `parts[4..5]` = Pergelangan Tangan Kiri (LW.x, LW.y) | `parts[6..7]` = Pergelangan Tangan Kanan (RW.x, RW.y)
- `parts[8..9]` = Pinggul Kiri (LH.x, LH.y) | `parts[10..11]` = Pinggul Kanan (RH.x, RH.y)

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
| **Desa 2 (Wildfire)** | Sembur Air | Rapatkan kedua-dua pergelangan tangan di hadapan dada | Sah jika `Vector2.Distance(LW, RW) < 0.14f` dan tangan di antara paras bahu dan pinggul (`LW.y > LS.y - 0.05f && LW.y < LH.y`). |
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

- **Pulau Utama (`Island_Root`):** Posisi (0, 0, 0), Skala (80, 1, 80) pada greybox Plane (model final: Skala (1, 1, 1) dengan ukuran asli 800 x 800 m). Berupa daratan besar yang grounded (lihat 2.4), bukan pulau terapung. Ukuran total 800 x 800 m, rasio 1:1 (rincian di bagian 2.5), jauh lebih luas dari versi awal sehingga jarak antar-zona lebih jauh.
- **Naga Pemain (`Dragon_Player`):** Posisi mula (0, 15, -80), Rotasi (0, 0, 0).
  - `Main Camera` sebagai child kepada `Dragon_Player` pada `localPosition` (0, 4, -12) dan `localEulerAngles` (12, 0, 0).
- **Lokasi 3 Desa** (`SphereCollider`, `IsTrigger = true`, `Radius = 18f`):
  - > ⚠️ **Koordinat di bawah bersifat SEMENTARA (placeholder greybox).** Karena daratan diperbesar dan posisi desa dibuat acak di bagian dalam pulau, koordinat final akan ditetapkan setelah desain desa dibahas. Perbarui bagian ini saat sudah final.
  - `Village_1_Pollution`: Posisi (200, 2, -80)
  - `Village_2_Wildfire`: Posisi (-10, 2, 133)
  - `Village_3_Drought`: Posisi (-260, 2, -13)
