"""
test_yolopose.py
Pengujian interaktif YOLOv8n-pose dengan akselerasi GPU CUDA + UDP Sender.
Resolusi target: 1280x720 @ 30 FPS, horizontal flip cv2.flip(frame, 1).
Indeks titik COCO (17 Keypoints):
  LS: 5 (Left Shoulder)
  RS: 6 (Right Shoulder)
  LW: 9 (Left Wrist)
  RW: 10 (Right Wrist)
  LH: 11 (Left Hip)
  RH: 12 (Right Hip)
"""

import os
import sys
import time
import tempfile
import cv2
import numpy as np
import torch

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()
from ultralytics import YOLO
from udp_sender import PoseUDPSender

def main():
    model_path = os.path.join(os.path.dirname(__file__), "yolov8n-pose.pt")
    if not os.path.exists(model_path):
        print(f"[!] Model {model_path} tidak ditemukan!")
        return

    # Inisialisasi YOLOv8n-pose
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[*] Memuat YOLO-Pose pada perangkat: {device}...")
    model = YOLO(model_path)
    if device.startswith("cuda"):
        model.to(device)

    # Inisialisasi UDP Sender
    sender = PoseUDPSender(ip="127.0.0.1", port=5052)

    # Buka webcam
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
    print(f"🚀 MENJALANKAN UJI YOLO-POSE (Device: {device})")
    print("   - Resolusi target: 720p (1280x720)")
    print("   - Mengirim UDP ke 127.0.0.1:5052")
    print("   - Tekan 'q' atau ESC pada jendela video untuk keluar")
    print("=" * 60)

    prev_time = time.time()
    fps_history = []

    # Indeks keypoint COCO
    IDX_LS, IDX_RS = 5, 6
    IDX_LW, IDX_RW = 9, 10
    IDX_LH, IDX_RH = 11, 12

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        # Wajib dibalik horizontal agar natural seperti cermin
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        t_start = time.perf_counter()

        # Inferensi YOLO-Pose
        results = model(frame, device=device, verbose=False, conf=0.35)
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        # Koordinat default
        ls = (0.45, 0.40)
        rs = (0.55, 0.40)
        lw = (0.35, 0.55)
        rw = (0.65, 0.55)
        lh = (0.45, 0.70)
        rh = (0.55, 0.70)

        pose_detected = False
        if results and len(results) > 0 and results[0].keypoints is not None:
            kpts_data = results[0].keypoints.data
            if kpts_data is not None and len(kpts_data) > 0:
                kpts = kpts_data[0].cpu().numpy()  # Bentuk: (17, 3) -> [x, y, conf]
                if len(kpts) >= 13:
                    pose_detected = True
                    # Normalisasi piksel ke rentang 0.0 - 1.0
                    ls = (float(kpts[IDX_LS][0]) / w, float(kpts[IDX_LS][1]) / h)
                    rs = (float(kpts[IDX_RS][0]) / w, float(kpts[IDX_RS][1]) / h)
                    lw = (float(kpts[IDX_LW][0]) / w, float(kpts[IDX_LW][1]) / h)
                    rw = (float(kpts[IDX_RW][0]) / w, float(kpts[IDX_RW][1]) / h)
                    lh = (float(kpts[IDX_LH][0]) / w, float(kpts[IDX_LH][1]) / h)
                    rh = (float(kpts[IDX_RH][0]) / w, float(kpts[IDX_RH][1]) / h)

                    # Kirim paket UDP
                    sender.send_pose(ls, rs, lw, rw, lh, rh)

                    # Gambar rangka tubuh (Skeleton Overlay)
                    def to_px(pt):
                        return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                    p_ls, p_rs = to_px(ls), to_px(rs)
                    p_lw, p_rw = to_px(lw), to_px(rw)
                    p_lh, p_rh = to_px(lh), to_px(rh)

                    color_line = (0, 255, 180)
                    thickness = 3
                    cv2.line(frame, p_ls, p_rs, color_line, thickness)
                    cv2.line(frame, p_ls, p_lw, color_line, thickness)
                    cv2.line(frame, p_rs, p_rw, color_line, thickness)
                    cv2.line(frame, p_ls, p_lh, color_line, thickness)
                    cv2.line(frame, p_rs, p_rh, color_line, thickness)
                    cv2.line(frame, p_lh, p_rh, color_line, thickness)

                    # Titik Bahu
                    cv2.circle(frame, p_ls, 8, (0, 255, 255), -1)
                    cv2.circle(frame, p_rs, 8, (0, 255, 255), -1)

                    # Titik Pergelangan Tangan
                    cv2.circle(frame, p_lw, 10, (255, 0, 255), -1)
                    cv2.circle(frame, p_rw, 10, (0, 255, 0), -1)

                    # Titik Pinggul
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

        # HUD Overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (20, 20), (450, 155), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        cv2.putText(frame, f"Model: YOLOv8n-pose ({device})", (30, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi: {latency_ms:.1f} ms", (30, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 0), 2)

        status_str = "Tubuh Terdeteksi [UDP ON]" if pose_detected else "Mencari Tubuh..."
        status_col = (0, 255, 0) if pose_detected else (0, 0, 255)
        cv2.putText(frame, f"Status: {status_str}", (30, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_col, 2)

        tilt = lw[1] - rw[1]
        dist = np.sqrt((lw[0] - rw[0])**2 + (lw[1] - rw[1])**2)
        cv2.putText(frame, f"Tilt: {tilt:+.2f}  |  Jarak Tangan: {dist:.2f}", (30, 135),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1)

        cv2.imshow("AR Dragon - YOLO-Pose Test", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    sender.close()
    print("[*] Selesai pengujian YOLO-Pose.")

if __name__ == "__main__":
    main()
