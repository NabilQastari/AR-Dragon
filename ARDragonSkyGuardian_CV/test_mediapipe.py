"""
test_mediapipe.py
Pengujian interaktif MediaPipe Pose Landmarker + UDP Sender.
Resolusi target: 1280x720 @ 30 FPS, horizontal flip cv2.flip(frame, 1).
Indeks titik MediaPipe:
  LS: 11 (Left Shoulder)
  RS: 12 (Right Shoulder)
  LW: 15 (Left Wrist)
  RW: 16 (Right Wrist)
  LH: 23 (Left Hip)
  RH: 24 (Right Hip)
"""

import os
import sys
import time
import tempfile
import cv2
import numpy as np

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from udp_sender import PoseUDPSender

def main():
    model_path = os.path.join(os.path.dirname(__file__), "pose_landmarker_lite.task")
    if not os.path.exists(model_path):
        print(f"[!] Error: Model file '{model_path}' tidak ditemukan.")
        return

    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        output_segmentation_masks=False,
        running_mode=vision.RunningMode.IMAGE
    )
    detector = vision.PoseLandmarker.create_from_options(options)

    # Inisialisasi UDP Sender
    sender = PoseUDPSender(ip="127.0.0.1", port=5052)

    # Buka webcam (coba CAP_DSHOW terlebih dahulu, fallback ke default)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("[!] Gagal membuka webcam.")
        return

    print("=" * 60)
    print("🚀 MENJALANKAN UJI MEDIAPIPE POSE")
    print("   - Resolusi target: 720p (1280x720)")
    print("   - Mengirim UDP ke 127.0.0.1:5052")
    print("   - Tekan 'q' atau ESC pada jendela video untuk keluar")
    print("=" * 60)

    prev_time = time.time()
    fps_history = []

    # Indeks keypoint MediaPipe
    IDX_LS, IDX_RS = 11, 12
    IDX_LW, IDX_RW = 15, 16
    IDX_LH, IDX_RH = 23, 24

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        # Wajib dibalik horizontal agar natural seperti cermin
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        t_start = time.perf_counter()

        # Konversi ke MediaPipe Image format
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Inferensi Pose
        detection_result = detector.detect(mp_image)
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        # Koordinat default tengah jika tidak terdeteksi
        ls = (0.45, 0.40)
        rs = (0.55, 0.40)
        lw = (0.35, 0.55)
        rw = (0.65, 0.55)
        lh = (0.45, 0.70)
        rh = (0.55, 0.70)

        pose_detected = False
        if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
            landmarks = detection_result.pose_landmarks[0]
            if len(landmarks) > max(IDX_LH, IDX_RH):
                pose_detected = True
                ls = (landmarks[IDX_LS].x, landmarks[IDX_LS].y)
                rs = (landmarks[IDX_RS].x, landmarks[IDX_RS].y)
                lw = (landmarks[IDX_LW].x, landmarks[IDX_LW].y)
                rw = (landmarks[IDX_RW].x, landmarks[IDX_RW].y)
                lh = (landmarks[IDX_LH].x, landmarks[IDX_LH].y)
                rh = (landmarks[IDX_RH].x, landmarks[IDX_RH].y)

                # Kirim paket UDP
                sender.send_pose(ls, rs, lw, rw, lh, rh)

                # Gambar rangka tubuh (Skeleton Overlay)
                def to_px(pt):
                    return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                p_ls, p_rs = to_px(ls), to_px(rs)
                p_lw, p_rw = to_px(lw), to_px(rw)
                p_lh, p_rh = to_px(lh), to_px(rh)

                # Garis penghubung tubuh (Cyan / Biru Muda)
                color_line = (255, 200, 0)
                thickness = 3
                cv2.line(frame, p_ls, p_rs, color_line, thickness)
                cv2.line(frame, p_ls, p_lw, color_line, thickness)
                cv2.line(frame, p_rs, p_rw, color_line, thickness)
                cv2.line(frame, p_ls, p_lh, color_line, thickness)
                cv2.line(frame, p_rs, p_rh, color_line, thickness)
                cv2.line(frame, p_lh, p_rh, color_line, thickness)

                # Titik Bahu (Kuning)
                cv2.circle(frame, p_ls, 8, (0, 255, 255), -1)
                cv2.circle(frame, p_rs, 8, (0, 255, 255), -1)

                # Titik Pergelangan Tangan (Merah/Magenta untuk kiri, Hijau untuk kanan)
                cv2.circle(frame, p_lw, 10, (255, 0, 255), -1)
                cv2.circle(frame, p_rw, 10, (0, 255, 0), -1)

                # Titik Pinggul (Oranye)
                cv2.circle(frame, p_lh, 7, (0, 165, 255), -1)
                cv2.circle(frame, p_rh, 7, (0, 165, 255), -1)

        # Hitung FPS
        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 30.0
        prev_time = curr_time
        fps_history.append(fps)
        if len(fps_history) > 30:
            fps_history.pop(0)
        avg_fps = sum(fps_history) / len(fps_history)

        # HUD Overlay (Panel Informasi)
        overlay = frame.copy()
        cv2.rectangle(overlay, (20, 20), (450, 155), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Teks HUD
        cv2.putText(frame, "Model: MediaPipe Pose (CPU Lite)", (30, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi: {latency_ms:.1f} ms", (30, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 0), 2)

        status_str = "Tubuh Terdeteksi [UDP ON]" if pose_detected else "Mencari Tubuh..."
        status_col = (0, 255, 0) if pose_detected else (0, 0, 255)
        cv2.putText(frame, f"Status: {status_str}", (30, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_col, 2)

        # Analisis gestur cepat di HUD
        tilt = lw[1] - rw[1]
        dist = np.sqrt((lw[0] - rw[0])**2 + (lw[1] - rw[1])**2)
        cv2.putText(frame, f"Tilt: {tilt:+.2f}  |  Jarak Tangan: {dist:.2f}", (30, 135),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1)

        cv2.imshow("AR Dragon - MediaPipe Pose Test", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    sender.close()
    print("[*] Selesai pengujian MediaPipe Pose.")

if __name__ == "__main__":
    main()
