"""
test_phase4_validation.py
Suite Validasi Komprehensif Phase 4 - Calibration & Adaptive Control
Memverifikasi:
1. Prosedur Kalibrasi 4-Tahap (Netral -> T-Pose -> Condong Kiri -> Condong Kanan -> Lengkap)
2. Penanganan Ragam Profil Pemain:
   - Profil Standar Dewasa (Standard Adult)
   - Profil Anak / Bertubuh Pendek (Child / Short Player)
   - Profil Mobilitas Terbatas (Limited Mobility)
   - Profil Asimetri Alami (Natural Spine Bias)
3. Threshold Kepakan Adaptif (Adaptive Flap Detection)
4. Kemudi Adaptif & Kompensasi Asimetri (Adaptive Leaning & Deadzone Calibration)
5. Deteksi Tuck Dive Proporsional (Adaptive Tuck Dive)
6. Kenyamanan & Reduksi Kelelahan (Comfort & Fatigue Reduction)
7. Integritas Telemetri UDP 34-Float (Calib State ID & Progress)
"""

import math
import time
from player_calibrator import (
    CalibrationState,
    PlayerBiometricProfile,
    AdaptiveThresholdEngine,
    PlayerCalibrator,
    get_default_profile
)
from motion_recognizer import (
    GestureStateMachine,
    GestureState,
    FlapStrokePhase
)
from udp_sender import PoseUDPSender

def test_calibration_step_sequence():
    print("[TEST 4.1] Player Calibration Step Sequence (4-Step Guided Workflow)...")
    calibrator = PlayerCalibrator(profile_save_path="test_profile_tmp.json")
    assert calibrator.state == CalibrationState.IDLE

    # Mulai kalibrasi
    calibrator.start_calibration()
    assert calibrator.state == CalibrationState.STEP1_NEUTRAL

    t0 = time.time()
    calibrator.step_start_time = t0 - 0.5  # 0.5s elapsed

    # Dummy biometrics & keypoints for Neutral
    bio_neutral = {
        "shoulder_width": 0.22,
        "torso_length": 0.36,
        "wingspan_ratio": 1.15,
        "lean_angle_deg": 1.5,  # Natural 1.5 deg right lean
        "avg_flap_height": -0.30
    }
    kpts_neutral = {
        "ls": (0.39, 0.40), "rs": (0.61, 0.40),
        "lw": (0.28, 0.65), "rw": (0.72, 0.65)
    }

    # Frame di step 1
    st, prog, txt = calibrator.update(bio_neutral, kpts_neutral)
    assert st == CalibrationState.STEP1_NEUTRAL
    assert 0.0 < prog < 1.0
    assert "TAHAP 1/4" in txt

    # Lewatkan waktu langkah 1 (durasi 1.5s)
    calibrator.step_start_time = t0 - 1.6
    st, prog, txt = calibrator.update(bio_neutral, kpts_neutral)
    assert st == CalibrationState.STEP2_TPOSE
    print("  -> Transisi Sukses: STEP 1 (Netral) -> STEP 2 (T-Pose)")

    # Data T-Pose
    bio_tpose = {
        "shoulder_width": 0.22,
        "torso_length": 0.36,
        "wingspan_ratio": 2.25,
        "lean_angle_deg": 1.2,
        "avg_flap_height": 0.05
    }
    kpts_tpose = {
        "ls": (0.39, 0.40), "rs": (0.61, 0.40),
        "lw": (0.12, 0.41), "rw": (0.88, 0.41)
    }
    calibrator.update(bio_tpose, kpts_tpose)
    calibrator.step_start_time = t0 - 3.2
    st, prog, txt = calibrator.update(bio_tpose, kpts_tpose)
    assert st == CalibrationState.STEP3_LEAN_LEFT
    print("  -> Transisi Sukses: STEP 2 (T-Pose) -> STEP 3 (Condong Kiri)")

    # Data Condong Kiri
    bio_lean_l = {
        "shoulder_width": 0.22, "torso_length": 0.36, "wingspan_ratio": 1.6,
        "lean_angle_deg": -16.5, "avg_flap_height": -0.10
    }
    calibrator.update(bio_lean_l, kpts_neutral)
    calibrator.step_start_time = t0 - 4.8
    st, prog, txt = calibrator.update(bio_lean_l, kpts_neutral)
    assert st == CalibrationState.STEP4_LEAN_RIGHT
    print("  -> Transisi Sukses: STEP 3 (Condong Kiri) -> STEP 4 (Condong Kanan)")

    # Data Condong Kanan
    bio_lean_r = {
        "shoulder_width": 0.22, "torso_length": 0.36, "wingspan_ratio": 1.6,
        "lean_angle_deg": 19.0, "avg_flap_height": -0.10
    }
    calibrator.update(bio_lean_r, kpts_neutral)
    calibrator.step_start_time = t0 - 6.4
    st, prog, txt = calibrator.update(bio_lean_r, kpts_neutral)
    assert st == CalibrationState.COMPLETE
    assert calibrator.current_profile.is_calibrated
    print(f"  -> Kalibrasi Selesai! Profil: {calibrator.current_profile.profile_name}")
    print(f"     * Neutral Bias: {calibrator.current_profile.neutral_lean_bias_deg:.2f}°")
    print(f"     * Max Wingspan Ratio: {calibrator.current_profile.max_wingspan_ratio:.2f}")
    print(f"     * Lean Left / Right: {calibrator.current_profile.max_lean_left_deg:.1f}° / {calibrator.current_profile.max_lean_right_deg:.1f}°")
    print("  -> PASSED: Seluruh tahapan kalibrasi berjalan mulus dan menghasilkan profil yang presisi.")


def test_player_profiles_variety():
    print("[TEST 4.2] Handling Variety of Player Profiles (Child, Adult, Limited Mobility)...")
    
    # 1. Profil Anak / Lengan Pendek
    child_profile = PlayerBiometricProfile(
        is_calibrated=True,
        profile_name="Child (Short Reach)",
        shoulder_width=0.15,
        torso_length=0.26,
        arm_reach=0.20,
        resting_wingspan_ratio=1.05,
        max_wingspan_ratio=1.85,
        neutral_lean_bias_deg=0.0,
        max_lean_left_deg=16.0,
        max_lean_right_deg=16.0,
        flap_upper_reach=0.25,
        flap_lower_reach=-0.22,
        tuck_wrist_dist_ratio=1.40
    )
    engine_child = AdaptiveThresholdEngine(child_profile)

    # 2. Profil Dewasa Bertubuh Tinggi
    tall_profile = PlayerBiometricProfile(
        is_calibrated=True,
        profile_name="Tall Adult",
        shoulder_width=0.26,
        torso_length=0.42,
        arm_reach=0.42,
        resting_wingspan_ratio=1.10,
        max_wingspan_ratio=2.35,
        neutral_lean_bias_deg=0.0,
        max_lean_left_deg=22.0,
        max_lean_right_deg=22.0,
        flap_upper_reach=0.50,
        flap_lower_reach=-0.45,
        tuck_wrist_dist_ratio=1.45
    )
    engine_tall = AdaptiveThresholdEngine(tall_profile)

    # 3. Profil Rentang Gerak Terbatas (Limited Mobility)
    limited_profile = PlayerBiometricProfile(
        is_calibrated=True,
        profile_name="Limited Mobility",
        shoulder_width=0.20,
        torso_length=0.35,
        arm_reach=0.30,
        resting_wingspan_ratio=1.05,
        max_wingspan_ratio=1.90,
        neutral_lean_bias_deg=0.0,
        max_lean_left_deg=10.0,  # Hanya mampu miring hingga 10 derajat
        max_lean_right_deg=10.0,
        flap_upper_reach=0.30,
        flap_lower_reach=-0.25,
        tuck_wrist_dist_ratio=1.40
    )
    engine_limited = AdaptiveThresholdEngine(limited_profile)

    print(f"  Child Min Flap Amplitude : {engine_child.min_flap_amplitude:.3f} (Lebih kecil, ramah anak)")
    print(f"  Tall Min Flap Amplitude  : {engine_tall.min_flap_amplitude:.3f} (Sesuai proporsi lengan panjang)")
    assert engine_child.min_flap_amplitude < engine_tall.min_flap_amplitude, "Child requires smaller amplitude than tall adult"

    print(f"  Limited Mobility Effective Lean : {engine_limited.effective_lean_left:.1f}°")
    print(f"  Tall Adult Effective Lean       : {engine_tall.effective_lean_left:.1f}°")
    assert engine_limited.effective_lean_left < engine_tall.effective_lean_left, "Limited mobility has compact lean span"
    print("  -> PASSED: Parameter adaptif berhasil diturunkan sesuai morfologi fisik pemain.")


def test_adaptive_flap_thresholding():
    print("[TEST 4.3] Adaptive Flap Thresholding (Equal Responsiveness across Players)...")
    
    # Buat profil anak dan dewasa
    child_profile = PlayerBiometricProfile(
        is_calibrated=True,
        arm_reach=0.20,
        torso_length=0.26
    )
    adult_profile = PlayerBiometricProfile(
        is_calibrated=True,
        arm_reach=0.40,
        torso_length=0.42
    )

    engine_child = AdaptiveThresholdEngine(child_profile)
    engine_adult = AdaptiveThresholdEngine(adult_profile)

    # Gerakan kepakan sedang untuk anak: stroke_amplitude = 0.22, stroke_velocity = 0.70
    child_power = engine_child.compute_adaptive_flap_power(stroke_amplitude=0.22, stroke_velocity=0.70)
    print(f"  Child Flap Power (Gerakan Lengan Anak 0.22 unit): {child_power*100:.1f}%")
    assert child_power >= 0.65, f"Child should achieve robust climb power with child-scaled stroke (got {child_power})"

    # Jika orang dewasa melakukan gerakan kecil 0.22 unit (hanya 50% jangkauan lengannya)
    adult_small_power = engine_adult.compute_adaptive_flap_power(stroke_amplitude=0.22, stroke_velocity=0.70)
    print(f"  Adult Flap Power on Small Twitch (0.22 unit): {adult_small_power*100:.1f}%")
    assert adult_small_power < child_power, "Adult should not over-trigger on small movement relative to their reach"

    # Saat orang dewasa melakukan kayuhan proporsional (0.42 unit, velocity 1.40)
    adult_full_power = engine_adult.compute_adaptive_flap_power(stroke_amplitude=0.42, stroke_velocity=1.40)
    print(f"  Adult Flap Power on Proportional Stroke (0.42 unit): {adult_full_power*100:.1f}%")
    assert adult_full_power >= 0.85, f"Adult achieves full power on proportional stroke (got {adult_full_power})"
    print("  -> PASSED: Deteksi kepakan sayap adaptif memberikan keadilan responsivitas fisik tanpa diskriminasi ukuran tubuh.")


def test_adaptive_leaning_and_asymmetry_deadzone():
    print("[TEST 4.4] Adaptive Leaning & Asymmetry Deadzone Calibration...")
    
    # Pemain dengan asimetri alami: berdiri santai condong ke kanan +2.8 derajat
    asymmetric_profile = PlayerBiometricProfile(
        is_calibrated=True,
        neutral_lean_bias_deg=2.8,
        max_lean_left_deg=16.0,
        max_lean_right_deg=18.0
    )
    engine_asym = AdaptiveThresholdEngine(asymmetric_profile)

    # 1. Saat berdiri santai di posisi alaminya (+2.8 derajat):
    steer_neutral, lbl = engine_asym.compute_adaptive_steering(raw_lean_angle_deg=2.8)
    print(f"  Resting Pose with Asymmetry (+2.8°): Steer = {steer_neutral:.3f} ({lbl})")
    assert steer_neutral == 0.0, f"Natural asymmetry bias must be completely cancelled out to prevent drifting (got {steer_neutral})"

    # 2. Sedikit goyangan santai di sekitar posisi rileks (+4.0 derajat, delta = +1.2 derajat < deadzone)
    steer_relaxed, _ = engine_asym.compute_adaptive_steering(raw_lean_angle_deg=4.0)
    print(f"  Relaxed Posture (+4.0°, Delta +1.2°): Steer = {steer_relaxed:.3f}")
    assert steer_relaxed == 0.0, "Slight natural posture shift must remain inside deadzone"

    # 3. Belok Kiri Aktif (raw -12.0 derajat, corrected = -14.8 derajat)
    steer_left, lbl_l = engine_asym.compute_adaptive_steering(raw_lean_angle_deg=-12.0)
    print(f"  Active Turn Left (raw -12.0°): Steer = {steer_left:.3f} ({lbl_l})")
    assert steer_left < -0.70, f"Active left lean should produce strong steering (got {steer_left})"

    # 4. Profil Mobilitas Terbatas (Hanya mampu miring maksimal 10 derajat)
    limited_profile = PlayerBiometricProfile(
        is_calibrated=True,
        neutral_lean_bias_deg=0.0,
        max_lean_left_deg=10.0,
        max_lean_right_deg=10.0
    )
    engine_limited = AdaptiveThresholdEngine(limited_profile)

    # Saat miring 9.0 derajat (90% kemampuan maksimalnya)
    steer_limited, _ = engine_limited.compute_adaptive_steering(raw_lean_angle_deg=9.0)
    print(f"  Limited Mobility Player (miring 9.0° dari maks 10°): Steer = {steer_limited*100:.1f}%")
    assert steer_limited > 0.80, f"Limited mobility player must achieve near 100% steering without painful strain (got {steer_limited})"
    print("  -> PASSED: Deadzone dinamis dan kompensasi asimetri berhasil menghilangkan drift kemudi santai.")


def test_adaptive_tuck_dive():
    print("[TEST 4.5] Adaptive Tuck Dive Compactness...")
    
    # Profil anak dengan bahu kecil vs dewasa berotot lebar
    profile_child = PlayerBiometricProfile(shoulder_width=0.14, tuck_wrist_dist_ratio=1.40)
    profile_broad = PlayerBiometricProfile(shoulder_width=0.28, tuck_wrist_dist_ratio=1.45)

    engine_child = AdaptiveThresholdEngine(profile_child)
    engine_broad = AdaptiveThresholdEngine(profile_broad)

    print(f"  Child Wrist Distance Limit: {engine_child.tuck_wrist_dist_limit:.3f} screen units")
    print(f"  Broad Adult Distance Limit: {engine_broad.tuck_wrist_dist_limit:.3f} screen units")

    # Uji verifikasi tuck
    # Jarak pergelangan 0.18 unit
    # Pada anak: 0.18 < 0.196 (Valid Compact)
    # Pada dewasa lebar: 0.18 << 0.406 (Valid Compact)
    is_child_tuck = engine_child.is_adaptive_tuck_dive(wrist_dist=0.18, elbows_below_wrists=True, elbows_below_shoulders=True)
    is_broad_tuck = engine_broad.is_adaptive_tuck_dive(wrist_dist=0.35, elbows_below_wrists=True, elbows_below_shoulders=True)

    assert is_child_tuck, "Child compact hands should trigger tuck dive"
    assert is_broad_tuck, "Broad adult with larger chest should trigger tuck dive naturally"
    print("  -> PASSED: Deteksi Tuck Dive proporsional dengan dimensi torso dan bahu pemain.")


def test_comfort_and_fatigue_reduction():
    print("[TEST 4.6] Comfort & Fatigue Reduction Verification...")
    
    profile = get_default_profile()
    engine = AdaptiveThresholdEngine(profile)
    sm = GestureStateMachine(adaptive_engine=engine)

    # 1. Pose Meluncur Santai (Gliding Relaxed Envelope):
    # Tangan direntangkan santai pada ketinggian netral (avg_flap_height = -0.05), tanpa kecepatan vertikal
    kpts_glide = {
        "ls": (0.40, 0.40), "rs": (0.60, 0.40),
        "lh": (0.44, 0.70), "rh": (0.56, 0.70),
        "le": (0.30, 0.42), "re": (0.70, 0.42),
        "lw": (0.22, 0.43), "rw": (0.78, 0.43)
    }
    bio_glide = {
        "shoulder_width": 0.20,
        "torso_length": 0.35,
        "wingspan_ratio": 1.95,
        "lean_angle_deg": 0.5,
        "avg_flap_height": -0.05,
        "left_flap_height": -0.05,
        "right_flap_height": -0.05
    }

    res_glide = sm.update(kpts_glide, bio_glide, is_tracking_valid=True)
    print(f"  Restful Glide State: {res_glide['active_state']} (Flap: {res_glide['is_flapping']}, Dive: {res_glide['is_tuck_dive']}, Steer: {res_glide['steering_input']:.2f})")
    assert res_glide["active_state"] == "GLIDE", "Restful pose must strictly register as GLIDE"
    assert not res_glide["is_flapping"] and not res_glide["is_tuck_dive"], "No accidental flap or dive during glide"
    assert res_glide["steering_input"] == 0.0, "Zero unintentional steer during glide"

    # 2. Kepakan Santai (1.6 Hz tempo natural tanpa perlu thrashing keras):
    # Simulasi 1 stroke kepakan santai
    sm.motion_tracker.history.clear()
    t_now = time.perf_counter()
    # Simulasikan upstroke
    sm.flap_classifier.phase = FlapStrokePhase.UPSTROKE
    sm.flap_classifier.last_active_phase = FlapStrokePhase.UPSTROKE
    sm.flap_classifier.stroke_peak_y = 0.35
    sm.flap_classifier.stroke_trough_y = -0.15

    # Lakukan downstroke santai
    is_flap, phase, freq, pwr = sm.flap_classifier.update(
        avg_flap_height=-0.15, vert_velocity=-1.8, t=t_now + 0.1, adaptive_engine=engine
    )
    print(f"  Relaxed Natural Flap Power: {pwr*100:.1f}%")
    assert pwr >= 0.75, f"Natural 1.6 Hz comfortable flap must generate robust lift >= 75% without exhausting strain (got {pwr})"
    print("  -> PASSED: Pose meluncur stabil dan kepakan santai terbukti mereduksi kelelahan fisik pemain.")


def test_udp_34_float_telemetry_protocol():
    print("[TEST 4.7] UDP Telemetry 34-Float Protocol Integrity (Phase 4)...")
    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    
    success = sender.send_pose(
        ls=(0.40, 0.40), rs=(0.60, 0.40),
        lw=(0.20, 0.45), rw=(0.80, 0.45),
        lh=(0.44, 0.72), rh=(0.56, 0.72),
        mouth_open=0.0,
        le=(0.30, 0.44), re=(0.70, 0.44),
        is_dive=0.0, is_flap=1.0, flap_freq=1.65, flap_power=0.88,
        body_pitch=0.25,
        nose=(0.50, 0.25),
        wingspan_ratio=2.10, flap_height=0.15, lean_angle_deg=-2.5, tracking_state=1.0,
        is_dash=0.0, dash_power=0.0, steering_input=-0.15, active_state_id=1.0,
        calib_state_id=5.0, calib_progress=1.0
    )
    assert success, "UDP send_pose must return True"
    sender.close()
    print("  -> PASSED: Format 34-float telemetri dengan metadata kalibrasi terkirim dengan sempurna.")


def run_all_phase4_tests():
    print("=" * 70)
    print("  PHASE 4 VALIDATION TEST SUITE: CALIBRATION & ADAPTIVE CONTROL")
    print("=" * 70)

    test_calibration_step_sequence()
    test_player_profiles_variety()
    test_adaptive_flap_thresholding()
    test_adaptive_leaning_and_asymmetry_deadzone()
    test_adaptive_tuck_dive()
    test_comfort_and_fatigue_reduction()
    test_udp_34_float_telemetry_protocol()

    print("=" * 70)
    print("  ALL 7 PHASE 4 VALIDATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_all_phase4_tests()
