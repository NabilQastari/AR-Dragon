"""
camera_stream.py
Threaded Bufferless Video Capture untuk menghilangkan lag/delay webcam di Windows OpenCV.
- Mengaktifkan hardware codec MJPG (30-60 FPS)
- Thread background khusus membaca kamera secara kontinu dan hanya menyimpan frame terbaru (Zero Buffer Delay)
"""

import threading
import time
import cv2

class ThreadedCamera:
    def __init__(self, src=0, width=1280, height=720, fps=30):
        self.src = src
        self.width = width
        self.height = height
        self.target_fps = fps

        # Inisialisasi DirectShow dengan fallback
        self.cap = cv2.VideoCapture(self.src, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = cv2.VideoCapture(self.src)

        # Aktifkan MJPG codec agar bandwidth USB tidak mencekik kamera ke 8-10 FPS
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.ret = False
        self.frame = None
        self.stopped = False
        self.lock = threading.Lock()

        # Baca frame awal
        self.ret, self.frame = self.cap.read()
        if not self.ret or self.frame is None:
            # Fallback jika MJPG 720p tidak didukung webcam, coba tanpa paksa MJPG
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.ret, self.frame = self.cap.read()

        # Jalankan thread pembaca kamera
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        while not self.stopped:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.005)
                continue
            with self.lock:
                self.ret = ret
                self.frame = frame

    def read(self):
        with self.lock:
            if self.frame is not None:
                return self.ret, self.frame.copy()
            return self.ret, None

    def release(self):
        self.stopped = True
        if self.thread.is_alive():
            self.thread.join(timeout=0.5)
        self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
