"""
player_calibrator.py
Modul Kalibrasi Pemain & Engine Threshold Adaptif (Phase 4).
Menyediakan:
1. PlayerBiometricProfile: Struktur penyimpanan proporsi biometrik personal pemain.
2. AdaptiveThresholdEngine: Perhitungan threshold dinamis adaptif terhadap ukuran tubuh, rentang gerak, dan asimetri alami pemain.
3. PlayerCalibrator: State machine pemandu kalibrasi interaktif 4-tahap (Netral -> T-Pose -> Condong Kiri -> Condong Kanan).
4. Persistensi JSON profil pemain untuk sesi permainan berulang.
"""

import os
import json
import math
import time
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple, Any, List

class CalibrationState(Enum):
    IDLE = 0            # Normal play (uncalibrated or using loaded profile)
    STEP1_NEUTRAL = 1   # Berdiri santai / Netral (mengukur postur rileks & asimetri)
    STEP2_TPOSE = 2     # T-Pose / Rentang Sayap (mengukur wingspan & panjang lengan)
    STEP3_LEAN_LEFT = 3 # Condong Kiri Maksimal Nyaman
    STEP4_LEAN_RIGHT = 4# Condong Kanan Maksimal Nyaman
    COMPLETE = 5        # Kalibrasi selesai & profil adaptif aktif

@dataclass
class PlayerBiometricProfile:
    """Menyimpan data proporsi tubuh pemain hasil kalibrasi personal."""
    is_calibrated: bool = False
    profile_name: str = "Default"
    
    # Biometrik Dasar Tubuh
    shoulder_width: float = 0.20        # Jarak bahu normal (fraksi layar)
    torso_length: float = 0.35          # Panjang torso (bahu ke pinggul)
    arm_reach: float = 0.32             # Panjang jangkauan lengan (bahu ke pergelangan)
    
    # Wingspan Ratio
    resting_wingspan_ratio: float = 1.05 # Wingspan saat tangan rileks di samping tubuh
    max_wingspan_ratio: float = 2.10     # Wingspan saat T-Pose penuh
    
    # Asimetri & Rentang Condong (Leaning)
    neutral_lean_bias_deg: float = 0.0   # Sudut kemiringan alami saat berdiri santai (bias asimetri tubuh)
    max_lean_left_deg: float = 18.0      # Sudut condong kiri maksimal yang nyaman bagi pemain
    max_lean_right_deg: float = 18.0     # Sudut condong kanan maksimal yang nyaman bagi pemain
    
    # Flap Stroke Range (Relatif terhadap bahu)
    flap_upper_reach: float = 0.40       # Jangkauan tangan ke atas saat kepakan tertinggi
    flap_lower_reach: float = -0.35      # Jangkauan tangan ke bawah saat kepakan terendah
    
    # Tuck Dive Compactness
    tuck_wrist_dist_ratio: float = 1.40  # Rasio jarak pergelangan tangan terhadap bahu saat tuck dive

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerBiometricProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def get_default_profile() -> PlayerBiometricProfile:
    """Mengembalikan profil standar yang aman dan seimbang untuk semua pemain."""
    return PlayerBiometricProfile(
        is_calibrated=True,
        profile_name="Standard Adult",
        shoulder_width=0.20,
        torso_length=0.35,
        arm_reach=0.32,
        resting_wingspan_ratio=1.05,
        max_wingspan_ratio=2.10,
        neutral_lean_bias_deg=0.0,
        max_lean_left_deg=18.0,
        max_lean_right_deg=18.0,
        flap_upper_reach=0.40,
        flap_lower_reach=-0.35,
        tuck_wrist_dist_ratio=1.40
    )


class AdaptiveThresholdEngine:
    """
    Engine kalkulasi threshold adaptif (Section 4.2 - 4.4).
    Mengonversi biometrik personal pemain menjadi parameter gestur yang nyaman dan setara.
    """
    def __init__(self, profile: Optional[PlayerBiometricProfile] = None):
        self.profile = profile if profile is not None else get_default_profile()
        self._recalculate_adaptive_parameters()

    def set_profile(self, profile: PlayerBiometricProfile):
        self.profile = profile
        self._recalculate_adaptive_parameters()

    def _recalculate_adaptive_parameters(self):
        p = self.profile

        # 1. Adaptasi Kepakan Sayap (Flap to Climb)
        # Jarak vertikal kepakan minimum berbanding lurus dengan panjang lengan pemain
        # Anak-anak / lengan pendek memerlukan jarak kepakan lebih kecil untuk 100% power
        self.min_flap_amplitude = max(0.12, p.arm_reach * 0.45)
        self.full_flap_amplitude = max(0.24, p.arm_reach * 1.10)
        self.flap_velocity_scale = max(0.8, p.arm_reach * 3.5)

        # 2. Adaptasi Kemudi Belok (Continuous Leaning & Deadzone)
        # Zona mati dinamis untuk mengakomodasi asimetri dan goyangan santai tubuh
        avg_max_lean = (p.max_lean_left_deg + p.max_lean_right_deg) * 0.5
        self.lean_deadzone_deg = max(2.5, avg_max_lean * 0.16)
        
        # Rentang efektif condong kiri & kanan yang nyaman
        self.effective_lean_left = max(5.0, p.max_lean_left_deg - self.lean_deadzone_deg)
        self.effective_lean_right = max(5.0, p.max_lean_right_deg - self.lean_deadzone_deg)
        self.neutral_bias = p.neutral_lean_bias_deg

        # 3. Adaptasi Menukik (Tuck to Dive)
        # Ambang batas kerapatan tangan disesuaikan dengan proporsi bahu & torso
        self.tuck_wrist_dist_limit = p.shoulder_width * p.tuck_wrist_dist_ratio

        # 4. Kenyamanan & Reduksi Kelelahan (Fatigue Reduction)
        # Ambang batas glide netral (istirahat santai tanpa beban)
        self.glide_min_wingspan = p.resting_wingspan_ratio * 0.90
        self.glide_max_wingspan = p.max_wingspan_ratio * 1.25

    def compute_adaptive_steering(self, raw_lean_angle_deg: float, arm_tilt_norm: float = 0.0) -> Tuple[float, str]:
        """
        Menghitung kemudi kontinu yang dikoreksi terhadap asimetri alami dan zona mati personal.
        Returns: (steering_input in [-1.0, +1.0], label)
        """
        # Kompensasi asimetri alami tubuh
        corrected_angle = raw_lean_angle_deg - self.neutral_bias

        # Kombinasi condong badan dengan tilt tangan jika ada
        lean_signal = corrected_angle

        # Cek Zona Mati Personal
        if abs(lean_signal) < self.lean_deadzone_deg:
            return 0.0, "NEUTRAL"

        if lean_signal > 0:
            # Condong Kanan
            effective = lean_signal - self.lean_deadzone_deg
            ratio = min(1.0, effective / self.effective_lean_right)
            # Quadratic ease-in untuk kenyamanan kontrol mikro
            steer = math.pow(ratio, 1.35)
            return float(steer), "LEAN_RIGHT"
        else:
            # Condong Kiri
            effective = abs(lean_signal) - self.lean_deadzone_deg
            ratio = min(1.0, effective / self.effective_lean_left)
            steer = -math.pow(ratio, 1.35)
            return float(steer), "LEAN_LEFT"

    def compute_adaptive_flap_power(self, stroke_amplitude: float, stroke_velocity: float) -> float:
        """
        Menghitung daya dorong kepakan yang disesuaikan dengan jangkauan fisik pemain.
        Returns: flap_power in [0.0, 1.0]
        """
        if stroke_amplitude < self.min_flap_amplitude:
            return 0.0

        # Normalisasi amplitudo terhadap jangkauan personal pemain
        amp_norm = min(1.0, (stroke_amplitude - self.min_flap_amplitude) / max(0.01, self.full_flap_amplitude - self.min_flap_amplitude))

        # Normalisasi kecepatan kayuhan
        vel_norm = min(1.0, stroke_velocity / self.flap_velocity_scale)

        # Gabungan amplitudo (60%) dan kecepatan (40%) untuk kenyamanan tanpa perlu tenaga ekstrem
        power = (amp_norm * 0.60) + (vel_norm * 0.40)
        return float(min(1.0, max(0.0, power)))

    def is_adaptive_tuck_dive(self, wrist_dist: float, elbows_below_wrists: bool, elbows_below_shoulders: bool) -> bool:
        """Verifikasi Tuck Dive dengan ambang batas kerapatan proporsional."""
        is_compact = wrist_dist < self.tuck_wrist_dist_limit
        return is_compact and elbows_below_wrists and elbows_below_shoulders


class PlayerCalibrator:
    """
    Sistem Kalibrasi Interaktif & Adaptif Pemain (Section 4.1).
    Memandu pemain melalui 4 langkah kalibrasi yang cepat, natural, dan ramah pengguna:
    1. Netral (1.5 detik): Mengukur postur santai & asimetri tubuh alami.
    2. T-Pose (1.5 detik): Mengukur wingspan maksimal & jangkauan lengan.
    3. Condong Kiri (1.5 detik): Mengukur batas condong kiri yang nyaman.
    4. Condong Kanan (1.5 detik): Mengukur batas condong kanan yang nyaman.
    """
    STEP_DURATION = 1.5  # Durasi per langkah dalam detik

    def __init__(self, profile_save_path: Optional[str] = None):
        self.profile_save_path = profile_save_path or os.path.join(
            os.path.dirname(__file__), "player_profile.json"
        )
        self.state = CalibrationState.IDLE
        self.step_start_time = 0.0
        self.progress = 0.0
        
        # Koleksi sampel data per tahap
        self.samples_neutral: List[Dict[str, float]] = []
        self.samples_tpose: List[Dict[str, float]] = []
        self.samples_lean_left: List[float] = []
        self.samples_lean_right: List[float] = []

        # Profil aktif & engine
        self.current_profile = self.load_profile() or get_default_profile()
        self.engine = AdaptiveThresholdEngine(self.current_profile)

    def start_calibration(self):
        """Memulai prosedur kalibrasi interaktif dari Langkah 1."""
        self.state = CalibrationState.STEP1_NEUTRAL
        self.step_start_time = time.time()
        self.progress = 0.0
        self.samples_neutral.clear()
        self.samples_tpose.clear()
        self.samples_lean_left.clear()
        self.samples_lean_right.clear()
        print("[PlayerCalibrator] Prosedur kalibrasi pemain dimulai. Tahap 1: Berdiri Santai (Netral).")

    def cancel_calibration(self):
        """Membatalkan kalibrasi dan kembali ke profil sebelumnya."""
        self.state = CalibrationState.IDLE
        self.progress = 0.0
        print("[PlayerCalibrator] Kalibrasi dibatalkan.")

    def update(self, biometrics: Optional[Dict[str, Any]], kpts: Optional[Dict[str, Tuple[float, float]]]) -> Tuple[CalibrationState, float, str]:
        """
        Memperbarui status kalibrasi setiap frame.
        Returns: (current_state, progress_0_to_1, instruction_text)
        """
        if self.state == CalibrationState.IDLE or self.state == CalibrationState.COMPLETE:
            status_text = "Profil Terkalibrasi Aktif" if self.current_profile.is_calibrated else "Standby (Profil Standar)"
            return self.state, 1.0 if self.current_profile.is_calibrated else 0.0, status_text

        if biometrics is None or kpts is None:
            return self.state, self.progress, "Menunggu deteksi tubuh pemain..."

        now = time.time()
        elapsed = now - self.step_start_time
        self.progress = min(1.0, elapsed / self.STEP_DURATION)

        sw = biometrics.get("shoulder_width", 0.20)
        tl = biometrics.get("torso_length", 0.35)
        ws = biometrics.get("wingspan_ratio", 1.20)
        lean = biometrics.get("lean_angle_deg", 0.0)
        
        # Panjang lengan dari bahu ke pergelangan
        ls = kpts.get("ls", (0.4, 0.4))
        lw = kpts.get("lw", (0.2, 0.4))
        arm_len = math.hypot(lw[0] - ls[0], lw[1] - ls[1])

        # State 1: Berdiri Santai / Netral
        if self.state == CalibrationState.STEP1_NEUTRAL:
            self.samples_neutral.append({
                "sw": sw, "tl": tl, "ws": ws, "lean": lean, "arm": arm_len
            })
            instruction = f"TAHAP 1/4: BERDIRI SANTAI (NETRAL) [{int(self.progress * 100)}%]"

            if elapsed >= self.STEP_DURATION:
                self.state = CalibrationState.STEP2_TPOSE
                self.step_start_time = now
                self.progress = 0.0
                print("[PlayerCalibrator] Tahap 1 selesai -> Tahap 2: Rentangkan Sayap (T-Pose).")

        # State 2: T-Pose / Rentang Sayap Maksimal
        elif self.state == CalibrationState.STEP2_TPOSE:
            self.samples_tpose.append({
                "sw": sw, "tl": tl, "ws": ws, "arm": arm_len
            })
            instruction = f"TAHAP 2/4: RENTANGKAN SAYAP (T-POSE) [{int(self.progress * 100)}%]"

            if elapsed >= self.STEP_DURATION:
                self.state = CalibrationState.STEP3_LEAN_LEFT
                self.step_start_time = now
                self.progress = 0.0
                print("[PlayerCalibrator] Tahap 2 selesai -> Tahap 3: Condongkan Badan ke Kiri.")

        # State 3: Condong Kiri Maksimal Nyaman
        elif self.state == CalibrationState.STEP3_LEAN_LEFT:
            if lean < 0:  # Kiri bernilai negatif
                self.samples_lean_left.append(abs(lean))
            instruction = f"TAHAP 3/4: CONDONGKAN BADAN KE KIRI [{int(self.progress * 100)}%]"

            if elapsed >= self.STEP_DURATION:
                self.state = CalibrationState.STEP4_LEAN_RIGHT
                self.step_start_time = now
                self.progress = 0.0
                print("[PlayerCalibrator] Tahap 3 selesai -> Tahap 4: Condongkan Badan ke Kanan.")

        # State 4: Condong Kanan Maksimal Nyaman
        elif self.state == CalibrationState.STEP4_LEAN_RIGHT:
            if lean > 0:  # Kanan bernilai positif
                self.samples_lean_right.append(lean)
            instruction = f"TAHAP 4/4: CONDONGKAN BADAN KE KANAN [{int(self.progress * 100)}%]"

            if elapsed >= self.STEP_DURATION:
                self._finalize_calibration()
                self.state = CalibrationState.COMPLETE
                self.progress = 1.0
                instruction = "KALIBRASI SUKSES! PROFIL ADAPTIF AKTIF"
                print("[PlayerCalibrator] Kalibrasi selesai! Profil adaptif berhasil dikompilasi.")

        return self.state, self.progress, instruction

    def _finalize_calibration(self):
        """Menghitung nilai rata-rata sampel dan menyusun profil biometrik baru."""
        # 1. Rata-rata Netral
        avg_sw = sum(s["sw"] for s in self.samples_neutral) / max(1, len(self.samples_neutral))
        avg_tl = sum(s["tl"] for s in self.samples_neutral) / max(1, len(self.samples_neutral))
        avg_arm = sum(s["arm"] for s in self.samples_neutral) / max(1, len(self.samples_neutral))
        avg_rest_ws = sum(s["ws"] for s in self.samples_neutral) / max(1, len(self.samples_neutral))
        avg_bias = sum(s["lean"] for s in self.samples_neutral) / max(1, len(self.samples_neutral))

        # 2. Rata-rata T-Pose
        if self.samples_tpose:
            max_ws = max(s["ws"] for s in self.samples_tpose)
            max_arm = max(s["arm"] for s in self.samples_tpose)
        else:
            max_ws = avg_rest_ws * 1.8
            max_arm = avg_arm * 1.2

        # 3. Rata-rata Condong Kiri & Kanan
        max_left = max(self.samples_lean_left) if self.samples_lean_left else 16.0
        max_right = max(self.samples_lean_right) if self.samples_lean_right else 16.0

        # Batasi ke batas aman dan nyaman (minimal 10 deg, maksimal 32 deg)
        max_left = float(min(32.0, max(10.0, max_left)))
        max_right = float(min(32.0, max(10.0, max_right)))

        # Susun Profil Baru
        self.current_profile = PlayerBiometricProfile(
            is_calibrated=True,
            profile_name="Personalized Player",
            shoulder_width=float(avg_sw),
            torso_length=float(avg_tl),
            arm_reach=float(max_arm),
            resting_wingspan_ratio=float(avg_rest_ws),
            max_wingspan_ratio=float(max_ws),
            neutral_lean_bias_deg=float(avg_bias),
            max_lean_left_deg=max_left,
            max_lean_right_deg=max_right,
            flap_upper_reach=float(max_arm * 1.15),
            flap_lower_reach=float(-max_arm * 0.95),
            tuck_wrist_dist_ratio=1.45
        )

        # Perbarui engine adaptif
        self.engine.set_profile(self.current_profile)
        self.save_profile()

    def save_profile(self):
        """Menyimpan profil pemain ke file JSON lokal."""
        try:
            with open(self.profile_save_path, "w") as f:
                json.dump(self.current_profile.to_dict(), f, indent=2)
            print(f"[PlayerCalibrator] Profil pemain tersimpan di {self.profile_save_path}")
        except Exception as e:
            print(f"[PlayerCalibrator] Gagal menyimpan profil: {e}")

    def load_profile(self) -> Optional[PlayerBiometricProfile]:
        """Memuat profil pemain dari file JSON jika tersedia."""
        if os.path.exists(self.profile_save_path):
            try:
                with open(self.profile_save_path, "r") as f:
                    data = json.load(f)
                prof = PlayerBiometricProfile.from_dict(data)
                print(f"[PlayerCalibrator] Profil pemain berhasil dimuat dari {self.profile_save_path}")
                return prof
            except Exception as e:
                print(f"[PlayerCalibrator] Gagal memuat profil: {e}")
        return None
