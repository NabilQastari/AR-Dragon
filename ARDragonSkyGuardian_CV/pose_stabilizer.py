"""
pose_stabilizer.py
High-Speed Pose Stabilizer & Velocity Predictor.
Dirancang khusus untuk mendeteksi gerakan tangan berkecepatan tinggi (kepakan sayap, ayunan cepat):
- Adaptive One-Euro Filter dengan responsifitas tinggi (beta tinggi untuk tangan)
- Velocity Extrapolation: jika tangan mengalami motion blur selama 1-3 frame, lintasan diproyeksikan secara inersia
- Elbow Kinematic Guard: memvalidasi posisi tangan berdasarkan titik siku agar tidak melompat keluar anatomi
"""

import math
import time
from typing import Tuple, Optional

class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.5, d_cutoff: float = 1.0):
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

        # Saat gerakan tangan cepat (|dx_hat| besar), cutoff naik drastis -> ZERO LAG
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        ex = self._smoothing_factor(dt, cutoff)
        x_hat = ex * x + (1.0 - ex) * self.x_prev

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat


class PoseStabilizer:
    def __init__(self):
        # Bahu & Pinggul: gerak lebih lambat, butuh stabilitas tinggi (beta=0.1)
        # Tangan (Wrist): gerak sangat cepat (kepak sayap), butuh respons instan (beta=0.8)
        self.filters_x = {
            "ls": OneEuroFilter(min_cutoff=1.2, beta=0.15),
            "rs": OneEuroFilter(min_cutoff=1.2, beta=0.15),
            "lh": OneEuroFilter(min_cutoff=1.0, beta=0.10),
            "rh": OneEuroFilter(min_cutoff=1.0, beta=0.10),
            "lw": OneEuroFilter(min_cutoff=1.5, beta=0.85),
            "rw": OneEuroFilter(min_cutoff=1.5, beta=0.85),
        }
        self.filters_y = {
            "ls": OneEuroFilter(min_cutoff=1.2, beta=0.15),
            "rs": OneEuroFilter(min_cutoff=1.2, beta=0.15),
            "lh": OneEuroFilter(min_cutoff=1.0, beta=0.10),
            "rh": OneEuroFilter(min_cutoff=1.0, beta=0.10),
            "lw": OneEuroFilter(min_cutoff=1.5, beta=0.85),
            "rw": OneEuroFilter(min_cutoff=1.5, beta=0.85),
        }

        # Velocity tracking untuk prediksi inersia saat tangan motion blur
        self.velocities = {k: (0.0, 0.0) for k in ["lw", "rw"]}
        self.last_pos = {}
        self.last_time = {}
        self.lost_frames = {"lw": 0, "rw": 0}

    def update_point(
        self,
        key: str,
        raw_x: float,
        raw_y: float,
        conf: float = 1.0,
        elbow_ref: Optional[Tuple[float, float]] = None
    ) -> Tuple[float, float]:
        t = time.perf_counter()

        # Jika tangan hilang/blur (conf < 0.20), gunakan ekstrapolasi inersia kecepatan (maksimal 4 frame)
        if conf < 0.20 and key in ["lw", "rw"] and key in self.last_pos:
            self.lost_frames[key] += 1
            if self.lost_frames[key] <= 4:
                # Proyeksikan berdasarkan kecepatan ayunan terakhir
                vx, vy = self.velocities[key]
                pred_x = self.last_pos[key][0] + vx * 0.7  # Damping sedikit
                pred_y = self.last_pos[key][1] + vy * 0.7

                # Batasi agar tidak meleset jauh dari siku jika ada
                if elbow_ref is not None:
                    max_reach = 0.38
                    dist = math.hypot(pred_x - elbow_ref[0], pred_y - elbow_ref[1])
                    if dist > max_reach:
                        pred_x = elbow_ref[0] + (pred_x - elbow_ref[0]) / dist * max_reach
                        pred_y = elbow_ref[1] + (pred_y - elbow_ref[1]) / dist * max_reach

                clean_x = self.filters_x[key].filter(pred_x, t)
                clean_y = self.filters_y[key].filter(pred_y, t)
                clean_x = max(0.0, min(1.0, clean_x))
                clean_y = max(0.0, min(1.0, clean_y))
                self.last_pos[key] = (clean_x, clean_y)
                return clean_x, clean_y

        # Titik valid terdeteksi
        self.lost_frames[key] = 0

        # Hitung vektor kecepatan instan untuk tangan
        if key in ["lw", "rw"] and key in self.last_pos:
            dt = t - self.last_time.get(key, t - 0.033)
            if dt > 0.001:
                vx = (raw_x - self.last_pos[key][0])
                vy = (raw_y - self.last_pos[key][1])
                # Smooth kecepatan
                old_vx, old_vy = self.velocities[key]
                self.velocities[key] = (0.6 * vx + 0.4 * old_vx, 0.6 * vy + 0.4 * old_vy)

        clean_x = self.filters_x[key].filter(raw_x, t)
        clean_y = self.filters_y[key].filter(raw_y, t)

        clean_x = max(0.0, min(1.0, clean_x))
        clean_y = max(0.0, min(1.0, clean_y))

        self.last_pos[key] = (clean_x, clean_y)
        self.last_time[key] = t
        return clean_x, clean_y
