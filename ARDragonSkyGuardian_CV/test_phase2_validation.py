"""
test_phase2_validation.py
Suite Validasi Otomatis Phase 2: Body Motion & Gesture Recognition.
Menguji secara menyeluruh 6 pilar utama pengenalan gestur:
1. Motion Tracking (Windowed Velocity, Acceleration, Angular Velocity)
2. Flapping Recognition (Upstroke/Downstroke, Amplitude, Frequency, Twitch Rejection)
3. Continuous Leaning (Deadzone, Smooth Monotonic Steering, Left/Right Discrimination)
4. Tuck Dive Recognition (Geometry, Minimum Hold Duration, Anti-False Trigger)
5. Propeller Dash vs Flapping Discrimination (Orbital Monotonic Rotation vs 1D Linear Oscillation)
6. Gesture State Machine (Hierarchical Priority, Cooldowns, Tracking Loss Safety)
"""

import sys
import time
import math
from typing import Dict, Tuple, List
import numpy as np

from motion_recognizer import (
    TemporalMotionTracker,
    FlapStrokeClassifier,
    ContinuousLeanClassifier,
    TuckDiveClassifier,
    PropellerRotationClassifier,
    GestureStateMachine,
    GestureState,
    FlapStrokePhase
)
from pose_stabilizer import BiometricNormalizer


def test_2_1_motion_tracking():
    print("\n" + "=" * 65)
    print("TEST 2.1: Motion Tracking (Velocity, Acceleration, Angular Omega)")
    print("=" * 65)

    tracker = TemporalMotionTracker(history_size=20)
    normalizer = BiometricNormalizer()

    # Base pose
    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.70), (0.58, 0.70)
    le, re = (0.30, 0.42), (0.70, 0.42)

    # Simulate constant downward motion of left wrist from y=0.30 to y=0.60 at 1.0 unit/sec
    t_start = 100.0
    for i in range(15):
        t = t_start + i * 0.02  # 50 FPS
        lw_y = 0.30 + (i * 0.02) * 1.0  # speed = 1.0 /s
        kpts = {
            "ls": ls, "rs": rs, "lh": lh, "rh": rh,
            "le": le, "re": re, "lw": (0.20, lw_y), "rw": (0.80, 0.40)
        }
        bio = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, (0.20, lw_y), (0.80, 0.40))
        tracker.record_frame(kpts, bio, t)

    vx, vy = tracker.get_joint_velocity("lw", window_frames=3)
    ax, ay = tracker.get_joint_acceleration("lw")

    print(f"   - Expected vy : ~1.000")
    print(f"   - Measured vy : {vy:.3f} unit/s")
    print(f"   - Measured ay : {ay:.3f} unit/s^2 (Constant speed, expected near 0)")

    assert abs(vy - 1.0) < 0.08, f"Velocity estimation error: {vy}"
    assert abs(ay) < 1.5, f"Acceleration estimation error: {ay}"
    print("   [PASS] Perhitungan kecepatan dan percepatan temporal terverifikasi akurat.")


def test_2_2_flapping_recognition():
    print("\n" + "=" * 65)
    print("TEST 2.2: Flapping Recognition (Stroke Phases, Amplitude & Twitches)")
    print("=" * 65)

    classifier = FlapStrokeClassifier()

    # 1. Tes Gerakan Kecil / Twitch Tidak Disengaja (< 0.15 amplitude)
    # Harus menghasilkan power 0.0
    t = 10.0
    for i in range(20):
        t += 0.03
        small_osc = math.sin(t * 10.0) * 0.05
        vert_vel = math.cos(t * 10.0) * 0.5
        is_flap, phase, freq, power = classifier.update(small_osc, vert_vel, t)

    print(f"   [Gerakan Kecil] Flap Active: {is_flap} | Flap Power: {power*100:.1f}%")
    assert power < 0.15, "Gerakan kecil tidak sengaja tidak boleh menghasilkan flap power besar!"

    # 2. Tes Kepakan Penuh & Kuat (Upstroke -> Downstroke penuh)
    t = 20.0
    detected_phases = set()
    full_flaps = 0
    for i in range(80):
        t += 0.025  # 40 FPS
        # Amplitude = 0.50 (melewati bahu secara signifikan)
        h_v = math.sin(t * 12.0) * 0.50
        v_v = math.cos(t * 12.0) * 6.0  # high vertical velocity
        is_flap, phase, freq, power = classifier.update(h_v, v_v, t)
        detected_phases.add(phase)
        if is_flap and power > 0.60:
            full_flaps += 1

    print(f"   [Kepakan Penuh] Fase Terdeteksi: {[p.value for p in detected_phases]}")
    print(f"   [Kepakan Penuh] Flap Power Maksimal: {power*100:.1f}% | Freq: {freq:.2f} Hz")

    assert FlapStrokePhase.UPSTROKE in detected_phases, "Harus mendeteksi UPSTROKE"
    assert FlapStrokePhase.DOWNSTROKE in detected_phases, "Harus mendeteksi DOWNSTROKE"
    assert full_flaps > 0, "Kepakan penuh harus menghasilkan daya dorong flap power tinggi"
    print("   [PASS] Segmentasi Upstroke/Downstroke dan penolakan twitch terverifikasi.")


def test_2_3_continuous_leaning():
    print("\n" + "=" * 65)
    print("TEST 2.3: Continuous Leaning (Deadzone & Monotonic Scaling)")
    print("=" * 65)

    # 1. Di dalam Deadzone (+/- 3.0 derajat)
    steer_dz_left, lbl1 = ContinuousLeanClassifier.evaluate_lean(-2.0, 0.0, 0.0)
    steer_dz_right, lbl2 = ContinuousLeanClassifier.evaluate_lean(2.5, 0.0, 0.0)

    print(f"   [Deadzone Check] -2.0° -> {steer_dz_left:.3f} ({lbl1}) | +2.5° -> {steer_dz_right:.3f} ({lbl2})")
    assert steer_dz_left == 0.0 and steer_dz_right == 0.0, "Di dalam deadzone harus bernilai tepat 0.0"

    # 2. Kemiringan Sedang (-12.0 derajat vs +12.0 derajat)
    steer_med_left, lbl_l = ContinuousLeanClassifier.evaluate_lean(-12.0, -0.2, 0.2)
    steer_med_right, lbl_r = ContinuousLeanClassifier.evaluate_lean(12.0, 0.2, -0.2)

    print(f"   [Kemiringan Sedang] -12° -> {steer_med_left:.3f} ({lbl_l}) | +12° -> {steer_med_right:.3f} ({lbl_r})")
    assert steer_med_left < -0.20 and lbl_l == "LEAN_LEFT"
    assert steer_med_right > 0.20 and lbl_r == "LEAN_RIGHT"
    assert abs(steer_med_left + steer_med_right) < 0.05, "Respon harus simetris"

    # 3. Kemiringan Penuh (+25.0 derajat)
    steer_full, lbl_full = ContinuousLeanClassifier.evaluate_lean(26.0, 0.5, -0.5)
    print(f"   [Kemiringan Penuh] +26° -> {steer_full:.3f} ({lbl_full})")
    assert steer_full >= 0.90, "Kemiringan penuh harus mendekati 1.0"
    print("   [PASS] Kurva kemudi kontinu dengan deadzone dan sensitivitas adaptif terverifikasi.")


def test_2_4_tuck_dive():
    print("\n" + "=" * 65)
    print("TEST 2.4: Tuck Dive Recognition (Hold Duration & Geometric Check)")
    print("=" * 65)

    classifier = TuckDiveClassifier()
    ls, rs = (0.40, 0.38), (0.60, 0.38)
    le, re = (0.34, 0.56), (0.66, 0.56)  # Elbows pointing down below shoulders & wrists
    lw, rw = (0.44, 0.44), (0.56, 0.44)  # Wrists compact at chest (Wingspan Ratio ~ 0.60)
    wingspan_compact = 0.60
    avg_flap_h = -0.15

    # 1. Pose baru pertama kali muncul (t = 0.0, hold duration < 120ms)
    # Tidak boleh langsung mentrigger dive!
    t0 = 50.0
    is_dive_1, _ = classifier.evaluate(wingspan_compact, avg_flap_h, ls, rs, le, re, lw, rw, t=t0)
    print(f"   - Frame 1 (t = 0ms)    : is_dive = {is_dive_1} (Menunggu minimum hold duration)")
    assert not is_dive_1, "Tuck dive tidak boleh langsung trigger di frame pertama tanpa hold duration"

    # 2. Pose ditahan melebihi 120ms (t = 150ms)
    is_dive_2, power = classifier.evaluate(wingspan_compact, avg_flap_h, ls, rs, le, re, lw, rw, t=t0 + 0.15)
    print(f"   - Frame 2 (t = 150ms)  : is_dive = {is_dive_2} | Dive Power = {power*100:.1f}%")
    assert is_dive_2, "Tuck dive harus terkonfirmasi setelah ditahan melebihi batas minimum durasi"

    # 3. Sayap dibuka kembali (Wingspan Ratio = 2.4)
    # Harus rilis seketika
    is_dive_3, _ = classifier.evaluate(2.40, 0.0, ls, rs, (0.30, 0.40), (0.70, 0.40), (0.16, 0.40), (0.84, 0.40), t=t0 + 0.20)
    print(f"   - Frame 3 (Sayap Buka) : is_dive = {is_dive_3} (Rilis instan)")
    assert not is_dive_3, "Tuck dive harus rilis seketika saat sayap dibuka"
    print("   [PASS] Deteksi Tuck Dive dengan hold duration check dan release instan terverifikasi.")


def test_2_5_propeller_dash_vs_flapping():
    print("\n" + "=" * 65)
    print("TEST 2.5: Propeller Dash vs Flapping Discrimination")
    print("=" * 65)

    rot_classifier = PropellerRotationClassifier()
    ls, rs = (0.40, 0.40), (0.60, 0.40)

    # 1. KASUS A: Gerakan Flapping (1D Linear Oscillation)
    # Tangan naik-turun bolak-balik. Propeller Dash TIDAK BOLEH aktif!
    t = 100.0
    dash_triggered_during_flap = False
    for i in range(60):
        t += 0.03
        y_osc = math.sin(t * 12.0) * 0.20
        lw = (0.22, 0.40 + y_osc)
        rw = (0.78, 0.40 + y_osc)
        is_dash, power, _ = rot_classifier.update(ls, rs, lw, rw, t)
        if is_dash:
            dash_triggered_during_flap = True

    print(f"   [Uji Flapping 1D] Propeller Dash Terpicu: {dash_triggered_during_flap}")
    assert not dash_triggered_during_flap, "Flapping 1D TIDAK BOLEH memicu Propeller Dash!"

    # 2. KASUS B: Gerakan Rotasi Lengan Nyata (2D Orbital Monotonic Rotation)
    # Tangan berputar membentuk lintasan lingkaran konsisten (> 240 derajat akumulasi)
    rot_classifier = PropellerRotationClassifier()
    dash_detected = False
    max_dash_power = 0.0
    for i in range(40):
        t += 0.03
        angle = t * 14.0  # Monotonic rotation
        radius = 0.14
        lw = (0.30 + math.cos(angle) * radius, 0.40 + math.sin(angle) * radius)
        rw = (0.70 + math.cos(angle + math.pi) * radius, 0.40 + math.sin(angle + math.pi) * radius)
        is_dash, power, _ = rot_classifier.update(ls, rs, lw, rw, t)
        if is_dash:
            dash_detected = True
            max_dash_power = max(max_dash_power, power)

    print(f"   [Uji Rotasi Lengan] Propeller Dash Terdeteksi: {dash_detected} | Max Power: {max_dash_power*100:.1f}%")
    assert dash_detected, "Gerakan rotasi konsisten harus memicu Propeller Dash!"
    print("   [PASS] Diskriminasi matematis antara Flapping vs Propeller Dash terverifikasi sempurna.")


def test_2_6_gesture_state_machine():
    print("\n" + "=" * 65)
    print("TEST 2.6: Gesture State Machine (Priority, Cooldowns, & Safety)")
    print("=" * 65)

    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.70), (0.58, 0.70)
    le, re = (0.30, 0.42), (0.70, 0.42)
    lw_glide, rw_glide = (0.16, 0.42), (0.84, 0.42)

    # 1. State Awal: Glide
    kpts_glide = {"ls": ls, "rs": rs, "lh": lh, "rh": rh, "le": le, "re": re, "lw": lw_glide, "rw": rw_glide}
    bio_glide = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_glide, rw_glide)
    res_glide = sm.update(kpts_glide, bio_glide, is_tracking_valid=True)

    print(f"   - State Awal (Sayap Rentang) : {res_glide['active_state']}")
    assert res_glide['active_state'] == GestureState.NEUTRAL_GLIDE.value

    # 2. Prioritas 1: Propeller Dash (Saat kedua tangan berputar kencang)
    t = time.perf_counter()
    res_dash = None
    for i in range(35):
        t += 0.03
        ang = t * 16.0
        lw_rot = (0.30 + math.cos(ang) * 0.12, 0.42 + math.sin(ang) * 0.12)
        rw_rot = (0.70 + math.cos(ang + math.pi) * 0.12, 0.42 + math.sin(ang + math.pi) * 0.12)
        k = {"ls": ls, "rs": rs, "lh": lh, "rh": rh, "le": le, "re": re, "lw": lw_rot, "rw": rw_rot}
        b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_rot, rw_rot)
        res_dash = sm.update(k, b, is_tracking_valid=True)

    print(f"   - Transisi ke Rotasi Lengan  : {res_dash['active_state']} (Dash Power: {res_dash['dash_power']*100:.1f}%)")
    assert res_dash['active_state'] == GestureState.PROPELLER_DASH.value

    # 3. Safety Fallback saat Tracking Hilang (LOST)
    res_lost = sm.update({}, {}, is_tracking_valid=False)
    print(f"   - Safety Fallback saat LOST  : {res_lost['active_state']} | Steering: {res_lost['steering_input']} | Power: {res_lost['flap_power']}")
    assert res_lost['active_state'] == GestureState.NEUTRAL_GLIDE.value
    assert res_lost['steering_input'] == 0.0 and res_lost['dash_power'] == 0.0 and res_lost['dive_power'] == 0.0
    print("   [PASS] State Machine prioritas, proteksi konflik, dan safety lockout terverifikasi.")


def run_all_phase2_tests():
    print("=" * 70)
    print("🚀 MENJALANKAN SUITE VALIDASI GESTURE RECOGNITION (PHASE 2)")
    print("=" * 70)

    t0 = time.time()
    test_2_1_motion_tracking()
    test_2_2_flapping_recognition()
    test_2_3_continuous_leaning()
    test_2_4_tuck_dive()
    test_2_5_propeller_dash_vs_flapping()
    test_2_6_gesture_state_machine()

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"✅ SELURUH PENGUJIAN PHASE 2 BERHASIL DIVERIFIKASI (Total: {elapsed:.2f} detik)")
    print("=" * 70)


if __name__ == "__main__":
    run_all_phase2_tests()
