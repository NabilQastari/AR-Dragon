"""
udp_sender.py
Modul pengirim data UDP untuk posisi keypoint pose + Status Mulut Terbuka,
serta pengirim frame video JPEG terkompresi untuk Unity In-Game PIP Preview.
Format CSV: LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y,MOUTH_OPEN
- 12 float pertama: Koordinat ternormalisasi (0.0000 - 1.0000)
- Nilai ke-13: Nilai mulut terbuka (0.0000 = tertutup rapat, 1.0000 = terbuka lebar)
"""

import socket
import cv2
import numpy as np
from typing import Tuple

class PoseUDPSender:
    def __init__(self, ip: str = "127.0.0.1", port: int = 5052):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_pose(
        self,
        ls: Tuple[float, float],
        rs: Tuple[float, float],
        lw: Tuple[float, float],
        rw: Tuple[float, float],
        lh: Tuple[float, float],
        rh: Tuple[float, float],
        mouth_open: float = 0.0,
    ) -> bool:
        """
        Mengirim 12 nilai koordinat tubuh + 1 nilai mulut terbuka (jawOpen).
        """
        try:
            def clamp(val: float) -> float:
                return max(0.0, min(1.0, float(val)))

            csv_string = (
                f"{clamp(ls[0]):.4f},{clamp(ls[1]):.4f},"
                f"{clamp(rs[0]):.4f},{clamp(rs[1]):.4f},"
                f"{clamp(lw[0]):.4f},{clamp(lw[1]):.4f},"
                f"{clamp(rw[0]):.4f},{clamp(rw[1]):.4f},"
                f"{clamp(lh[0]):.4f},{clamp(lh[1]):.4f},"
                f"{clamp(rh[0]):.4f},{clamp(rh[1]):.4f},"
                f"{clamp(mouth_open):.4f}"
            )
            self.sock.sendto(csv_string.encode("utf-8"), (self.ip, self.port))
            return True
        except Exception:
            return False

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class VideoUDPSender:
    """
    Mengirim frame video webcam (downscaled JPEG) melalui UDP ke Unity PIP.
    Default port: 5053. Ringan (~3 KB per frame) dan zero-conflict dengan OpenCV webcam.
    """
    def __init__(self, ip: str = "127.0.0.1", port: int = 5053, width: int = 320, height: int = 180, quality: int = 48):
        self.ip = ip
        self.port = port
        self.target_size = (width, height)
        self.encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        except Exception:
            pass

    def send_frame(self, frame: np.ndarray) -> bool:
        if frame is None:
            return False
        try:
            # Resize ke ukuran thumbnail preview PIP
            small_frame = cv2.resize(frame, self.target_size, interpolation=cv2.INTER_AREA)
            success, encoded_img = cv2.imencode('.jpg', small_frame, self.encode_param)
            if not success:
                return False

            data = encoded_img.tobytes()
            # UDP MTU safety check (< 65000 bytes)
            if len(data) <= 65000:
                self.sock.sendto(data, (self.ip, self.port))
                return True
            return False
        except Exception:
            return False

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

