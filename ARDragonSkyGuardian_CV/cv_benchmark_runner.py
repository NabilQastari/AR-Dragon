"""
cv_benchmark_runner.py
Skrip pengujian otomatis (benchmark) untuk 3 framework Computer Vision:
1. MediaPipe Pose
2. YOLOv8n-pose
3. RTMPose (rtmlib + ONNX Runtime GPU)

Setiap model diuji selama 15 detik. Hasil perbandingan performa (FPS, Latensi, Jitter)
akan dihitung dan disimpan ke dalam file 'cv_benchmark_report.txt'.
"""

import os
import sys
import glob
import time
import tempfile
import cv2
import numpy as np
import torch

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()

# Konfigurasi DLL NVIDIA CUDA 12 & cuDNN v9
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
from ultralytics import YOLO
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import mediapipe as mp

TEST_DURATION_SEC = 15.0

def benchmark_model(model_name: str, init_fn, infer_fn, cap):
    print(f"\n[+] Memulai pengujian untuk: {model_name}...")
    model_obj = init_fn()

    # Warmup 5 frame
    for _ in range(5):
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frame = cv2.flip(frame, 1)
        _ = infer_fn(model_obj, frame)

    frame_times = []
    latencies = []
    detections = 0
    total_frames = 0

    start_time = time.time()
    last_frame_time = time.perf_counter()

    while True:
        elapsed = time.time() - start_time
        if elapsed >= TEST_DURATION_SEC:
            break

        ret, frame = cap.read()
        if not ret or frame is None:
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        t0 = time.perf_counter()
        has_pose = infer_fn(model_obj, frame)
        t1 = time.perf_counter()

        latency_ms = (t1 - t0) * 1000.0
        latencies.append(latency_ms)

        now = time.perf_counter()
        dt = now - last_frame_time
        last_frame_time = now
        if dt > 0:
            frame_times.append(dt)

        total_frames += 1
        if has_pose:
            detections += 1

        # Gambar UI benchmark pada layar
        remaining = max(0.0, TEST_DURATION_SEC - elapsed)
        progress = elapsed / TEST_DURATION_SEC

        # Overlay banner
        cv2.rectangle(frame, (20, 20), (520, 140), (25, 25, 25), -1)
        cv2.putText(frame, f"BENCHMARK: {model_name}", (35, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, f"Sisa Waktu: {remaining:4.1f} s | Frames: {total_frames}", (35, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        curr_fps = 1.0 / dt if dt > 0 else 30.0
        cv2.putText(frame, f"FPS: {curr_fps:4.1f} | Latensi: {latency_ms:4.1f} ms", (35, 115),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        # Progress bar
        bar_x, bar_y, bar_w, bar_h = 35, 125, 450, 8
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (80, 80, 80), -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(bar_w * progress), bar_y + bar_h), (0, 200, 255), -1)

        cv2.imshow("AR Dragon - Computer Vision Benchmark", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC untuk batalkan
            print("[!] Benchmark dihentikan oleh pengguna.")
            break

    # Hitung metrik
    fps_list = [1.0 / dt for dt in frame_times if dt > 0]
    avg_fps = float(np.mean(fps_list)) if fps_list else 0.0
    min_fps = float(np.min(fps_list)) if fps_list else 0.0
    max_fps = float(np.max(fps_list)) if fps_list else 0.0
    avg_latency = float(np.mean(latencies)) if latencies else 0.0

    # Jitter dihitung dari standar deviasi interval antar-frame (dalam milidetik)
    jitter_ms = float(np.std(frame_times) * 1000.0) if len(frame_times) > 1 else 0.0
    det_rate = (detections / total_frames * 100.0) if total_frames > 0 else 0.0

    print(f"   ✔ {model_name} selesai: Avg FPS = {avg_fps:.1f}, Latensi = {avg_latency:.1f} ms, Jitter = {jitter_ms:.2f} ms")

    return {
        "model": model_name,
        "avg_fps": avg_fps,
        "min_fps": min_fps,
        "max_fps": max_fps,
        "avg_latency": avg_latency,
        "jitter_ms": jitter_ms,
        "total_frames": total_frames,
        "det_rate": det_rate
    }

def main():
    print("=" * 65)
    print("🏁 BENCHMARK RUNNER: PERBANDINGAN MODEL COMPUTER VISION (15s/Model)")
    print("=" * 65)

    # 1. Buka Kamera
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("[!] Gagal membuka webcam untuk pengujian benchmark.")
        return

    # Definisi fungsi inisialisasi & inferensi tiap model
    # Model 1: MediaPipe Pose
    def init_mp():
        model_path = os.path.join(os.path.dirname(__file__), "pose_landmarker_lite.task")
        base_opts = python.BaseOptions(model_asset_path=model_path)
        opts = vision.PoseLandmarkerOptions(base_options=base_opts, output_segmentation_masks=False)
        return vision.PoseLandmarker.create_from_options(opts)

    def infer_mp(detector, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = detector.detect(mp_img)
        return bool(res.pose_landmarks and len(res.pose_landmarks) > 0)

    # Model 2: YOLOv8n-pose
    def init_yolo():
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        model_path = os.path.join(os.path.dirname(__file__), "yolov8n-pose.pt")
        m = YOLO(model_path)
        if device.startswith("cuda"):
            m.to(device)
        return (m, device)

    def infer_yolo(yolo_pack, frame):
        m, dev = yolo_pack
        res = m(frame, device=dev, verbose=False, conf=0.35)
        if res and len(res) > 0 and res[0].keypoints is not None:
            kd = res[0].keypoints.data
            return bool(kd is not None and len(kd) > 0)
        return False

    # Model 3: RTMPose
    def init_rtm():
        try:
            return Body(mode='lightweight', backend='onnxruntime', device='cuda')
        except Exception:
            return Body(mode='lightweight', backend='onnxruntime', device='cpu')

    def infer_rtm(body_obj, frame):
        kpts, scores = body_obj(frame)
        return bool(kpts is not None and len(kpts) > 0)

    models_to_test = [
        ("MediaPipe Pose (CPU Lite)", init_mp, infer_mp),
        ("YOLOv8n-pose (CUDA GPU)", init_yolo, infer_yolo),
        ("RTMPose (rtmlib + ONNX CUDA)", init_rtm, infer_rtm)
    ]

    results = []
    for name, init_f, infer_f in models_to_test:
        res = benchmark_model(name, init_f, infer_f, cap)
        results.append(res)
        time.sleep(1.0)

    cap.release()
    cv2.destroyAllWindows()

    # Tulis laporan ke cv_benchmark_report.txt
    report_path = os.path.join(os.path.dirname(__file__), "cv_benchmark_report.txt")
    timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")

    report_lines = [
        "=" * 75,
        f" LAPORAN BENCHMARK COMPUTER VISION: AR DRAGON SKY GUARDIAN",
        f" Waktu Pengujian : {timestamp_str}",
        f" Durasi Uji Tiap Model : {TEST_DURATION_SEC} Detik",
        "=" * 75,
        "",
        f"{'Model':<30} | {'Avg FPS':<8} | {'Min/Max FPS':<12} | {'Latensi (ms)':<12} | {'Jitter (ms)':<10}",
        "-" * 82,
    ]

    for r in results:
        fps_range = f"{r['min_fps']:.0f} / {r['max_fps']:.0f}"
        line = f"{r['model']:<30} | {r['avg_fps']:>7.1f} | {fps_range:>12} | {r['avg_latency']:>12.1f} | {r['jitter_ms']:>10.2f}"
        report_lines.append(line)

    report_lines.extend([
        "-" * 82,
        "",
        "KETERANGAN METRIK:",
        "1. Avg FPS: Rata-rata frame per detik (Target minimal: 30 FPS untuk gameplay mulus).",
        "2. Latensi: Rata-rata waktu komputasi inferensi model per frame dalam milidetik.",
        "3. Jitter: Standar deviasi kestabilan jeda antar-frame (Semakin kecil semakin stabil/mulus).",
        "4. Semua model mengirim paket UDP 12-float CSV ke 127.0.0.1:5052.",
        "=" * 75
    ])

    report_content = "\n".join(report_lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print("\n" + report_content)
    print(f"\n[OK] Laporan berhasil disimpan ke: {report_path}")

if __name__ == "__main__":
    main()
