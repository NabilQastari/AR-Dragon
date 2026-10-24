"""
udp_sender.py
Modul pengirim data UDP untuk posisi keypoint pose (12-float CSV string).
Format: LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y
Semua nilai ternormalisasi (0.0000 - 1.0000).
"""

import socket
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
    ) -> bool:
        """
        Mengirim 6 pasangan koordinat (12 float) ternormalisasi.
        LS: Left Shoulder, RS: Right Shoulder
        LW: Left Wrist,    RW: Right Wrist
        LH: Left Hip,      RH: Right Hip
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
                f"{clamp(rh[0]):.4f},{clamp(rh[1]):.4f}"
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
