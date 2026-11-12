"""
udp_sender.py
Modul pengirim data UDP untuk posisi keypoint pose + Status Mulut Terbuka + Biometrik Ternormalisasi
+ Gesture State Machine (Phase 2), serta pengirim frame video JPEG terkompresi untuk Unity PIP Preview.

Format CSV (Backward-Compatible):
- 13 Float Dasar (0..12): LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y,MOUTH_OPEN
- Tambahan Dinamis (13..20): LE_X,LE_Y,RE_X,RE_Y,IS_DIVE,IS_FLAP,FLAP_FREQ,FLAP_POWER
- Tambahan Pose (21..23): BODY_PITCH, NOSE_X, NOSE_Y
- Tambahan Biometrik Phase 1 (24..27): WINGSPAN_RATIO, FLAP_HEIGHT, LEAN_ANGLE_DEG, TRACKING_STATE
- Tambahan Gestur Phase 2 (28..31): IS_DASH, DASH_POWER, STEERING_INPUT, ACTIVE_STATE_ID
"""

import socket
import cv2
import numpy as np
from typing import Tuple, Optional

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
        le: Optional[Tuple[float, float]] = None,
        re: Optional[Tuple[float, float]] = None,
        is_dive: float = 0.0,
        is_flap: float = 0.0,
        flap_freq: float = 0.0,
        flap_power: float = 0.0,
        body_pitch: float = 0.0,
        nose: Optional[Tuple[float, float]] = None,
        wingspan_ratio: float = 0.0,
        flap_height: float = 0.0,
        lean_angle_deg: float = 0.0,
        tracking_state: float = 1.0,  # 1.0 = TRACKED, 0.5 = DEGRADED, 0.0 = LOST
        is_dash: float = 0.0,
        dash_power: float = 0.0,
        steering_input: float = 0.0,
        active_state_id: float = 0.0,  # 0=Glide, 1=Flap, 2=Dive, 3=Dash
        calib_state_id: float = 0.0,   # 0=Idle, 1=Neutral, 2=TPose, 3=LeanL, 4=LeanR, 5=Complete
        calib_progress: float = 0.0,   # 0.0 to 1.0
        is_hover: float = 0.0,
        is_gentle_descent: float = 0.0,
        is_fly_up: float = 0.0,
        chest_elevation: float = 1.55,
        forearm_flap_power: float = 0.0
    ) -> bool:
        """
        Mengirim telemetry string CSV secara efisien dan konsisten (Phase 4: 34 Float, Extended: 39 Float).
        """
        try:
            def clamp(val: float) -> float:
                return max(0.0, min(1.0, float(val)))

            parts = [
                f"{clamp(ls[0]):.4f}", f"{clamp(ls[1]):.4f}",
                f"{clamp(rs[0]):.4f}", f"{clamp(rs[1]):.4f}",
                f"{clamp(lw[0]):.4f}", f"{clamp(lw[1]):.4f}",
                f"{clamp(rw[0]):.4f}", f"{clamp(rw[1]):.4f}",
                f"{clamp(lh[0]):.4f}", f"{clamp(lh[1]):.4f}",
                f"{clamp(rh[0]):.4f}", f"{clamp(rh[1]):.4f}",
                f"{clamp(mouth_open):.4f}"
            ]

            if le is not None and re is not None:
                parts.extend([
                    f"{clamp(le[0]):.4f}", f"{clamp(le[1]):.4f}",
                    f"{clamp(re[0]):.4f}", f"{clamp(re[1]):.4f}",
                    f"{1.0 if is_dive > 0.5 else 0.0:.1f}",
                    f"{1.0 if is_flap > 0.5 else 0.0:.1f}",
                    f"{float(flap_freq):.2f}",
                    f"{clamp(flap_power):.2f}",
                    f"{max(-1.0, min(1.0, float(body_pitch))):.2f}"
                ])

                if nose is not None:
                    parts.extend([
                        f"{clamp(nose[0]):.4f}",
                        f"{clamp(nose[1]):.4f}"
                    ])

                    # Phase 1 Biometric Telemetry (24..27)
                    parts.extend([
                        f"{float(wingspan_ratio):.2f}",
                        f"{float(flap_height):.2f}",
                        f"{float(lean_angle_deg):.2f}",
                        f"{float(tracking_state):.1f}"
                    ])

                    # Phase 2 Gesture Telemetry (28..31)
                    parts.extend([
                        f"{1.0 if is_dash > 0.5 else 0.0:.1f}",
                        f"{clamp(dash_power):.2f}",
                        f"{max(-1.0, min(1.0, float(steering_input))):.2f}",
                        f"{float(active_state_id):.0f}"
                    ])

                    # Phase 4 Calibration Telemetry (32..33)
                    parts.extend([
                        f"{float(calib_state_id):.0f}",
                        f"{clamp(calib_progress):.2f}"
                    ])

                    # Additional Flight Gestures Telemetry (34..38)
                    parts.extend([
                        f"{1.0 if is_hover > 0.5 else 0.0:.1f}",
                        f"{1.0 if is_gentle_descent > 0.5 else 0.0:.1f}",
                        f"{1.0 if is_fly_up > 0.5 else 0.0:.1f}",
                        f"{float(chest_elevation):.2f}",
                        f"{clamp(forearm_flap_power):.2f}"
                    ])

            csv_string = ",".join(parts)
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
            small_frame = cv2.resize(frame, self.target_size, interpolation=cv2.INTER_AREA)
            success, encoded_img = cv2.imencode('.jpg', small_frame, self.encode_param)
            if not success:
                return False

            data = encoded_img.tobytes()
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
