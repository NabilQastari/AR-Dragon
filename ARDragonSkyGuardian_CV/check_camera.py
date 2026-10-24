"""
check_camera.py
Skrip untuk mendeteksi indeks webcam yang tersedia dan resolusi yang didukung di Windows.
"""

import cv2

COMMON_RESOLUTIONS = [
    (640, 480, "480p (4:3)"),
    (800, 600, "SVGA (4:3)"),
    (1280, 720, "720p HD (16:9)"),
    (1920, 1080, "1080p FHD (16:9)"),
]

def check_cameras(max_tested: int = 5):
    print("=" * 60)
    print("[*] MEMERIKSA DAFTAR KAMERA & RESOLUSI YANG DIDUKUNG")
    print("=" * 60)
    available_cameras = []

    for index in range(max_tested):
        # Coba CAP_DSHOW dulu, jika tidak terbuka coba default backend
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)

        if not cap.isOpened():
            cap.release()
            continue

        ret, frame = cap.read()
        if not ret or frame is None:
            cap.release()
            continue

        print(f"\n[+] Kamera terdeteksi pada Index: {index}")
        supported_res = []

        for width, height, label in COMMON_RESOLUTIONS:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if actual_w == width and actual_h == height:
                supported_res.append(f"{width}x{height} ({label})")
                print(f"    [OK] {width}x{height} - {label} [DIDUKUNG]")
            else:
                print(f"    [-]  {width}x{height} - {label} [Disesuaikan ke {actual_w}x{actual_h}]")

        fps = cap.get(cv2.CAP_PROP_FPS)
        backend = cap.getBackendName()
        print(f"    Backend: {backend} | Default FPS: {fps}")

        available_cameras.append({
            "index": index,
            "supported_resolutions": supported_res
        })
        cap.release()

    print("\n" + "=" * 60)
    if available_cameras:
        print(f"[SUCCESS] Total {len(available_cameras)} kamera aktif ditemukan.")
        for cam in available_cameras:
            print(f" - Kamera Index {cam['index']}: {len(cam['supported_resolutions'])} profil resolusi terverifikasi.")
    else:
        print("[NOTICE] Tidak ada kamera yang berhasil dibuka secara otomatis.")
        print("         Pastikan webcam terhubung atau tidak sedang digunakan aplikasi lain.")
    print("=" * 60)

if __name__ == "__main__":
    check_cameras()
