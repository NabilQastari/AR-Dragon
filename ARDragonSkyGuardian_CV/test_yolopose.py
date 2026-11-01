"""
test_yolopose.py
Pengujian interaktif YOLOv8n-pose dengan High-Speed Motion Tracking + CUDA.
- Menggunakan ThreadedCamera (MJPG, Zero Buffer Lag)
- High-Speed PoseStabilizer dengan Velocity Extrapolation (Tangan tidak hilang saat digerakkan cepat / blur)
- Kinematik Siku (Elbow) untuk memandu pergelangan tangan
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

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[*] Memuat YOLO-Pose pada perangkat: {device}...")
    model = YOLO(model_path)
    if device.startswith("cuda"):
        model.to(device)

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    stabilizer = PoseStabilizer()

    print("[*] Mengaktifkan Kamera Kecepatan Tinggi (MJPG 30 FPS)...")
    cam = ThreadedCamera(src=0, width=1280, height=720, fps=30)
    time.sleep(0.5)

    print("=" * 65)
    print(f"🚀 MENJALANKAN UJI HIGH-SPEED YOLO-POSE (Device: {device})")
    print("   - Fitur : High-Speed Velocity Predictor (Anti-Blur)")
    print("   - Kamera: Threaded Zero-Lag Stream (MJPG)")
    print("   - UDP   : 127.0.0.1:5052")
    print("   - Tekan 'q' atau ESC untuk keluar")
    print("=" * 65)

    prev_time = time.time()
    fps_history = []

    # Indeks keypoint COCO (17 titik)
    IDX_LS, IDX_RS = 5, 6
    IDX_LE, IDX_RE = 7, 8   # Left Elbow, Right Elbow
    IDX_LW, IDX_RW = 9, 10  # Left Wrist, Right Wrist
    IDX_LH, IDX_RH = 11, 12 # Left Hip, Right Hip

    try:
        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            t_start = time.perf_counter()

            # Menggunakan conf=0.20 agar tangan yang blur tetap terdeteksi oleh CNN
            results = model(frame, device=device, imgsz=640, verbose=False, conf=0.20)
            latency_ms = (time.perf_counter() - t_start) * 1000.0

            pose_detected = False
            is_fast_motion = False

            if results and len(results) > 0 and results[0].keypoints is not None:
                kpts_data = results[0].keypoints.data
                if kpts_data is not None and len(kpts_data) > 0:
                    kpts = kpts_data[0].cpu().numpy()
                    if len(kpts) >= 13:
                        pose_detected = True

                        def get_pt(idx):
                            return float(kpts[idx][0]) / w, float(kpts[idx][1]) / h, float(kpts[idx][2])

                        raw_ls_x, raw_ls_y, c_ls = get_pt(IDX_LS)
                        raw_rs_x, raw_rs_y, c_rs = get_pt(IDX_RS)
                        raw_le_x, raw_le_y, c_le = get_pt(IDX_LE)
                        raw_re_x, raw_re_y, c_re = get_pt(IDX_RE)
                        raw_lw_x, raw_lw_y, c_lw = get_pt(IDX_LW)
                        raw_rw_x, raw_rw_y, c_rw = get_pt(IDX_RW)
                        raw_lh_x, raw_lh_y, c_lh = get_pt(IDX_LH)
                        raw_rh_x, raw_rh_y, c_rh = get_pt(IDX_RH)

                        # Deteksi apakah tangan sedang bergerak cepat
                        vl = np.hypot(*stabilizer.velocities["lw"])
                        vr = np.hypot(*stabilizer.velocities["rw"])
                        if vl > 0.04 or vr > 0.04:
                            is_fast_motion = True

                        # Update stabilisasi dengan panduan posisi siku (elbow anchoring)
                        ls = stabilizer.update_point("ls", raw_ls_x, raw_ls_y, c_ls)
                        rs = stabilizer.update_point("rs", raw_rs_x, raw_rs_y, c_rs)
                        lw = stabilizer.update_point("lw", raw_lw_x, raw_lw_y, c_lw, elbow_ref=(raw_le_x, raw_le_y))
                        rw = stabilizer.update_point("rw", raw_rw_x, raw_rw_y, c_rw, elbow_ref=(raw_re_x, raw_re_y))
                        lh = stabilizer.update_point("lh", raw_lh_x, raw_lh_y, c_lh)
                        rh = stabilizer.update_point("rh", raw_rh_x, raw_rh_y, c_rh)

                        # Kirim ke Unity UDP
                        sender.send_pose(ls, rs, lw, rw, lh, rh)

                        def to_px(pt):
                            return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                        p_ls, p_rs = to_px(ls), to_px(rs)
                        p_lw, p_rw = to_px(lw), to_px(rw)
                        p_lh, p_rh = to_px(lh), to_px(rh)
                        p_le, p_re = to_px((raw_le_x, raw_le_y)), to_px((raw_re_x, raw_re_y))

                        # Gambar rangka lengkap termasuk siku
                        color_bone = (0, 230, 255)
                        cv2.line(frame, p_ls, p_rs, color_bone, 3)
                        cv2.line(frame, p_ls, p_le, color_bone, 3)
                        cv2.line(frame, p_le, p_lw, color_bone, 3)
                        cv2.line(frame, p_rs, p_re, color_bone, 3)
                        cv2.line(frame, p_re, p_rw, color_bone, 3)
                        cv2.line(frame, p_ls, p_lh, color_bone, 3)
                        cv2.line(frame, p_rs, p_rh, color_bone, 3)
                        cv2.line(frame, p_lh, p_rh, color_bone, 3)

                        # Sendi bahu, siku, pinggul
                        cv2.circle(frame, p_ls, 8, (0, 255, 255), -1)
                        cv2.circle(frame, p_rs, 8, (0, 255, 255), -1)
                        cv2.circle(frame, p_le, 6, (180, 255, 100), -1)
                        cv2.circle(frame, p_re, 6, (180, 255, 100), -1)
                        cv2.circle(frame, p_lh, 7, (0, 165, 255), -1)
                        cv2.circle(frame, p_rh, 7, (0, 165, 255), -1)

                        # Pergelangan tangan (warna berubah merah menyala saat bergerak cepat)
                        hand_color = (0, 120, 255) if is_fast_motion else (255, 0, 200)
                        cv2.circle(frame, p_lw, 12, hand_color, -1)
                        cv2.circle(frame, p_rw, 12, (0, 255, 0), -1)

                        # Garis vektor kecepatan tangan (menunjukkan arah ayunan tangan secara real-time)
                        if is_fast_motion:
                            vx_l, vy_l = stabilizer.velocities["lw"]
                            vx_r, vy_r = stabilizer.velocities["rw"]
                            cv2.arrowedLine(frame, p_lw, (int(p_lw[0] + vx_l * w * 1.5), int(p_lw[1] + vy_l * h * 1.5)), (0, 0, 255), 3)
                            cv2.arrowedLine(frame, p_rw, (int(p_rw[0] + vx_r * w * 1.5), int(p_rw[1] + vy_r * h * 1.5)), (0, 255, 0), 3)

                        tilt = lw[1] - rw[1]
                        dist = np.hypot(lw[0] - rw[0], lw[1] - rw[1])
                    else:
                        tilt, dist = 0.0, 0.5
            else:
                tilt, dist = 0.0, 0.5

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
            cv2.rectangle(overlay, (20, 20), (480, 175), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

            cv2.putText(frame, f"Model: YOLOv8n-pose (Fast-Motion Optimized)", (35, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 255), 2)
            cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi AI: {latency_ms:.1f} ms", (35, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            speed_tag = " [FAST MOTION DETECTED]" if is_fast_motion else ""
            status_str = ("Tracking Aktif" if pose_detected else "Mencari Tubuh...") + speed_tag
            status_col = (0, 100, 255) if is_fast_motion else ((0, 255, 0) if pose_detected else (0, 0, 255))
            cv2.putText(frame, f"Status: {status_str}", (35, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, status_col, 2)

            if abs(tilt) < 0.08:
                action_text = "Lurus (Gliding)"
            elif tilt > 0.08:
                action_text = f"Belok Kanan ({tilt:+.2f})"
            else:
                action_text = f"Belok Kiri ({tilt:+.2f})"

            cv2.putText(frame, f"Arah: {action_text} | Jarak: {dist:.2f}", (35, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)

            cv2.putText(frame, "Tips: Pastikan pencahayaan cukup untuk mengurangi blur", (35, 165),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 160, 160), 1)

            cv2.imshow("AR Dragon - High-Speed Pose Test", frame)
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
