"""
test_yolopose.py
Pengujian interaktif YOLOv8n-pose dengan Kinematic Flap-Stabilizer + CUDA.
- Menggunakan ThreadedCamera (MJPG 30 FPS, Zero Buffer Lag)
- PoseStabilizer dengan Arm-Length Clamping (Anti-Glitch Kepak Sayap)
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
    print(f"🚀 MENJALANKAN UJI YOLO-POSE ANTI-GLITCH (Device: {device})")
    print("   - Fitur : Kinematic Arm Clamping (Anti-Glitch Kepak Sayap)")
    print("   - Kamera: Threaded Zero-Lag Stream (MJPG)")
    print("   - UDP   : 127.0.0.1:5052")
    print("   - Tekan 'q' atau ESC untuk keluar")
    print("=" * 65)

    prev_time = time.time()
    fps_history = []
    flap_count = 0
    prev_above = False

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
            results = model(frame, device=device, imgsz=640, verbose=False, conf=0.25)
            latency_ms = (time.perf_counter() - t_start) * 1000.0

            pose_detected = False
            is_above = False

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

                        # Stabilisasi dengan jangkar bahu (mencegah tangan melompat keluar)
                        ls = stabilizer.update_point("ls", raw_ls_x, raw_ls_y, c_ls)
                        rs = stabilizer.update_point("rs", raw_rs_x, raw_rs_y, c_rs)
                        lw = stabilizer.update_point("lw", raw_lw_x, raw_lw_y, c_lw, shoulder_ref=ls)
                        rw = stabilizer.update_point("rw", raw_rw_x, raw_rw_y, c_rw, shoulder_ref=rs)
                        lh = stabilizer.update_point("lh", raw_lh_x, raw_lh_y, c_lh)
                        rh = stabilizer.update_point("rh", raw_rh_x, raw_rh_y, c_rh)

                        sender.send_pose(ls, rs, lw, rw, lh, rh)

                        # Logika Kepak Sayap (Flapping): Tangan di atas bahu vs di bawah bahu
                        is_above = (lw[1] < ls[1]) and (rw[1] < rs[1])
                        if is_above != prev_above:
                            flap_count += 1
                            prev_above = is_above

                        def to_px(pt):
                            return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                        p_ls, p_rs = to_px(ls), to_px(rs)
                        p_lw, p_rw = to_px(lw), to_px(rw)
                        p_lh, p_rh = to_px(lh), to_px(rh)
                        p_le, p_re = to_px((raw_le_x, raw_le_y)), to_px((raw_re_x, raw_re_y))

                        # Gambar garis bahu acuan kepak sayap
                        cv2.line(frame, (0, p_ls[1]), (w, p_rs[1]), (80, 80, 80), 1, cv2.LINE_AA)

                        # Rangka tubuh
                        color_bone = (0, 255, 200)
                        cv2.line(frame, p_ls, p_rs, color_bone, 3)
                        cv2.line(frame, p_ls, p_le, color_bone, 3)
                        cv2.line(frame, p_le, p_lw, color_bone, 3)
                        cv2.line(frame, p_rs, p_re, color_bone, 3)
                        cv2.line(frame, p_re, p_rw, color_bone, 3)
                        cv2.line(frame, p_ls, p_lh, color_bone, 3)
                        cv2.line(frame, p_rs, p_rh, color_bone, 3)
                        cv2.line(frame, p_lh, p_rh, color_bone, 3)

                        cv2.circle(frame, p_ls, 8, (0, 255, 255), -1)
                        cv2.circle(frame, p_rs, 8, (0, 255, 255), -1)
                        cv2.circle(frame, p_lh, 7, (0, 165, 255), -1)
                        cv2.circle(frame, p_rh, 7, (0, 165, 255), -1)

                        # Indikator warna pergelangan tangan: Hijau jika di atas bahu, Magenta jika di bawah
                        hand_color = (0, 255, 0) if is_above else (255, 0, 255)
                        cv2.circle(frame, p_lw, 13, hand_color, -1)
                        cv2.circle(frame, p_rw, 13, hand_color, -1)

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

            cv2.putText(frame, "Model: YOLOv8n-pose (Anti-Glitch)", (35, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 255), 2)
            cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi AI: {latency_ms:.1f} ms", (35, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            flap_status = "TANGAN DI ATAS BAHU" if is_above else "TANGAN DI BAWAH BAHU"
            flap_color = (0, 255, 0) if is_above else (200, 200, 200)
            cv2.putText(frame, f"Kepak Sayap: {flap_status}", (35, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, flap_color, 2)

            cv2.putText(frame, f"Total Flap Count: {flap_count}  |  Tilt: {tilt:+.2f}", (35, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)

            cv2.putText(frame, "Pastikan seluruh rentang tangan terlihat di webcam", (35, 165),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 150, 150), 1)

            cv2.imshow("AR Dragon - Anti-Glitch Pose Test", frame)
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
