"""
test_rtmpose.py
Pengujian interaktif RTMPose (via rtmlib + ONNX Runtime GPU CUDA) + Zero-Delay Head-Cropped Water Breath Tracker.
- Pose: RTMPose (CUDA) dengan Kinematic Arm Clamping
- Mulut: Head-Cropped Instant Mouth Tracker (~5 ms, Zero Delay)
- Kamera: ThreadedCamera (MJPG 30 FPS, Zero Buffer Lag)
- UDP: 127.0.0.1:5052 (13 Float CSV)
"""

import os
import sys
import glob
import time
import tempfile
import cv2
import numpy as np

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()

venv_nvidia = os.path.join(sys.prefix, 'Lib', 'site-packages', 'nvidia')
if os.path.isdir(venv_nvidia):
    bins = [b for b in glob.glob(os.path.join(venv_nvidia, '*', 'bin')) if os.path.isdir(b)]
    if bins:
        os.environ['PATH'] = ';'.join(bins) + ';' + os.environ.get('PATH', '')
        for b in bins:
            try:
                os.add_dll_directory(b)
            except Exception:
                pass

import onnxruntime as ort
ort.set_default_logger_severity(3)
ort.preload_dlls()
from rtmlib import Body

from udp_sender import PoseUDPSender
from camera_stream import ThreadedCamera
from pose_stabilizer import PoseStabilizer
from mouth_tracker import MouthTracker

def main():
    print("[*] Menginisialisasi RTMPose (mode='lightweight', backend='onnxruntime', device='cuda')...")
    try:
        body = Body(mode='lightweight', backend='onnxruntime', device='cuda')
        actual_ep = body.pose_model.session.get_providers()
        if 'CUDAExecutionProvider' in actual_ep:
            device_name = "CUDA (RTX 3050)"
            print(f"[OK] RTMPose aktif dengan CUDA GPU Acceleration ({actual_ep[0]})")
        else:
            device_name = "CPU (Fallback)"
            print(f"[!] Warning: CUDA tidak aktif di session, berjalan di: {actual_ep}")
    except Exception as e:
        print(f"[!] Gagal inisialisasi CUDA, fallback ke CPU: {e}")
        body = Body(mode='lightweight', backend='onnxruntime', device='cpu')
        device_name = "CPU (Fallback)"

    print("[*] Memuat Zero-Delay Head-Cropped Mouth Tracker...")
    mouth_tracker = MouthTracker()

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    stabilizer = PoseStabilizer()

    print("[*] Mengaktifkan Kamera Kecepatan Tinggi (MJPG 30 FPS)...")
    cam = ThreadedCamera(src=0, width=1280, height=720, fps=30)
    time.sleep(0.5)

    print("=" * 65)
    print(f"🚀 MENJALANKAN UJI RTMPOSE (ZERO-DELAY ARCHITECTURE)")
    print("   - Pose : RTMPose Lightweight ONNX CUDA")
    print("   - Mulut: Head-Crop Instant MAR (~5 ms, Zero Delay)")
    print("   - UDP  : 127.0.0.1:5052 (13 Float CSV)")
    print("   - Tekan 'q' atau ESC untuk keluar")
    print("=" * 65)

    prev_time = time.time()
    fps_history = []
    flap_count = 0
    prev_above = False
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

            # 1. Inferensi RTMPose
            keypoints, scores = body(frame)

            pose_detected = False
            is_above = False

            if keypoints is not None and len(keypoints) > 0:
                kpts = keypoints[0]
                scs = scores[0] if (scores is not None and len(scores) > 0) else None

                # Verifikasi pose riil (bahu terdeteksi dgn keypoint score > 0.25)
                valid_pose = True
                if scs is not None and len(scs) > IDX_RS:
                    if scs[IDX_LS] < 0.25 and scs[IDX_RS] < 0.25:
                        valid_pose = False

                if len(kpts) >= 13 and valid_pose:
                    pose_detected = True

                    raw_nose_x = float(kpts[IDX_NOSE][0]) / w
                    raw_nose_y = float(kpts[IDX_NOSE][1]) / h
                    head_pos = (raw_nose_x, raw_nose_y)

                    raw_ls = (float(kpts[IDX_LS][0]) / w, float(kpts[IDX_LS][1]) / h)
                    raw_rs = (float(kpts[IDX_RS][0]) / w, float(kpts[IDX_RS][1]) / h)
                    raw_lw = (float(kpts[IDX_LW][0]) / w, float(kpts[IDX_LW][1]) / h)
                    raw_rw = (float(kpts[IDX_RW][0]) / w, float(kpts[IDX_RW][1]) / h)
                    raw_lh = (float(kpts[IDX_LH][0]) / w, float(kpts[IDX_LH][1]) / h)
                    raw_rh = (float(kpts[IDX_RH][0]) / w, float(kpts[IDX_RH][1]) / h)
                    raw_le = (float(kpts[IDX_LE][0]) / w, float(kpts[IDX_LE][1]) / h)
                    raw_re = (float(kpts[IDX_RE][0]) / w, float(kpts[IDX_RE][1]) / h)

                    ls = stabilizer.update_point("ls", raw_ls[0], raw_ls[1])
                    rs = stabilizer.update_point("rs", raw_rs[0], raw_rs[1])
                    lw = stabilizer.update_point("lw", raw_lw[0], raw_lw[1], shoulder_ref=ls)
                    rw = stabilizer.update_point("rw", raw_rw[0], raw_rw[1], shoulder_ref=rs)
                    lh = stabilizer.update_point("lh", raw_lh[0], raw_lh[1])
                    rh = stabilizer.update_point("rh", raw_rh[0], raw_rh[1])

                    is_above = (lw[1] < ls[1]) and (rw[1] < rs[1])
                    if is_above != prev_above:
                        flap_count += 1
                        prev_above = is_above

                    tilt = lw[1] - rw[1]
                else:
                    tilt = 0.0
            else:
                tilt = 0.0

            # 2. Inferensi Mulut Terbuka via Crop Area Kepala (~5 ms)
            is_water_breathing, mouth_score, mouth_center = mouth_tracker.process_crop(frame, head_pos)

            if pose_detected:
                udp_mouth_val = 1.0 if is_water_breathing else mouth_score
                sender.send_pose(ls, rs, lw, rw, lh, rh, mouth_open=udp_mouth_val)

            latency_ms = (time.perf_counter() - t_start) * 1000.0

            # 3. Visualisasi Rendering Cepat
            if pose_detected:
                def to_px(pt):
                    return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                p_ls, p_rs = to_px(ls), to_px(rs)
                p_lw, p_rw = to_px(lw), to_px(rw)
                p_lh, p_rh = to_px(lh), to_px(rh)
                p_le, p_re = to_px(raw_le), to_px(raw_re)

                cv2.line(frame, (0, p_ls[1]), (w, p_rs[1]), (80, 80, 80), 1)

                color_bone = (255, 100, 200)
                cv2.line(frame, p_ls, p_rs, color_bone, 3)
                cv2.line(frame, p_ls, p_le, color_bone, 3)
                cv2.line(frame, p_le, p_lw, color_bone, 3)
                cv2.line(frame, p_rs, p_re, color_bone, 3)
                cv2.line(frame, p_re, p_rw, color_bone, 3)
                cv2.line(frame, p_ls, p_lh, color_bone, 3)
                cv2.line(frame, p_rs, p_rh, color_bone, 3)
                cv2.line(frame, p_lh, p_rh, color_bone, 3)

                cv2.circle(frame, p_ls, 7, (0, 255, 255), -1)
                cv2.circle(frame, p_rs, 7, (0, 255, 255), -1)

                hand_color = (0, 255, 0) if is_above else (255, 0, 255)
                cv2.circle(frame, p_lw, 12, hand_color, -1)
                cv2.circle(frame, p_rw, 12, hand_color, -1)

            # Efek Visual Semburan Air Instan
            if is_water_breathing and mouth_center is not None:
                mx, my = mouth_center
                cv2.circle(frame, (mx, my), 24, (255, 220, 0), 2)
                for _ in range(8):
                    ox = np.random.randint(-25, 26)
                    oy = np.random.randint(10, 60)
                    cv2.circle(frame, (mx + ox, my + oy), np.random.randint(3, 7), (255, 255, 120), -1)

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
            cv2.rectangle(overlay, (20, 20), (510, 195), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

            cv2.putText(frame, f"RTMPose [{device_name}] (Zero-Delay)", (35, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 255), 2)
            cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi Total: {latency_ms:.1f} ms", (35, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            flap_status = "DI ATAS BAHU" if is_above else "DI BAWAH BAHU"
            cv2.putText(frame, f"Kepak Sayap: {flap_status} (Flap: {flap_count})", (35, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)

            breath_str = f"SEMBUR AIR AKTIF! ({mouth_score:.2f})" if is_water_breathing else f"Mulut Tertutup ({mouth_score:.2f})"
            breath_col = (255, 220, 0) if is_water_breathing else (160, 160, 160)
            cv2.putText(frame, f"Aksi Mulut : {breath_str}", (35, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, breath_col, 2)

            cv2.putText(frame, f"Tilt Belok : {tilt:+.2f} | UDP: [0..11] Pose + [12] Mulut", (35, 170),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

            cv2.imshow("AR Dragon - RTMPose Zero-Delay Test", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
        sender.close()
        print("[*] Selesai pengujian RTMPose.")

if __name__ == "__main__":
    main()
