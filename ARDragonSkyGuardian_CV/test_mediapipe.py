"""
test_mediapipe.py
Pengujian interaktif MediaPipe Pose FULL + Instant Mouth Water Breath Tracker.
- Pose: MediaPipe Pose FULL (Gerakan Tubuh Atas & Kepak Sayap Anti-Glitch)
- Mulut: MouthTracker (Instant MAR + jawOpen, Zero Delay, Hysteresis Trigger)
- Kamera: ThreadedCamera (MJPG 30 FPS, Zero Buffer Lag)
- UDP: 127.0.0.1:5052 (13 Float CSV)
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
from camera_stream import ThreadedCamera
from pose_stabilizer import PoseStabilizer
from mouth_tracker import MouthTracker

def main():
    pose_model_path = os.path.join(os.path.dirname(__file__), "pose_landmarker_full.task")
    if not os.path.exists(pose_model_path):
        pose_model_path = os.path.join(os.path.dirname(__file__), "pose_landmarker_lite.task")

    print("[*] Memuat Pose Landmarker...")
    pose_opts = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=pose_model_path),
        output_segmentation_masks=False,
        running_mode=vision.RunningMode.IMAGE
    )
    pose_detector = vision.PoseLandmarker.create_from_options(pose_opts)

    print("[*] Memuat Instant Mouth Tracker (MAR + Blendshapes)...")
    mouth_tracker = MouthTracker()

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    stabilizer = PoseStabilizer()

    print("[*] Mengaktifkan Kamera Kecepatan Tinggi (MJPG 30 FPS)...")
    cam = ThreadedCamera(src=0, width=1280, height=720, fps=30)
    time.sleep(0.5)

    print("=" * 65)
    print("🚀 MENJALANKAN UJI MEDIAPIPE (INSTANT WATER BREATH)")
    print("   - Gerakan Tubuh: Kepak Sayap, Belok, Hover")
    print("   - Mulut Instan : Buka Mulut Wajar Langsung Sembur (Zero Delay)")
    print("   - UDP          : 127.0.0.1:5052 (13 Float CSV)")
    print("   - Tekan 'q' atau ESC untuk keluar")
    print("=" * 65)

    prev_time = time.time()
    fps_history = []
    flap_count = 0
    prev_above = False

    IDX_LS, IDX_RS = 11, 12
    IDX_LE, IDX_RE = 13, 14
    IDX_LW, IDX_RW = 15, 16
    IDX_LH, IDX_RH = 23, 24

    try:
        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            t_start = time.perf_counter()

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # 1. Deteksi Pose
            pose_result = pose_detector.detect(mp_image)

            # 2. Deteksi Mulut Instan (MAR + Blendshapes)
            is_water_breathing, mouth_score, mouth_center = mouth_tracker.process_frame(mp_image, w, h)

            latency_ms = (time.perf_counter() - t_start) * 1000.0

            pose_detected = False
            is_above = False

            if pose_result.pose_landmarks and len(pose_result.pose_landmarks) > 0:
                landmarks = pose_result.pose_landmarks[0]
                if len(landmarks) > max(IDX_LH, IDX_RH):
                    pose_detected = True
                    raw_ls = (landmarks[IDX_LS].x, landmarks[IDX_LS].y)
                    raw_rs = (landmarks[IDX_RS].x, landmarks[IDX_RS].y)
                    raw_lw = (landmarks[IDX_LW].x, landmarks[IDX_LW].y)
                    raw_rw = (landmarks[IDX_RW].x, landmarks[IDX_RW].y)
                    raw_lh = (landmarks[IDX_LH].x, landmarks[IDX_LH].y)
                    raw_rh = (landmarks[IDX_RH].x, landmarks[IDX_RH].y)
                    raw_le = (landmarks[IDX_LE].x, landmarks[IDX_LE].y)
                    raw_re = (landmarks[IDX_RE].x, landmarks[IDX_RE].y)

                    ls = stabilizer.update_point("ls", raw_ls[0], raw_ls[1])
                    rs = stabilizer.update_point("rs", raw_rs[0], raw_rs[1])
                    lw = stabilizer.update_point("lw", raw_lw[0], raw_lw[1], shoulder_ref=ls)
                    rw = stabilizer.update_point("rw", raw_rw[0], raw_rw[1], shoulder_ref=rs)
                    lh = stabilizer.update_point("lh", raw_lh[0], raw_lh[1])
                    rh = stabilizer.update_point("rh", raw_rh[0], raw_rh[1])

                    # Kirim UDP 13 float: 12 koordinat pose + 1 status mulut (1.0 jika aktif, 0.0 jika tidak)
                    udp_mouth_val = 1.0 if is_water_breathing else mouth_score
                    sender.send_pose(ls, rs, lw, rw, lh, rh, mouth_open=udp_mouth_val)

                    is_above = (lw[1] < ls[1]) and (rw[1] < rs[1])
                    if is_above != prev_above:
                        flap_count += 1
                        prev_above = is_above

                    def to_px(pt):
                        return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                    p_ls, p_rs = to_px(ls), to_px(rs)
                    p_lw, p_rw = to_px(lw), to_px(rw)
                    p_lh, p_rh = to_px(lh), to_px(rh)
                    p_le, p_re = to_px(raw_le), to_px(raw_re)

                    cv2.line(frame, (0, p_ls[1]), (w, p_rs[1]), (80, 80, 80), 1, cv2.LINE_AA)

                    color_bone = (255, 200, 0)
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

                    hand_color = (0, 255, 0) if is_above else (255, 0, 255)
                    cv2.circle(frame, p_lw, 13, hand_color, -1)
                    cv2.circle(frame, p_rw, 13, hand_color, -1)

                    tilt = lw[1] - rw[1]
                else:
                    tilt = 0.0
            else:
                tilt = 0.0

            # Efek Visual Semburan Air Instan
            if is_water_breathing and mouth_center is not None:
                mx, my = mouth_center
                # Lingkaran aura air bercahaya
                for r_ring in [15, 28, 45]:
                    cv2.circle(frame, (mx, my), r_ring, (255, 220, 0), 2)
                # Partikel semburan air memancar deras
                for _ in range(12):
                    offset_x = np.random.randint(-30, 31)
                    offset_y = np.random.randint(15, 85)
                    cv2.circle(frame, (mx + offset_x, my + offset_y), np.random.randint(4, 9), (255, 255, 120), -1)

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

            cv2.putText(frame, "MediaPipe: Full Pose + Instant Water Breath", (35, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 255), 2)
            cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi Total: {latency_ms:.1f} ms", (35, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            flap_status = "DI ATAS BAHU" if is_above else "DI BAWAH BAHU"
            cv2.putText(frame, f"Kepak Sayap: {flap_status} (Flap: {flap_count})", (35, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)

            # Indikator Mulut Terbuka
            breath_str = f"SEMBUR AIR AKTIF! ({mouth_score:.2f})" if is_water_breathing else f"Mulut Tertutup ({mouth_score:.2f})"
            breath_col = (255, 220, 0) if is_water_breathing else (160, 160, 160)
            cv2.putText(frame, f"Aksi Mulut : {breath_str}", (35, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, breath_col, 2)

            cv2.putText(frame, f"Tilt Belok : {tilt:+.2f} | UDP: [0..11] Pose + [12] Mulut", (35, 170),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

            cv2.imshow("AR Dragon - MediaPipe Instant Breath Test", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
        sender.close()
        print("[*] Selesai pengujian MediaPipe.")

if __name__ == "__main__":
    main()
