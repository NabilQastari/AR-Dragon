"""
test_rtmpose.py
Pengujian interaktif RTMPose (via rtmlib + ONNX Runtime GPU CUDA) + High Performance Stream + Adaptive Stabilizer.
- ThreadedCamera (MJPG, Zero Buffer Lag)
- PoseStabilizer (One-Euro Filter)
- UDP 127.0.0.1:5052
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
ort.preload_dlls()
from rtmlib import Body
from udp_sender import PoseUDPSender
from camera_stream import ThreadedCamera
from pose_stabilizer import PoseStabilizer

def main():
    print("[*] Menginisialisasi RTMPose (mode='lightweight', backend='onnxruntime', device='cuda')...")
    try:
        body = Body(mode='lightweight', backend='onnxruntime', device='cuda')
        device_name = "CUDA (RTX 3050)"
    except Exception as e:
        print(f"[!] Gagal inisialisasi CUDA, fallback ke CPU: {e}")
        body = Body(mode='lightweight', backend='onnxruntime', device='cpu')
        device_name = "CPU (Fallback)"

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    stabilizer = PoseStabilizer(min_cutoff=1.5, beta=0.08)

    print("[*] Mengaktifkan Kamera Berkecapatan Tinggi (MJPG 30 FPS)...")
    cam = ThreadedCamera(src=0, width=1280, height=720, fps=30)
    time.sleep(0.5)

    print("=" * 65)
    print(f"🚀 MENJALANKAN UJI RTMPOSE OPTIMAL ({device_name})")
    print("   - Kamera : Threaded Zero-Lag Stream (MJPG)")
    print("   - Filter : Adaptive One-Euro Pose Stabilizer (Anti-Jitter)")
    print("   - UDP    : 127.0.0.1:5052")
    print("   - Tekan 'q' atau ESC untuk keluar")
    print("=" * 65)

    prev_time = time.time()
    fps_history = []

    IDX_LS, IDX_RS = 5, 6
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

            keypoints, scores = body(frame)
            latency_ms = (time.perf_counter() - t_start) * 1000.0

            pose_detected = False
            if keypoints is not None and len(keypoints) > 0:
                kpts = keypoints[0]
                if len(kpts) >= 13:
                    pose_detected = True

                    raw_ls = (float(kpts[IDX_LS][0]) / w, float(kpts[IDX_LS][1]) / h)
                    raw_rs = (float(kpts[IDX_RS][0]) / w, float(kpts[IDX_RS][1]) / h)
                    raw_lw = (float(kpts[IDX_LW][0]) / w, float(kpts[IDX_LW][1]) / h)
                    raw_rw = (float(kpts[IDX_RW][0]) / w, float(kpts[IDX_RW][1]) / h)
                    raw_lh = (float(kpts[IDX_LH][0]) / w, float(kpts[IDX_LH][1]) / h)
                    raw_rh = (float(kpts[IDX_RH][0]) / w, float(kpts[IDX_RH][1]) / h)

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

                    color_bone = (255, 100, 200)
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

            cv2.putText(frame, f"Model: RTMPose ({device_name})", (35, 50),
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

            cv2.imshow("AR Dragon - RTMPose Test", frame)
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
