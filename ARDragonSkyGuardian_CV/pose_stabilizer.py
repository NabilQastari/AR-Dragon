"""
pose_stabilizer.py
Robust Kinematic Pose Stabilizer untuk gerakan dinamis (Kepak Sayap, Angkat Tangan, Sembur Air).
- Menghilangkan glitch lompatan titik tangan tanpa inersia palsu
- Batasan Kinematika Lengan (Arm Length Clamping): mencegah titik terlempar keluar tubuh
- One-Euro Filter presisi tinggi: mulus saat diam, instan saat bergerak
"""

import math
import time
from typing import Tuple, Optional

class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.2, beta: float = 0.35, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    def _smoothing_factor(self, dt: float, cutoff: float) -> float:
        r = 2.0 * math.pi * cutoff * dt
        return r / (r + 1.0)

    def filter(self, x: float, t: float = None) -> float:
        if t is None:
            t = time.perf_counter()

        if self.x_prev is None:
            self.x_prev = x
            self.t_prev = t
            return x

        dt = t - self.t_prev
        if dt <= 1e-5:
            return self.x_prev

        dx = (x - self.x_prev) / dt
        edx = self._smoothing_factor(dt, self.d_cutoff)
        dx_hat = edx * dx + (1.0 - edx) * self.dx_prev

        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        ex = self._smoothing_factor(dt, cutoff)
        x_hat = ex * x + (1.0 - ex) * self.x_prev

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat


class PoseStabilizer:
    def __init__(self):
        self.filters_x = {k: OneEuroFilter(min_cutoff=1.2, beta=0.35) for k in ["ls", "rs", "lh", "rh", "lw", "rw", "le", "re"]}
        self.filters_y = {k: OneEuroFilter(min_cutoff=1.2, beta=0.35) for k in ["ls", "rs", "lh", "rh", "lw", "rw", "le", "re"]}
        self.last_clean = {}

    def update_point(
        self,
        key: str,
        raw_x: float,
        raw_y: float,
        conf: float = 1.0,
        shoulder_ref: Optional[Tuple[float, float]] = None,
        shoulder_width: Optional[float] = None,
        elbow_ref: Optional[Tuple[float, float]] = None
    ) -> Tuple[float, float]:
        t = time.perf_counter()

        # Validasi batas layar
        raw_x = max(0.01, min(0.99, raw_x))
        raw_y = max(0.01, min(0.99, raw_y))

        # 1. Batasan Kinematika Lengan Dinamis (Anatomical Clamping)
        if shoulder_ref is not None and key in ["lw", "rw"]:
            sx, sy = shoulder_ref
            arm_dist = math.hypot(raw_x - sx, raw_y - sy)

            # Hitung panjang lengan proporsional terhadap jarak bahu (1.4x lebar bahu)
            if shoulder_width is not None and shoulder_width > 0.05:
                max_arm_length = max(0.20, min(0.65, shoulder_width * 1.45))
            else:
                max_arm_length = 0.48

            if arm_dist > max_arm_length:
                # Clamp tangan agar tetap di ujung jangkauan lengan alami pengguna
                scale = max_arm_length / arm_dist
                raw_x = sx + (raw_x - sx) * scale
                raw_y = sy + (raw_y - sy) * scale

        # 2. Kinematika Siku ke Pergelangan Tangan (Forearm Clamping saat low confidence)
        if elbow_ref is not None and key in ["lw", "rw"] and conf < 0.25:
            ex, ey = elbow_ref
            forearm_dist = math.hypot(raw_x - ex, raw_y - ey)
            max_forearm = (shoulder_width * 0.8) if (shoulder_width is not None and shoulder_width > 0.05) else 0.28
            if forearm_dist > max_forearm:
                scale = max_forearm / forearm_dist
                raw_x = ex + (raw_x - ex) * scale
                raw_y = ey + (raw_y - ey) * scale

        # 3. Outlier Rejection: Jika titik melompat > 0.20 dalam 1 frame dengan confidence rendah (< 0.25)
        if conf < 0.25 and key in self.last_clean:
            prev_x, prev_y = self.last_clean[key]
            step = math.hypot(raw_x - prev_x, raw_y - prev_y)
            if step > 0.18:
                # Pertahankan posisi bersih sebelumnya agar tidak terjadi glitch visual
                return prev_x, prev_y

        clean_x = self.filters_x[key].filter(raw_x, t)
        clean_y = self.filters_y[key].filter(raw_y, t)

        clean_x = max(0.0, min(1.0, clean_x))
        clean_y = max(0.0, min(1.0, clean_y))

        self.last_clean[key] = (clean_x, clean_y)
        return clean_x, clean_y


class WingFlapDetector:
    """
    Detektor Kepakan Sayap Cerdas dengan State Machine Hysteresis:
    - Mencegah fluktuasi/flicker saat tangan sejajar bahu
    - Mendeteksi 1 siklus kepakan penuh (NAIK -> TURUN)
    - Mengukur kecepatan kepakan (Flap Frequency) & Flap Power
    """
    STATE_DOWN = 0
    STATE_GOING_UP = 1
    STATE_UP = 2
    STATE_GOING_DOWN = 3

    def __init__(self, hysteresis: float = 0.035):
        self.hysteresis = hysteresis
        self.state = self.STATE_DOWN
        self.flap_count = 0
        self.last_flap_time = 0.0
        self.flap_frequency = 0.0
        self.flap_history = []
        self.last_y = 0.5
        self.flap_power = 0.0

    def update(self, lw: Tuple[float, float], rw: Tuple[float, float],
               ls: Tuple[float, float], rs: Tuple[float, float]) -> Tuple[int, str, float, float]:
        now = time.perf_counter()
        avg_wrist_y = (lw[1] + rw[1]) * 0.5
        avg_shoulder_y = (ls[1] + rs[1]) * 0.5

        # Kecepatan vertikal tangan (power kepakan)
        dy = abs(avg_wrist_y - self.last_y)
        self.last_y = avg_wrist_y
        self.flap_power = min(1.0, dy * 12.0)

        # Ambang batas histeresis
        up_threshold = avg_shoulder_y - self.hysteresis
        down_threshold = avg_shoulder_y + self.hysteresis

        is_clearly_above = (lw[1] < up_threshold) and (rw[1] < up_threshold)
        is_clearly_below = (lw[1] > down_threshold) and (rw[1] > down_threshold)

        status_str = "SEJAJAR BAHU"

        if self.state == self.STATE_DOWN:
            status_str = "SAYAP DI BAWAH"
            if is_clearly_above:
                self.state = self.STATE_UP
        elif self.state == self.STATE_UP:
            status_str = "SAYAP DI ATAS"
            if is_clearly_below:
                # Siklus kepakan lengkap: NAIK lalu TURUN
                self.flap_count += 1
                self.state = self.STATE_DOWN
                if self.last_flap_time > 0:
                    dt = now - self.last_flap_time
                    if dt > 0.15:
                        freq = 1.0 / dt
                        self.flap_history.append(freq)
                        if len(self.flap_history) > 5:
                            self.flap_history.pop(0)
                        self.flap_frequency = sum(self.flap_history) / len(self.flap_history)
                self.last_flap_time = now

        # Timeout jika tidak mengepak dalam 2 detik
        if now - self.last_flap_time > 2.0:
            self.flap_frequency = max(0.0, self.flap_frequency * 0.9)

        return self.flap_count, status_str, self.flap_frequency, self.flap_power


def compute_smooth_tilt(lw: Tuple[float, float], rw: Tuple[float, float],
                        deadzone: float = 0.035, max_tilt: float = 0.28) -> Tuple[float, float]:
    """
    Menghitung kemiringan (tilt) dengan Deadzone dan kurva halus:
    - Di dalam deadzone: 0.0 (terbang lurus stabil tanpa drift)
    - Di luar deadzone: ternormalisasi -1.0 (belok kiri tajam) s/d +1.0 (belok kanan tajam)
    """
    # lw[1] - rw[1]: jika tangan kiri lebih rendah (lw[1] lebih besar), tilt positif (belok kanan)
    raw_diff = lw[1] - rw[1]

    if abs(raw_diff) <= deadzone:
        normalized_tilt = 0.0
    else:
        sign = 1.0 if raw_diff > 0 else -1.0
        effective = abs(raw_diff) - deadzone
        range_val = max(0.01, max_tilt - deadzone)
        normalized_tilt = sign * min(1.0, effective / range_val)

    return raw_diff, normalized_tilt
