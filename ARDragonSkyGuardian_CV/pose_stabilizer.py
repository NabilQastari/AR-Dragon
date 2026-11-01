"""
pose_stabilizer.py
Adaptive One-Euro Filter untuk stabilisasi koordinat keypoint pose.
- Menghilangkan jitter/getaran saat tangan diam (Akurat & Stabil)
- Respons seketika tanpa lag saat tangan bergerak cepat (Zero Delay)
- Menolak glitch/lonjakan titik saat confidence rendah
"""

import math
import time
from typing import Tuple

class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.05, d_cutoff: float = 1.0):
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

        # Hitung laju perubahan (kecepatan pergerakan)
        dx = (x - self.x_prev) / dt
        edx = self._smoothing_factor(dt, self.d_cutoff)
        dx_hat = edx * dx + (1.0 - edx) * self.dx_prev

        # Cutoff dinamis: semakin cepat tangan bergerak, cutoff naik (lag = 0)
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        ex = self._smoothing_factor(dt, cutoff)
        x_hat = ex * x + (1.0 - ex) * self.x_prev

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat


class PoseStabilizer:
    def __init__(self, min_cutoff: float = 1.2, beta: float = 0.08):
        # 6 titik tubuh: LS, RS, LW, RW, LH, RH (masing-masing X dan Y)
        self.filters_x = {key: OneEuroFilter(min_cutoff, beta) for key in ["ls", "rs", "lw", "rw", "lh", "rh"]}
        self.filters_y = {key: OneEuroFilter(min_cutoff, beta) for key in ["ls", "rs", "lw", "rw", "lh", "rh"]}
        self.last_valid = {}

    def update_point(self, key: str, raw_x: float, raw_y: float, conf: float = 1.0) -> Tuple[float, float]:
        t = time.perf_counter()

        # Outlier rejection: jika confidence drop drastis di bawah 0.35 dan melompat jauh
        if conf < 0.35 and key in self.last_valid:
            prev_x, prev_y = self.last_valid[key]
            dist = math.hypot(raw_x - prev_x, raw_y - prev_y)
            if dist > 0.25:  # Lonjakan tidak wajar
                return prev_x, prev_y

        clean_x = self.filters_x[key].filter(raw_x, t)
        clean_y = self.filters_y[key].filter(raw_y, t)

        clean_x = max(0.0, min(1.0, clean_x))
        clean_y = max(0.0, min(1.0, clean_y))

        self.last_valid[key] = (clean_x, clean_y)
        return clean_x, clean_y
