"""
active_cv_sender.py
Modul Pengirim Pose CV Resmi (Locked Model: YOLOv8n-pose CUDA GPU).
Dirancang khusus untuk dijalankan berdampingan dengan Unity AR Dragon Sky Guardian.
- Model: YOLOv8n-pose (Tensor GPU ~12 ms)
- Multi-person: Primary Player Auto-Lock (Prioritas Pemain Utama)
- Biometrik: Dynamic Anatomical Arm Clamping & Adaptive One-Euro Filter
- Sayap: WingFlapDetector State Machine (Anti-Flicker & Flap Power)
- Kemudi: Smooth Deadzone Tilt (-100% s/d +100%)
- Mulut: Zero-Delay Head-Cropped Water Breath Tracker (~5 ms)
- Protokol: UDP 127.0.0.1:5052 (13 Float CSV)
- Mode: GUI Preview interaktif atau Headless (--headless)
"""

import os
import sys
import time
import math
import argparse
import tempfile
import cv2
import numpy as np
import torch

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()
from ultralytics import YOLO

from udp_sender import PoseUDPSender, VideoUDPSender
from camera_stream import ThreadedCamera
from pose_stabilizer import PoseStabilizer, WingFlapDetector, compute_smooth_tilt
from mouth_tracker import MouthTracker

def parse_args():
    parser = argparse.ArgumentParser(description="Active CV Sender for Unity AR Dragon Sky Guardian")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="Target UDP IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5052, help="Target UDP Pose Port (default: 5052)")
    parser.add_argument("--video-port", type=int, default=5053, help="Target UDP Video PIP Port (default: 5053)")
    parser.add_argument("--no-video-stream", action="store_true", help="Disable PIP video UDP stream")
    parser.add_argument("--cam", type=int, default=0, help="Camera Index (default: 0)")
    parser.add_argument("--width", type=int, default=1280, help="Capture Width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Capture Height (default: 720)")
    parser.add_argument("--headless", action="store_true", help="Run in headless background mode (no GUI window)")
    return parser.parse_args()

def main():
    args = parse_args()

    model_path = os.path.join(os.path.dirname(__file__), "yolov8n-pose.pt")
    if not os.path.exists(model_path):
        print(f"[!] File model tidak ditemukan: {model_path}")
        return

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[*] Inisialisasi YOLOv8n-pose pada perangkat: {device}...")
    pose_model = YOLO(model_path)
    if device.startswith("cuda"):
        pose_model.to(device)

    print("[*] Menginisialisasi Mouth Tracker (Zero-Delay Head-Crop)...")
    mouth_tracker = MouthTracker()

    print(f"[*] Membuka koneksi UDP Pose ke {args.ip}:{args.port}...")
    sender = PoseUDPSender(ip=args.ip, port=args.port)

    video_sender = None
    if not args.no_video_stream:
        print(f"[*] Membuka streaming video PIP UDP ke {args.ip}:{args.video_port}...")
        video_sender = VideoUDPSender(ip=args.ip, port=args.video_port)

    stabilizer = PoseStabilizer()
    flap_detector = WingFlapDetector(hysteresis=0.035)

    print(f"[*] Menyalakan kamera (MJPG 30 FPS, Cam ID {args.cam})...")
    cam = ThreadedCamera(src=args.cam, width=args.width, height=args.height, fps=30)
    time.sleep(0.5)

    print("=" * 70)
    print("🐉 ACTIVE CV SENDER - AR DRAGON SKY GUARDIAN (YOLOv8n-pose)")
    print(f"   - Target UDP Pose : {args.ip}:{args.port}")
    print(f"   - Target UDP Video: {args.ip}:{args.video_port} ({'AKTIF' if video_sender else 'NONAKTIF'})")
    print(f"   - Mode Eksekusi   : {'HEADLESS (Background)' if args.headless else 'INTERAKTIF GUI PREVIEW'}")
    print(f"   - Akselerasi      : NVIDIA CUDA Tensor ({device})")
    print("   - Tekan Ctrl+C (atau 'q'/ESC pada GUI) untuk menghentikan pengiriman")
    print("=" * 70)

    IDX_NOSE = 0
    IDX_LS, IDX_RS = 5, 6
    IDX_LE, IDX_RE = 7, 8
    IDX_LW, IDX_RW = 9, 10
    IDX_LH, IDX_RH = 11, 12

    prev_time = time.time()
    fps_history = []
    head_pos = None

    try:
        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            t_start = time.perf_counter()

            # 1. Inferensi Pose YOLOv8n
            results = pose_model(frame, device=device, imgsz=640, verbose=False, conf=0.25)

            pose_detected = False
            flap_count = 0
            flap_state_str = "TIDAK TERDETEKSI"
            flap_freq = 0.0
            flap_power = 0.0
            norm_tilt = 0.0
            raw_diff = 0.0

            if results and len(results) > 0 and results[0].keypoints is not None:
                kpts_data = results[0].keypoints.data
                boxes = results[0].boxes
                if kpts_data is not None and len(kpts_data) > 0:
                    # Kunci target pemain utama dengan Bounding Box terbesar
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

                        # Stabilisasi sendi bahu, siku, dan pinggul
                        ls = stabilizer.update_point("ls", raw_ls_x, raw_ls_y, c_ls)
                        rs = stabilizer.update_point("rs", raw_rs_x, raw_rs_y, c_rs)
                        le = stabilizer.update_point("le", raw_le_x, raw_le_y, c_le)
                        re = stabilizer.update_point("re", raw_re_x, raw_re_y, c_re)
                        lh = stabilizer.update_point("lh", raw_lh_x, raw_lh_y, c_lh)
                        rh = stabilizer.update_point("rh", raw_rh_x, raw_rh_y, c_rh)

                        # Biometrik: Jarak bahu aktual pengguna di layar
                        shoulder_dist = math.hypot(ls[0] - rs[0], ls[1] - rs[1])

                        # Stabilisasi pergelangan tangan dengan Dynamic Arm Clamping
                        lw = stabilizer.update_point("lw", raw_lw_x, raw_lw_y, c_lw,
                                                     shoulder_ref=ls, shoulder_width=shoulder_dist, elbow_ref=le)
                        rw = stabilizer.update_point("rw", raw_rw_x, raw_rw_y, c_rw,
                                                     shoulder_ref=rs, shoulder_width=shoulder_dist, elbow_ref=re)

                        flap_count, flap_state_str, flap_freq, flap_power = flap_detector.update(lw, rw, ls, rs)
                        raw_diff, norm_tilt = compute_smooth_tilt(lw, rw, deadzone=0.035, max_tilt=0.25)

            # 2. Deteksi Manuver Dinamis ala Sky Peck:
            # - TUCK TO DIVE (Sesuai Foto Pengguna): Tangan mengepal di dada atas/leher, siku ke bawah -> Dive Terjun Cepat
            # - FLAP TO CLIMB (Kepakan Sayap): Menggerakkan tangan naik-turun -> Daya angkat vertikal halus & dorongan maju
            # - LEAN TO TURN: Condongkan tubuh (torso) atau miringkan lengan untuk berbelok dan banking sayap
            # - GLIDE: Tangan merentang mendatar -> Meluncur anggun dengan kecepatan jelajah stabil
            is_tuck_dive = False
            is_flapping = False
            is_y = False
            total_lean = 0.0
            vert_mode_str = "SKY PECK: GLIDE (Meluncur Anggun)"
            vert_mode_color = (255, 220, 60)

            if pose_detected:
                dy_l = lw[1] - ls[1]
                dy_r = rw[1] - rs[1]
                avg_dy = (dy_l + dy_r) * 0.5
                wrist_dist = math.hypot(lw[0] - rw[0], lw[1] - rw[1])

                # Hitung Lean to Turn ala Sky Peck (50% Arm Tilt + 50% Torso Lean)
                mid_s = ((ls[0] + rs[0]) * 0.5, (ls[1] + rs[1]) * 0.5)
                mid_h = ((lh[0] + rh[0]) * 0.5, (lh[1] + rh[1]) * 0.5)
                sw = max(0.08, shoulder_dist)
                torso_lean = (mid_s[0] - mid_h[0]) / sw
                total_lean = float(np.clip(0.50 * norm_tilt + 0.50 * (torso_lean * 2.2), -1.0, 1.0))
                if abs(total_lean) < 0.05:
                    total_lean = 0.0

                # a. TUCK DIVE (Foto Pengguna): Siku di bawah pergelangan tangan & bahu, tangan rapat di dada
                elbows_below_wrists = (le[1] > lw[1] + 0.04) and (re[1] > rw[1] + 0.04)
                elbows_below_shoulders = (le[1] > ls[1] + 0.07) and (re[1] > rs[1] + 0.07)
                wrists_at_chest = (lw[1] > ls[1] - 0.12) and (rw[1] > rs[1] - 0.12) and (lw[1] < lh[1] - 0.08) and (rw[1] < rh[1] - 0.08)
                hands_compact = wrist_dist < (shoulder_dist * 1.65)

                if elbows_below_wrists and elbows_below_shoulders and wrists_at_chest and hands_compact:
                    is_tuck_dive = True

                # b. FLAPPING: Siklus kepakan aktif (Fly Up + Speed Up ala Sky Peck)
                now_t = time.perf_counter()
                has_recent_flap = (now_t - flap_detector.last_flap_time) < 0.60 and (flap_detector.last_flap_time > 0)
                is_active_flapping = (flap_power > 0.20 and not is_tuck_dive)
                if has_recent_flap or is_active_flapping:
                    is_flapping = True

                # c. ORIENTASI BADAN (Body Pitch: -1.0 s/d +1.0)
                head_dist = mid_s[1] - raw_nose_y
                head_ratio = head_dist / sw

                # Signal orientasi kepala/badan (netral ~ 0.48)
                head_signal = (head_ratio - 0.48) / 0.14
                head_signal = max(-1.0, min(1.0, head_signal))
                if abs(head_signal) < 0.22:
                    head_signal = 0.0
                else:
                    head_signal = math.copysign((abs(head_signal) - 0.22) / 0.78, head_signal)

                # d. DECOUPLING: Saat tangan dikepakkan, ayunan tangan TIDAK BOLEH memicu Pose Y / Pose A!
                if is_flapping:
                    is_y = False
                    is_a = False

                    # Periksa apakah busur ayunan kepakan diarahkan ke atas kepala (high arc) atau ke bawah (low arc)
                    avg_wrist_y = (lw[1] + rw[1]) * 0.5
                    arm_aim_offset = mid_s[1] - avg_wrist_y  # Positif jika tangan mengepak di atas bahu
                    if arm_aim_offset > 0.08:
                        flap_aim = min(1.0, (arm_aim_offset - 0.08) / 0.12)
                    elif arm_aim_offset < -0.12:
                        flap_aim = -min(1.0, (abs(arm_aim_offset) - 0.12) / 0.12)
                    else:
                        flap_aim = 0.0

                    body_pitch = 0.55 * head_signal + 0.45 * flap_aim
                else:
                    body_pitch = head_signal
                    is_y = ((dy_l < -0.04 and dy_r < -0.04) or (avg_dy < -0.05)) and not is_tuck_dive
                    is_a = ((dy_l > 0.05 and dy_r > 0.05) or (avg_dy > 0.06)) and not is_tuck_dive

                # Tentukan label dan warna status untuk HUD
                if is_tuck_dive:
                    vert_mode_str = "SKY PECK: TUCK DIVE (Menukik Cepat ↓↓)"
                    vert_mode_color = (0, 100, 255)
                elif is_flapping:
                    vert_mode_str = f"SKY PECK: FLAP TO CLIMB ↑ (+{flap_power*100:.0f}%)"
                    vert_mode_color = (0, 255, 120)
                elif is_y:
                    vert_mode_str = "SKY PECK: ZOOM CLIMB ↑"
                    vert_mode_color = (0, 255, 220)
                elif is_a:
                    vert_mode_str = "SKY PECK: DIVE ↓"
                    vert_mode_color = (0, 160, 255)
                else:
                    vert_mode_str = "SKY PECK: GLIDE (Meluncur Anggun)"
                    vert_mode_color = (255, 220, 60)

            # 3. Inferensi Mulut Terbuka via Crop Area Kepala
            is_water_breathing, mouth_score, mouth_center = mouth_tracker.process_crop(frame, head_pos)

            # 4. Pengiriman Paket UDP ke Unity (13 float dasar + siku + flag gestur + body_pitch + nose)
            if pose_detected:
                udp_mouth_val = 1.0 if is_water_breathing else mouth_score
                sender.send_pose(
                    ls, rs, lw, rw, lh, rh,
                    mouth_open=udp_mouth_val,
                    le=le, re=re,
                    is_dive=1.0 if is_tuck_dive else 0.0,
                    is_flap=1.0 if is_flapping else 0.0,
                    flap_freq=flap_freq,
                    flap_power=flap_power,
                    body_pitch=body_pitch,
                    nose=(raw_nose_x, raw_nose_y)
                )

            latency_ms = (time.perf_counter() - t_start) * 1000.0

            curr_time = time.time()
            dt = curr_time - prev_time
            prev_time = curr_time
            fps = 1.0 / dt if dt > 0 else 30.0
            fps_history.append(fps)
            if len(fps_history) > 30:
                fps_history.pop(0)
            avg_fps = sum(fps_history) / len(fps_history)

            # 5. Gambar Anotasi Pose & Visual Feedback pada Frame
            if pose_detected:
                def to_px(pt):
                    return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                p_ls, p_rs = to_px(ls), to_px(rs)
                p_lw, p_rw = to_px(lw), to_px(rw)
                p_lh, p_rh = to_px(lh), to_px(rh)
                p_le, p_re = to_px(le), to_px(re)

                color_bone = (0, 255, 180)
                cv2.line(frame, p_ls, p_rs, color_bone, 3)
                cv2.line(frame, p_ls, p_le, color_bone, 3)
                cv2.line(frame, p_le, p_lw, color_bone, 3)
                cv2.line(frame, p_rs, p_re, color_bone, 3)
                cv2.line(frame, p_re, p_rw, color_bone, 3)
                cv2.line(frame, p_ls, p_lh, color_bone, 3)
                cv2.line(frame, p_rs, p_rh, color_bone, 3)
                cv2.line(frame, p_lh, p_rh, color_bone, 3)

                is_above = (lw[1] < ls[1]) and (rw[1] < rs[1])
                hand_col = (0, 255, 0) if is_above else (255, 50, 200)
                cv2.circle(frame, p_lw, 10, hand_col, -1)
                cv2.circle(frame, p_rw, 10, hand_col, -1)

            if is_water_breathing and mouth_center is not None:
                mx, my = mouth_center
                cv2.circle(frame, (mx, my), 22, (255, 220, 0), 2)

            # 6. Kirim Frame Video ke Unity via UDP (PIP Preview)
            if video_sender is not None:
                video_sender.send_frame(frame)

            # 7. Rendering GUI Window (Kecuali mode headless)
            if not args.headless:
                # HUD Telemetri
                overlay = frame.copy()
                cv2.rectangle(overlay, (20, 15), (550, 195), (15, 15, 15), -1)
                cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)

                status_txt = "TERKUNCI" if pose_detected else "MENCARI..."
                cv2.putText(frame, f"AR DRAGON CV SENDER [CUDA] - {status_txt}", (35, 45),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
                cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi AI: {latency_ms:.1f} ms", (35, 75),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 255, 120), 2)
                cv2.putText(frame, f"Manuver: {vert_mode_str}", (35, 105),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, vert_mode_color, 2)
                cv2.putText(frame, f"Sayap: {flap_state_str} (Freq: {flap_freq:.1f} Hz) | Lean: {total_lean:+.2f}", (35, 135),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
                cv2.putText(frame, f"Mulut: {'SEMBUR AIR' if is_water_breathing else 'TUTUP'} ({mouth_score:.2f})", (35, 160),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 220, 0) if is_water_breathing else (180, 180, 180), 1)
                cv2.putText(frame, f"UDP  : 127.0.0.1:{args.port} | PIP: :{args.video_port}", (35, 182),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (150, 150, 150), 1)

                cv2.imshow("AR Dragon - Active CV Sender (YOLOv8n-pose)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break
    except KeyboardInterrupt:
        print("\n[*] Sinyal interrupt diterima, mematikan sender...")
    finally:
        cam.release()
        cv2.destroyAllWindows()
        sender.close()
        if video_sender is not None:
            video_sender.close()
        print("[*] Active CV Sender berhasil dihentikan secara aman.")

if __name__ == "__main__":
    main()
