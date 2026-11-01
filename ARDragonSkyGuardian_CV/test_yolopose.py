"""
test_yolopose.py
Pengujian interaktif YOLOv8n-pose (CUDA) + Face Landmarker (Mulut Terbuka / Sembur Air) + Kepak Sayap Anti-Glitch.
- Pose: YOLOv8n-pose (CUDA GPU) dengan Kinematic Arm Clamping
- Wajah & Mulut: MediaPipe Face Landmarker Blendshapes (jawOpen) untuk Sembur Air
- Kamera: ThreadedCamera (MJPG 30 FPS, Zero Buffer Lag)
- UDP: 127.0.0.1:5052 (13 Float CSV)
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
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

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
    pose_model = YOLO(model_path)
    if device.startswith("cuda"):
        pose_model.to(device)

    # Inisialisasi Face Landmarker untuk deteksi mulut terbuka
    face_model_path = os.path.join(os.path.dirname(__file__), "face_landmarker.task")
    face_detector = None
    if os.path.exists(face_model_path):
        print("[*] Memuat Face Landmarker (jawOpen Blendshapes)...")
        face_opts = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=face_model_path),
            output_face_blendshapes=True,
            num_faces=1,
            running_mode=vision.RunningMode.IMAGE
        )
        face_detector = vision.FaceLandmarker.create_from_options(face_opts)

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    stabilizer = PoseStabilizer()

    print("[*] Mengaktifkan Kamera Kecepatan Tinggi (MJPG 30 FPS)...")
    cam = ThreadedCamera(src=0, width=1280, height=720, fps=30)
    time.sleep(0.5)

    print("=" * 65)
    print(f"🚀 MENJALANKAN UJI YOLO-POSE (Pose CUDA + Mulut Sembur Air)")
    print("   - Gerakan Tubuh: Kepak Sayap (Flapping), Gliding, Belok")
    print("   - Aksi Mulut   : Buka Mulut Lebar -> Semburan Air Naga")
    print("   - Kamera       : Threaded Zero-Lag Stream (MJPG)")
    print("   - UDP          : 127.0.0.1:5052 (13 Float CSV)")
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

            # 1. Inferensi Pose via YOLO (GPU CUDA)
            results = pose_model(frame, device=device, imgsz=640, verbose=False, conf=0.25)

            # 2. Inferensi Mulut via Face Landmarker Blendshapes
            jaw_open_score = 0.0
            mouth_center = None
            if face_detector is not None:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                face_result = face_detector.detect(mp_image)
                if face_result.face_blendshapes and len(face_result.face_blendshapes) > 0:
                    for category in face_result.face_blendshapes[0]:
                        if category.category_name == "jawOpen":
                            jaw_open_score = float(category.score)
                            break
                if face_result.face_landmarks and len(face_result.face_landmarks) > 0:
                    lm = face_result.face_landmarks[0]
                    lip_top, lip_bot = lm[13], lm[14]
                    mouth_center = (int((lip_top.x + lip_bot.x) * 0.5 * w), int((lip_top.y + lip_bot.y) * 0.5 * h))

            latency_ms = (time.perf_counter() - t_start) * 1000.0

            pose_detected = False
            is_above = False
            is_water_breathing = (jaw_open_score >= 0.35)

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

                        ls = stabilizer.update_point("ls", raw_ls_x, raw_ls_y, c_ls)
                        rs = stabilizer.update_point("rs", raw_rs_x, raw_rs_y, c_rs)
                        lw = stabilizer.update_point("lw", raw_lw_x, raw_lw_y, c_lw, shoulder_ref=ls)
                        rw = stabilizer.update_point("rw", raw_rw_x, raw_rw_y, c_rw, shoulder_ref=rs)
                        lh = stabilizer.update_point("lh", raw_lh_x, raw_lh_y, c_lh)
                        rh = stabilizer.update_point("rh", raw_rh_x, raw_rh_y, c_rh)

                        # Kirim UDP 13 float
                        sender.send_pose(ls, rs, lw, rw, lh, rh, mouth_open=jaw_open_score)

                        # Kepak sayap
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

                        cv2.line(frame, (0, p_ls[1]), (w, p_rs[1]), (80, 80, 80), 1, cv2.LINE_AA)

                        color_bone = (0, 255, 180)
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

            # Efek Partikel Air Semburan Naga
            if is_water_breathing and mouth_center is not None:
                mx, my = mouth_center
                for r_ring in [15, 30, 48]:
                    cv2.circle(frame, (mx, my), r_ring, (255, 200, 0), 2)
                for _ in range(8):
                    offset_x = np.random.randint(-25, 26)
                    offset_y = np.random.randint(10, 75)
                    cv2.circle(frame, (mx + offset_x, my + offset_y), np.random.randint(3, 7), (255, 255, 100), -1)

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

            cv2.putText(frame, f"YOLOv8n-pose (CUDA) + Face Water Breath", (35, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 255), 2)
            cv2.putText(frame, f"FPS: {avg_fps:.1f}  |  Latensi Total: {latency_ms:.1f} ms", (35, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            flap_status = "DI ATAS BAHU" if is_above else "DI BAWAH BAHU"
            cv2.putText(frame, f"Kepak Sayap: {flap_status} (Flap: {flap_count})", (35, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)

            breath_str = f"SEMBUR AIR AKTIF! ({jaw_open_score:.2f})" if is_water_breathing else f"Mulut Tertutup ({jaw_open_score:.2f})"
            breath_col = (255, 200, 0) if is_water_breathing else (160, 160, 160)
            cv2.putText(frame, f"Aksi Mulut : {breath_str}", (35, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, breath_col, 2)

            cv2.putText(frame, f"Tilt Belok : {tilt:+.2f} | UDP: [0..11] Pose + [12] Mulut", (35, 170),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

            cv2.imshow("AR Dragon - YOLO-Pose & Water Breath Test", frame)
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
