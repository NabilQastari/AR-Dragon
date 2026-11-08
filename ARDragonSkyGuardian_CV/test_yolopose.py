"""
test_yolopose.py
Pengujian interaktif YOLOv8n-pose (CUDA) + Zero-Delay Head-Cropped Water Breath Tracker.
- Pose: YOLOv8n-pose (CUDA GPU ~12 ms) dengan Anatomical Dynamic Arm Clamping & Primary Player Auto-Lock
- Mulut: Head-Cropped Instant Mouth Tracker (~5 ms, Zero Delay)
- Sayap: WingFlapDetector State Machine (Anti-Flicker Hysteresis, Flap Rate Hz & Power)
- Kemudi: Smooth Deadzone Flight Tilt (-100% to +100%)
- Kamera: ThreadedCamera (MJPG 30 FPS, Zero Buffer Lag)
- UDP: 127.0.0.1:5052 (13 Float CSV)
"""

import os
import sys
import time
import math
import tempfile
import cv2
import numpy as np
import torch

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()
from ultralytics import YOLO

from udp_sender import PoseUDPSender
from camera_stream import ThreadedCamera
from pose_stabilizer import PoseStabilizer, WingFlapDetector, compute_smooth_tilt
from mouth_tracker import MouthTracker

def main():
    model_path = os.path.join(os.path.dirname(__file__), "yolov8n-pose.pt")
    if not os.path.exists(model_path):
        print(f"[!] Model {model_path} tidak ditemukan!")
        return

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[*] Memuat YOLO-Pose pada perangkat: {device}...")
    pose_model = YOLO(model_path)
    if device.startswith("cuda"):
        pose_model.to(device)

    print("[*] Memuat Zero-Delay Head-Cropped Mouth Tracker...")
    mouth_tracker = MouthTracker()

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    stabilizer = PoseStabilizer()
    flap_detector = WingFlapDetector(hysteresis=0.035)

    print("[*] Mengaktifkan Kamera Kecepatan Tinggi (MJPG 30 FPS)...")
    cam = ThreadedCamera(src=0, width=1280, height=720, fps=30)
    time.sleep(0.5)

    print("=" * 65)
    print("🚀 MENJALANKAN UJI YOLO-POSE ULTRA-ACCURACY (ZERO-DELAY)")
    print("   - Pose   : YOLOv8n CUDA Tensor Acceleration (~12 ms)")
    print("   - Locking: Primary Player Auto-Targeting (Largest Bounding Box)")
    print("   - Anatomi: Dynamic Biometric Arm Clamping + Forearm Stabilization")
    print("   - Sayap  : WingFlapDetector State Machine (Anti-Flicker & Power)")
    print("   - Kemudi : Smooth Deadzone Flight Tilt (-100% s/d +100%)")
    print("   - Mulut  : Head-Crop Instant MAR (~5 ms, Zero Delay)")
    print("   - UDP    : 127.0.0.1:5052 (13 Float CSV)")
    print("   - Tekan 'q' atau ESC untuk keluar")
    print("=" * 65)

    prev_time = time.time()
    fps_history = []
    head_pos = None

    IDX_NOSE = 0
    IDX_LS, IDX_RS = 5, 6
    IDX_LE, IDX_RE = 7, 8
    IDX_LW, IDX_RW = 9, 10
    IDX_LH, IDX_RH = 11, 12

    try:
        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            t_start = time.perf_counter()

            # 1. Inferensi Pose via YOLO (CUDA GPU ~12 ms)
            results = pose_model(frame, device=device, imgsz=640, verbose=False, conf=0.25)

            pose_detected = False
            flap_count = 0
            flap_state_str = "TIDAK TERDETEKSI"
            flap_freq = 0.0
            flap_power = 0.0
            norm_tilt = 0.0
            raw_diff = 0.0
            num_persons = 0

            if results and len(results) > 0 and results[0].keypoints is not None:
                kpts_data = results[0].keypoints.data
                boxes = results[0].boxes
                if kpts_data is not None and len(kpts_data) > 0:
                    num_persons = len(kpts_data)

                    # Kunci pemain utama (Bounding Box terbesar paling dekat layar)
                    best_idx = 0
                    if boxes is not None and len(boxes) > 1:
                        max_area = 0.0
                        for b_idx, box in enumerate(boxes):
                            xyxy = box.xyxy[0].cpu().numpy()
                            area = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1])
                            if area > max_area:
                                max_area = area
                                best_idx = b_idx

                    kpts = kpts_data[best_idx].cpu().numpy()
                    if len(kpts) >= 13:
                        pose_detected = True

                        def get_pt(idx):
                            return float(kpts[idx][0]) / w, float(kpts[idx][1]) / h, float(kpts[idx][2])

                        raw_nose_x, raw_nose_y, c_nose = get_pt(IDX_NOSE)
                        head_pos = (raw_nose_x, raw_nose_y)

                        raw_ls_x, raw_ls_y, c_ls = get_pt(IDX_LS)
                        raw_rs_x, raw_rs_y, c_rs = get_pt(IDX_RS)
                        raw_le_x, raw_le_y, c_le = get_pt(IDX_LE)
                        raw_re_x, raw_re_y, c_re = get_pt(IDX_RE)
                        raw_lw_x, raw_lw_y, c_lw = get_pt(IDX_LW)
                        raw_rw_x, raw_rw_y, c_rw = get_pt(IDX_RW)
                        raw_lh_x, raw_lh_y, c_lh = get_pt(IDX_LH)
                        raw_rh_x, raw_rh_y, c_rh = get_pt(IDX_RH)

                        # Stabilisasi Bahu, Siku, & Pinggul
                        ls = stabilizer.update_point("ls", raw_ls_x, raw_ls_y, c_ls)
                        rs = stabilizer.update_point("rs", raw_rs_x, raw_rs_y, c_rs)
                        le = stabilizer.update_point("le", raw_le_x, raw_le_y, c_le)
                        re = stabilizer.update_point("re", raw_re_x, raw_re_y, c_re)
                        lh = stabilizer.update_point("lh", raw_lh_x, raw_lh_y, c_lh)
                        rh = stabilizer.update_point("rh", raw_rh_x, raw_rh_y, c_rh)

                        # Biometrik: Jarak Bahu Dinamis
                        shoulder_dist = math.hypot(ls[0] - rs[0], ls[1] - rs[1])

                        # Stabilisasi Pergelangan Tangan dgn Batasan Kinematika Lengan
                        lw = stabilizer.update_point("lw", raw_lw_x, raw_lw_y, c_lw,
                                                     shoulder_ref=ls, shoulder_width=shoulder_dist, elbow_ref=le)
                        rw = stabilizer.update_point("rw", raw_rw_x, raw_rw_y, c_rw,
                                                     shoulder_ref=rs, shoulder_width=shoulder_dist, elbow_ref=re)

                        # Deteksi Kepakan Sayap Cerdas (Hysteresis State Machine)
                        flap_count, flap_state_str, flap_freq, flap_power = flap_detector.update(lw, rw, ls, rs)

                        # Kemudi Terbang Halus dengan Deadzone
                        raw_diff, norm_tilt = compute_smooth_tilt(lw, rw, deadzone=0.035, max_tilt=0.25)

            # 2. Inferensi Mulut Terbuka via Crop Area Kepala (Sangat Cepat ~5 ms)
            is_water_breathing, mouth_score, mouth_center = mouth_tracker.process_crop(frame, head_pos)

            if pose_detected:
                udp_mouth_val = 1.0 if is_water_breathing else mouth_score
                sender.send_pose(ls, rs, lw, rw, lh, rh, mouth_open=udp_mouth_val)

            latency_ms = (time.perf_counter() - t_start) * 1000.0

            # 3. Visualisasi Rendering Cepat & Responsif
            if pose_detected:
                def to_px(pt):
                    return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                p_ls, p_rs = to_px(ls), to_px(rs)
                p_lw, p_rw = to_px(lw), to_px(rw)
                p_lh, p_rh = to_px(lh), to_px(rh)
                p_le, p_re = to_px(le), to_px(re)

                # Garis Horizon Referensi Bahu
                cv2.line(frame, (0, p_ls[1]), (w, p_rs[1]), (60, 60, 60), 1)

                # Tulang Kerangka Tubuh (Bahu, Lengan, Pinggul)
                color_bone = (0, 255, 180)
                cv2.line(frame, p_ls, p_rs, color_bone, 3)
                cv2.line(frame, p_ls, p_le, color_bone, 3)
                cv2.line(frame, p_le, p_lw, color_bone, 3)
                cv2.line(frame, p_rs, p_re, color_bone, 3)
                cv2.line(frame, p_re, p_rw, color_bone, 3)
                cv2.line(frame, p_ls, p_lh, color_bone, 3)
                cv2.line(frame, p_rs, p_rh, color_bone, 3)
                cv2.line(frame, p_lh, p_rh, color_bone, 3)

                # Sendi Bahu & Siku
                cv2.circle(frame, p_ls, 6, (0, 255, 255), -1)
                cv2.circle(frame, p_rs, 6, (0, 255, 255), -1)
                cv2.circle(frame, p_le, 5, (0, 200, 255), -1)
                cv2.circle(frame, p_re, 5, (0, 200, 255), -1)

                # Efek Visual Tangan: Warna berubah sesuai status kepakan & power
                is_above = (lw[1] < ls[1]) and (rw[1] < rs[1])
                hand_color = (0, 255, 0) if is_above else (255, 50, 200)

                # Cincin Glow saat kepakan bertenaga
                glow_r = int(12 + flap_power * 14)
                cv2.circle(frame, p_lw, glow_r, (0, 255, 255), 2 if flap_power > 0.3 else 1)
                cv2.circle(frame, p_rw, glow_r, (0, 255, 255), 2 if flap_power > 0.3 else 1)
                cv2.circle(frame, p_lw, 10, hand_color, -1)
                cv2.circle(frame, p_rw, 10, hand_color, -1)

            # Efek Visual Semburan Air Instan
            if is_water_breathing and mouth_center is not None:
                mx, my = mouth_center
                cv2.circle(frame, (mx, my), 26, (255, 220, 0), 2)
                for _ in range(10):
                    ox = np.random.randint(-25, 26)
                    oy = np.random.randint(10, 65)
                    cv2.circle(frame, (mx + ox, my + oy), np.random.randint(3, 7), (255, 255, 120), -1)

            # Penghitungan FPS Riil
            curr_time = time.time()
            dt = curr_time - prev_time
            prev_time = curr_time
            fps = 1.0 / dt if dt > 0 else 30.0
            fps_history.append(fps)
            if len(fps_history) > 30:
                fps_history.pop(0)
            avg_fps = sum(fps_history) / len(fps_history)

            # HUD Panel Kontrol & Telemetri Real-time
            overlay = frame.copy()
            cv2.rectangle(overlay, (20, 15), (570, 225), (15, 15, 15), -1)
            cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)

            # Header & Target Lock
            lock_str = f"LOCKED ({num_persons} Terdeteksi)" if pose_detected else "MENCARI TARGET..."
            lock_col = (0, 255, 0) if pose_detected else (0, 165, 255)
            cv2.putText(frame, "YOLOv8n-pose ULTRA-ACCURACY [CUDA]", (35, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 255), 2)
            cv2.putText(frame, f"Target: {lock_str}", (380, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, lock_col, 1)

            # Performance Bar
            cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi AI: {latency_ms:.1f} ms", (35, 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 120), 2)

            # Telemetri Kepak Sayap
            pwr_pct = int(flap_power * 100)
            cv2.putText(frame, f"Kepakan : {flap_state_str} (Total: {flap_count})", (35, 105),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)
            cv2.putText(frame, f"Rate    : {flap_freq:.1f} Hz  |  Power Dorong: {pwr_pct}%", (35, 132),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1)

            # Telemetri Kemudi & Deadzone Flight Bar
            if abs(norm_tilt) < 0.05:
                steer_str = "LURUS (Stabil Deadzone)"
                steer_col = (100, 255, 100)
            elif norm_tilt < 0:
                steer_str = f"BELOK KIRI ({int(abs(norm_tilt)*100)}%)"
                steer_col = (0, 200, 255)
            else:
                steer_str = f"BELOK KANAN ({int(abs(norm_tilt)*100)}%)"
                steer_col = (0, 200, 255)

            cv2.putText(frame, f"Kemudi  : {steer_str}", (35, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, steer_col, 1)

            # Mini Steering Indicator Bar
            bar_cx = 440
            bar_y = 157
            bar_w = 90
            cv2.rectangle(frame, (bar_cx - bar_w, bar_y - 6), (bar_cx + bar_w, bar_y + 6), (80, 80, 80), 1)
            cv2.line(frame, (bar_cx, bar_y - 8), (bar_cx, bar_y + 8), (140, 140, 140), 1)
            # Deadzone marker
            dz_px = int(bar_w * 0.15)
            cv2.line(frame, (bar_cx - dz_px, bar_y - 4), (bar_cx - dz_px, bar_y + 4), (100, 100, 100), 1)
            cv2.line(frame, (bar_cx + dz_px, bar_y - 4), (bar_cx + dz_px, bar_y + 4), (100, 100, 100), 1)
            # Steering Indicator Pointer
            ptr_x = int(bar_cx + norm_tilt * bar_w)
            cv2.circle(frame, (ptr_x, bar_y), 6, steer_col, -1)

            # Telemetri Aksi Mulut / Semburan Air
            breath_str = f"SEMBUR AIR AKTIF! ({mouth_score:.2f})" if is_water_breathing else f"Mulut Normal ({mouth_score:.2f})"
            breath_col = (255, 220, 0) if is_water_breathing else (160, 160, 160)
            cv2.putText(frame, f"Mulut   : {breath_str}", (35, 190),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, breath_col, 2)

            # UDP Telemetry
            cv2.putText(frame, "UDP 5052: Streaming Aktif (13-Float CSV)", (35, 215),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)

            cv2.imshow("AR Dragon - YOLO Ultra-Accuracy Test", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
        sender.close()
        print("[*] Selesai pengujian YOLO-Pose.")

if __name__ == "__main__":
    main()
