"""
test_rtmpose.py
Pengujian interaktif RTMPose (via rtmlib + ONNX Runtime GPU CUDA) + UDP Sender.
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
import glob
import time
import tempfile
import cv2
import numpy as np

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()

# Pastikan DLL NVIDIA CUDA 12 & cuDNN v9 di dalam venv terbaca oleh Windows & ONNX Runtime
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
ort.preload_dlls()
from rtmlib import Body
from udp_sender import PoseUDPSender

def main():
    print("[*] Menginisialisasi RTMPose (mode='lightweight', backend='onnxruntime', device='cuda')...")
    try:
        body = Body(mode='lightweight', backend='onnxruntime', device='cuda')
        device_name = "CUDA (RTX 3050)"
    except Exception as e:
        print(f"[!] Gagal inisialisasi CUDA, fallback ke CPU: {e}")
        body = Body(mode='lightweight', backend='onnxruntime', device='cpu')
        device_name = "CPU (Fallback)"

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
    print(f"🚀 MENJALANKAN UJI RTMPOSE ({device_name})")
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

        # Inferensi RTMPose
        keypoints, scores = body(frame)
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        # Koordinat default
        ls = (0.45, 0.40)
        rs = (0.55, 0.40)
        lw = (0.35, 0.55)
        rw = (0.65, 0.55)
        lh = (0.45, 0.70)
        rh = (0.55, 0.70)

        pose_detected = False
        if keypoints is not None and len(keypoints) > 0:
            kpts = keypoints[0]  # Bentuk: (17, 2)
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

                color_line = (255, 100, 200)
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

        cv2.putText(frame, f"Model: RTMPose ({device_name})", (30, 45),
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

        cv2.imshow("AR Dragon - RTMPose Test", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    sender.close()
    print("[*] Selesai pengujian RTMPose.")

if __name__ == "__main__":
    main()
