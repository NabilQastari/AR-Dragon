"""
mouth_tracker.py
Fast & High-Precision Mouth Tracker untuk Semburan Air Naga.
- Menggabungkan Geometric Mouth Aspect Ratio (MAR: bibir atas vs bawah) + Google Face Blendshape (jawOpen)
- Instant Trigger: Tidak perlu menganga ekstrem, buka mulut wajar langsung menyala SEKETIKA (Zero Delay)
- Schmitt Trigger (Hysteresis): Menghilangkan kedipan (flicker) saat menyemburkan air
"""

import os
import math
import tempfile
from typing import Tuple, Optional

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class MouthTracker:
    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            model_path = os.path.join(os.path.dirname(__file__), "face_landmarker.task")

        self.available = False
        self.detector = None
        self.is_active = False  # Status semburan air saat ini (Hysteresis)

        # Ambang batas responsif instan
        self.ON_THRESHOLD = 0.22   # Buka mulut wajar langsung AKTIF
        self.OFF_THRESHOLD = 0.15  # Tetap aktif sampai mulut benar-benar tertutup

        if os.path.exists(model_path):
            base_opts = python.BaseOptions(model_asset_path=model_path)
            opts = vision.FaceLandmarkerOptions(
                base_options=base_opts,
                output_face_blendshapes=True,
                num_faces=1,
                running_mode=vision.RunningMode.IMAGE
            )
            self.detector = vision.FaceLandmarker.create_from_options(opts)
            self.available = True

    def process_frame(self, mp_image: mp.Image, frame_w: int, frame_h: int) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        """
        Mengembalikan:
        - is_water_breath: bool (Apakah semburan air aktif)
        - mouth_score: float (0.0000 - 1.0000)
        - mouth_pixel_center: (x, y) koordinat tengah mulut di layar
        """
        if not self.available or self.detector is None:
            return False, 0.0, None

        res = self.detector.detect(mp_image)

        jaw_open_blendshape = 0.0
        if res.face_blendshapes and len(res.face_blendshapes) > 0:
            for cat in res.face_blendshapes[0]:
                if cat.category_name == "jawOpen":
                    jaw_open_blendshape = float(cat.score)
                    break

        mar = 0.0
        mouth_center = None

        if res.face_landmarks and len(res.face_landmarks) > 0:
            lm = res.face_landmarks[0]
            # Landmark bibir:
            # 13: Bibir Atas Dalam (Upper Lip Inner)
            # 14: Bibir Bawah Dalam (Lower Lip Inner)
            # 61: Sudut Mulut Kiri
            # 291: Sudut Mulut Kanan
            top_lip = lm[13]
            bot_lip = lm[14]
            left_corner = lm[61]
            right_corner = lm[291]

            lip_height = abs(bot_lip.y - top_lip.y)
            mouth_width = math.hypot(right_corner.x - left_corner.x, right_corner.y - left_corner.y)

            if mouth_width > 0.01:
                mar = lip_height / mouth_width

            cx = int((top_lip.x + bot_lip.x) * 0.5 * frame_w)
            cy = int((top_lip.y + bot_lip.y) * 0.5 * frame_h)
            mouth_center = (cx, cy)

        # Gabungkan MAR geometris (instan) dengan neural blendshape
        # MAR biasanya berkisar 0.02 (tertutup) sampai 0.35+ (terbuka)
        combined_score = max(jaw_open_blendshape, mar * 2.2)
        combined_score = max(0.0, min(1.0, combined_score))

        # Hysteresis Schmitt Trigger: instan menyala dan stabil tanpa flicker
        if not self.is_active:
            if combined_score >= self.ON_THRESHOLD:
                self.is_active = True
        else:
            if combined_score < self.OFF_THRESHOLD:
                self.is_active = False

        return self.is_active, combined_score, mouth_center
