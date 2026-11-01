"""
test_yolopose.py
Pengujian interaktif YOLOv8n-pose dengan akselerasi GPU CUDA + High Performance Stream + Adaptive Stabilizer.
- Menggunakan ThreadedCamera (MJPG codec, Zero Buffer Lag)
- Menggunakan PoseStabilizer (One-Euro Filter untuk presisi tinggi & anti-jitter)
- Mengirimkan 12-float CSV via UDP ke Unity (127.0.0.1:5052)
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
from camera_stream import ThreadedCamera
from pose_stabilizer import PoseStabilizer

def main():
    model_path = os.path.join(os.path.dirname(__file__), "yolov8n-pose.pt")
    if not os.path.exists(model_path):
        print(f"[!] Model {model_path} tidak ditemukan!")
        return

    # Inisialisasi YOLOv8n-pose pada CUDA
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[*] Memuat YOLO-Pose pada perangkat: {device}...")
    model = YOLO(model_path)
    if device.startswith("cuda"):
        model.to(device)

    # Inisialisasi UDP Sender & Stabilizer
    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    stabilizer = PoseStabilizer(min_cutoff=1.5, beta=0.08)

    # Inisialisasi Kamera dengan Bufferless Stream (Anti-Delay)
    print("[*] Mengaktifkan Kamera Berkecapatan Tinggi (MJPG 30 FPS)...")
    cam = ThreadedCamera(src=0, width=1280, height=720, fps=30)
    time.sleep(0.5)

    print("=" * 65)
    print(f"🚀 MENJALANKAN UJI YOLO-POSE OPTIMAL (Device: {device})")
    print("   - Kamera : Threaded Zero-Lag Stream (MJPG)")
    print("   - Filter : Adaptive One-Euro Pose Stabilizer (Anti-Jitter)")
    print("   - UDP    : 127.0.0.1:5052")
    print("   - Tekan 'q' atau ESC untuk keluar")
    print("=" * 65)

    prev_time = time.time()
    fps_history = []

    # Indeks keypoint COCO
    IDX_LS, IDX_RS = 5, 6
    IDX_LW, IDX_RW = 9, 10
    IDX_LH, IDX_RH = 11, 12

    try:
        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue

            # Mirror horizontal
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            t_start = time.perf_counter()

            # Inferensi YOLO-Pose (resolusi inferensi 640 untuk presisi maksimal)
            results = model(frame, device=device, imgsz=640, verbose=False, conf=0.30)
            latency_ms = (time.perf_counter() - t_start) * 1000.0

            pose_detected = False
            if results and len(results) > 0 and results[0].keypoints is not None:
                kpts_data = results[0].keypoints.data
                if kpts_data is not None and len(kpts_data) > 0:
                    kpts = kpts_data[0].cpu().numpy()  # (17, 3) -> [x, y, conf]
                    if len(kpts) >= 13:
                        pose_detected = True

                        # Ambil koordinat mentah dan confidence
                        def get_pt(idx):
                            return float(kpts[idx][0]) / w, float(kpts[idx][1]) / h, float(kpts[idx][2])

                        raw_ls_x, raw_ls_y, c_ls = get_pt(IDX_LS)
                        raw_rs_x, raw_rs_y, c_rs = get_pt(IDX_RS)
                        raw_lw_x, raw_lw_y, c_lw = get_pt(IDX_LW)
                        raw_rw_x, raw_rw_y, c_rw = get_pt(IDX_RW)
                        raw_lh_x, raw_lh_y, c_lh = get_pt(IDX_LH)
                        raw_rh_x, raw_rh_y, c_rh = get_pt(IDX_RH)

                        # Stabilisasi adaptif (Menghilangkan jitter dan delay)
                        ls = stabilizer.update_point("ls", raw_ls_x, raw_ls_y, c_ls)
                        rs = stabilizer.update_point("rs", raw_rs_x, raw_rs_y, c_rs)
                        lw = stabilizer.update_point("lw", raw_lw_x, raw_lw_y, c_lw)
                        rw = stabilizer.update_point("rw", raw_rw_x, raw_rw_y, c_rw)
                        lh = stabilizer.update_point("lh", raw_lh_x, raw_lh_y, c_lh)
                        rh = stabilizer.update_point("rh", raw_rh_x, raw_rh_y, c_rh)

                        # Kirim paket UDP real-time
                        sender.send_pose(ls, rs, lw, rw, lh, rh)

                        # Visualisasi Skeleton Overlay
                        def to_px(pt):
                            return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                        p_ls, p_rs = to_px(ls), to_px(rs)
                        p_lw, p_rw = to_px(lw), to_px(rw)
                        p_lh, p_rh = to_px(lh), to_px(rh)

                        # Tulang lengan & badan
                        color_bone = (0, 230, 255)
                        cv2.line(frame, p_ls, p_rs, color_bone, 3)
                        cv2.line(frame, p_ls, p_lw, color_bone, 3)
                        cv2.line(frame, p_rs, p_rw, color_bone, 3)
                        cv2.line(frame, p_ls, p_lh, color_bone, 3)
                        cv2.line(frame, p_rs, p_rh, color_bone, 3)
                        cv2.line(frame, p_lh, p_rh, color_bone, 3)

                        # Titik sendi
                        cv2.circle(frame, p_ls, 8, (0, 255, 255), -1)
                        cv2.circle(frame, p_rs, 8, (0, 255, 255), -1)
                        cv2.circle(frame, p_lw, 11, (255, 0, 200), -1)
                        cv2.circle(frame, p_rw, 11, (0, 255, 0), -1)
                        cv2.circle(frame, p_lh, 7, (0, 165, 255), -1)
                        cv2.circle(frame, p_rh, 7, (0, 165, 255), -1)

                        # Hitung metrik gestur
                        tilt = lw[1] - rw[1]
                        dist = np.hypot(lw[0] - rw[0], lw[1] - rw[1])
                    else:
                        tilt, dist = 0.0, 0.5
            else:
                tilt, dist = 0.0, 0.5

            # Hitung FPS aktual
            curr_time = time.time()
            dt = curr_time - prev_time
            prev_time = curr_time
            fps = 1.0 / dt if dt > 0 else 30.0
            fps_history.append(fps)
            if len(fps_history) > 30:
                fps_history.pop(0)
            avg_fps = sum(fps_history) / len(fps_history)

            # HUD Panel
            overlay = frame.copy()
            cv2.rectangle(overlay, (20, 20), (460, 165), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

            cv2.putText(frame, f"Model: YOLOv8n-pose (CUDA Optimized)", (35, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
            cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi AI: {latency_ms:.1f} ms", (35, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 0), 2)

            status_str = "Zero-Lag Stream [UDP ON]" if pose_detected else "Mencari Tubuh..."
            status_col = (0, 255, 0) if pose_detected else (0, 0, 255)
            cv2.putText(frame, f"Status: {status_str}", (35, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_col, 2)

            # Tampilkan arah belok naga
            if abs(tilt) < 0.08:
                action_text = "Lurus (Gliding)"
            elif tilt > 0.08:
                action_text = f"Belok Kanan ({tilt:+.2f})"
            else:
                action_text = f"Belok Kiri ({tilt:+.2f})"

            cv2.putText(frame, f"Arah: {action_text} | Jarak Tangan: {dist:.2f}", (35, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)

            cv2.imshow("AR Dragon - High Performance Pose Test", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
        sender.close()
        print("[*] Pengujian selesai.")

if __name__ == "__main__":
    main()
