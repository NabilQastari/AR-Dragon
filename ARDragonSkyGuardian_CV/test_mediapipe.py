"""
test_mediapipe.py
Pengujian interaktif MediaPipe Pose Landmarker + High Performance Stream + Adaptive Stabilizer.
- ThreadedCamera (MJPG, Zero Buffer Lag)
- PoseStabilizer (One-Euro Filter)
- UDP 127.0.0.1:5052
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

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    stabilizer = PoseStabilizer(min_cutoff=1.5, beta=0.08)

    print("[*] Mengaktifkan Kamera Berkecapatan Tinggi (MJPG 30 FPS)...")
    cam = ThreadedCamera(src=0, width=1280, height=720, fps=30)
    time.sleep(0.5)

    print("=" * 65)
    print("🚀 MENJALANKAN UJI MEDIAPIPE POSE OPTIMAL")
    print("   - Kamera : Threaded Zero-Lag Stream (MJPG)")
    print("   - Filter : Adaptive One-Euro Pose Stabilizer (Anti-Jitter)")
    print("   - UDP    : 127.0.0.1:5052")
    print("   - Tekan 'q' atau ESC untuk keluar")
    print("=" * 65)

    prev_time = time.time()
    fps_history = []

    IDX_LS, IDX_RS = 11, 12
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

            detection_result = detector.detect(mp_image)
            latency_ms = (time.perf_counter() - t_start) * 1000.0

            pose_detected = False
            if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
                landmarks = detection_result.pose_landmarks[0]
                if len(landmarks) > max(IDX_LH, IDX_RH):
                    pose_detected = True
                    raw_ls = (landmarks[IDX_LS].x, landmarks[IDX_LS].y)
                    raw_rs = (landmarks[IDX_RS].x, landmarks[IDX_RS].y)
                    raw_lw = (landmarks[IDX_LW].x, landmarks[IDX_LW].y)
                    raw_rw = (landmarks[IDX_RW].x, landmarks[IDX_RW].y)
                    raw_lh = (landmarks[IDX_LH].x, landmarks[IDX_LH].y)
                    raw_rh = (landmarks[IDX_RH].x, landmarks[IDX_RH].y)

                    ls = stabilizer.update_point("ls", raw_ls[0], raw_ls[1])
                    rs = stabilizer.update_point("rs", raw_rs[0], raw_rs[1])
                    lw = stabilizer.update_point("lw", raw_lw[0], raw_lw[1])
                    rw = stabilizer.update_point("rw", raw_rw[0], raw_rw[1])
                    lh = stabilizer.update_point("lh", raw_lh[0], raw_lh[1])
                    rh = stabilizer.update_point("rh", raw_rh[0], raw_rh[1])

                    sender.send_pose(ls, rs, lw, rw, lh, rh)

                    def to_px(pt):
                        return (int(np.clip(pt[0], 0, 1) * w), int(np.clip(pt[1], 0, 1) * h))

                    p_ls, p_rs = to_px(ls), to_px(rs)
                    p_lw, p_rw = to_px(lw), to_px(rw)
                    p_lh, p_rh = to_px(lh), to_px(rh)

                    color_bone = (255, 200, 0)
                    cv2.line(frame, p_ls, p_rs, color_bone, 3)
                    cv2.line(frame, p_ls, p_lw, color_bone, 3)
                    cv2.line(frame, p_rs, p_rw, color_bone, 3)
                    cv2.line(frame, p_ls, p_lh, color_bone, 3)
                    cv2.line(frame, p_rs, p_rh, color_bone, 3)
                    cv2.line(frame, p_lh, p_rh, color_bone, 3)

                    cv2.circle(frame, p_ls, 8, (0, 255, 255), -1)
                    cv2.circle(frame, p_rs, 8, (0, 255, 255), -1)
                    cv2.circle(frame, p_lw, 11, (255, 0, 255), -1)
                    cv2.circle(frame, p_rw, 11, (0, 255, 0), -1)
                    cv2.circle(frame, p_lh, 7, (0, 165, 255), -1)
                    cv2.circle(frame, p_rh, 7, (0, 165, 255), -1)

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

            overlay = frame.copy()
            cv2.rectangle(overlay, (20, 20), (460, 165), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

            cv2.putText(frame, "Model: MediaPipe Pose (CPU Lite)", (35, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
            cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi AI: {latency_ms:.1f} ms", (35, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 0), 2)

            status_str = "Zero-Lag Stream [UDP ON]" if pose_detected else "Mencari Tubuh..."
            status_col = (0, 255, 0) if pose_detected else (0, 0, 255)
            cv2.putText(frame, f"Status: {status_str}", (35, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_col, 2)

            if abs(tilt) < 0.08:
                action_text = "Lurus (Gliding)"
            elif tilt > 0.08:
                action_text = f"Belok Kanan ({tilt:+.2f})"
            else:
                action_text = f"Belok Kiri ({tilt:+.2f})"

            cv2.putText(frame, f"Arah: {action_text} | Jarak Tangan: {dist:.2f}", (35, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)

            cv2.imshow("AR Dragon - MediaPipe Pose Test", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
        sender.close()
        print("[*] Selesai pengujian MediaPipe Pose.")

if __name__ == "__main__":
    main()
