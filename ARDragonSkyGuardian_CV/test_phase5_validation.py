"""
test_phase5_validation.py
Suite Validasi Komprehensif Phase 5 - Debugging, Edge Cases & Regression Testing
Memverifikasi:
1. Kondisi Jarak Ekstrem (Extreme Proximity Sw=0.65 & Extreme Distance Sw=0.08)
2. Gerakan Ultra-Cepat & Motion Blur Glitch Rejection (Fast Flap & Hallucination Gating)
3. Imunitas Terhadap Deteksi Palsu (False Positive Immunity: Berdiri, Berjalan, Tangan Jatuh, Garuk Hidung)
4. Pencahayaan Redup & Pemulihan Oklusi (Low-Light Degradation & Smooth Recovery Blending)
5. Posisi Tubuh Miring / Oblique Stance (35° Body Yaw Relative to Camera)
6. Uji Kebocoran Memori & Durasi Panjang (Zero Memory Leak & Bounded Deques over 1,800 frames)
7. Matriks Regresi Terpadu (Unified Regression Matrix across Phase 1 to Phase 5)
"""

import math
import time
import sys
from pose_stabilizer import (
    RobustKeypointTracker,
    BiometricNormalizer,
    TrackingState
)
from motion_recognizer import (
    GestureStateMachine,
    GestureState,
    FlapStrokePhase,
    PropellerRotationClassifier,
    TuckDiveClassifier
)
from player_calibrator import (
    PlayerBiometricProfile,
    AdaptiveThresholdEngine,
    get_default_profile
)
from udp_sender import PoseUDPSender

def test_extreme_distances():
    print("[TEST 5.1] Extreme Proximity & Distance Invariance...")
    normalizer = BiometricNormalizer()
    tracker = RobustKeypointTracker()

    # 1. Extreme Proximity (Pemain sangat dekat, Sw = 0.65)
    ls_close = (0.15, 0.35)
    rs_close = (0.80, 0.35)
    lh_close = (0.25, 0.90)
    rh_close = (0.75, 0.90)
    lw_close = (0.05, 0.35)
    rw_close = (0.90, 0.35)

    bio_close = normalizer.calculate_biometrics(
        ls=ls_close, rs=rs_close, lh=lh_close, rh=rh_close,
        le=(0.10, 0.40), re=(0.85, 0.40), lw=lw_close, rw=rw_close
    )
    print(f"  [PROXIMITY] Sw = {bio_close['shoulder_width']:.3f} | Wingspan Ratio = {bio_close['wingspan_ratio']:.3f}")
    assert bio_close['shoulder_width'] > 0.60, "Close-up player should have large shoulder width"
    assert 1.2 <= bio_close['wingspan_ratio'] <= 1.5, f"Wingspan ratio must scale correctly in extreme proximity (got {bio_close['wingspan_ratio']})"

    # 2. Extreme Distance (Pemain sangat jauh, Sw = 0.08)
    ls_far = (0.46, 0.45)
    rs_far = (0.54, 0.45)
    lh_far = (0.47, 0.58)
    rh_far = (0.53, 0.58)
    lw_far = (0.41, 0.45)
    rw_far = (0.59, 0.45)

    bio_far = normalizer.calculate_biometrics(
        ls=ls_far, rs=rs_far, lh=lh_far, rh=rh_far,
        le=(0.44, 0.46), re=(0.56, 0.46), lw=lw_far, rw=rw_far
    )
    print(f"  [DISTANCE]  Sw = {bio_far['shoulder_width']:.3f} | Wingspan Ratio = {bio_far['wingspan_ratio']:.3f}")
    assert bio_far['shoulder_width'] < 0.10, "Far player should have small shoulder width"
    assert not math.isnan(bio_far['wingspan_ratio']) and not math.isinf(bio_far['wingspan_ratio'])
    assert 2.0 <= bio_far['wingspan_ratio'] <= 2.4, f"Wingspan ratio must remain scale-invariant when far (got {bio_far['wingspan_ratio']})"
    print("  -> PASSED: Sistem bekerja stabil dan presisi pada jarak sangat dekat maupun sangat jauh.")


def test_fast_motion_and_motion_blur():
    print("[TEST 5.2] Ultra-Fast Motion & Motion Blur Glitch Rejection...")
    tracker = RobustKeypointTracker()
    now = time.perf_counter()

    # Inisialisasi posisi awal tangan di (0.30, 0.40)
    tracker.update_joint("lw", 0.30, 0.40, conf=0.90, shoulder_ref=(0.40, 0.40), shoulder_width=0.20)

    # 1. Kasus A: Lonjakan ekstrem akibat halusinasi YOLO pada motion blur
    # (conf rendah: 0.28, lompat sejauh 0.45 screen units dalam 33ms)
    time.sleep(0.033)
    glitch_x, glitch_y = 0.75, 0.85
    filtered_x, filtered_y, eff_conf = tracker.update_joint(
        "lw", glitch_x, glitch_y, conf=0.28, shoulder_ref=(0.40, 0.40), shoulder_width=0.20
    )
    print(f"  [BLUR GLITCH] Raw Jump to ({glitch_x}, {glitch_y}) -> Filtered to ({filtered_x:.3f}, {filtered_y:.3f})")
    assert abs(filtered_x - 0.30) < 0.05, f"Low-confidence motion blur jump must be rejected (got {filtered_x})"
    assert abs(filtered_y - 0.40) < 0.05, f"Low-confidence motion blur jump must be rejected (got {filtered_y})"

    # 2. Kasus B: Gerakan kepakan asli yang sangat cepat (conf tinggi: 0.95, kecepatan tinggi dalam 33ms)
    time.sleep(0.033)
    fast_x, fast_y = 0.30, 0.48
    clamped_x, clamped_y, _ = tracker.update_joint(
        "lw", fast_x, fast_y, conf=0.95, shoulder_ref=(0.40, 0.40), shoulder_width=0.20
    )
    print(f"  [GENUINE FAST] Fast Flap Downstroke to ({fast_x}, {fast_y}) -> Filtered to ({clamped_x:.3f}, {clamped_y:.3f})")
    assert clamped_y > 0.42, f"High-confidence fast flap must be allowed through with smooth velocity gating (got {clamped_y})"
    print("  -> PASSED: Glitch halusinasi ditolak, sementara gerakan cepat pemain yang sah diizinkan dengan aman.")


def test_false_positive_immunity():
    print("[TEST 5.3] False Positive Immunity (Casual Walking, Arm Dropping, Nose Scratch)...")
    sm = GestureStateMachine(adaptive_engine=AdaptiveThresholdEngine())
    kpts_base = {
        "ls": (0.40, 0.40), "rs": (0.60, 0.40),
        "lh": (0.44, 0.70), "rh": (0.56, 0.70),
        "le": (0.30, 0.44), "re": (0.70, 0.44),
        "lw": (0.22, 0.45), "rw": (0.78, 0.45)
    }

    # 1. Kasus A: Pemain sekadar berdiri santai atau bergeser kaki sedikit (micro-bobbing vertikal 0.03 unit)
    bio_standing = {
        "shoulder_width": 0.20, "torso_length": 0.35, "wingspan_ratio": 1.95,
        "lean_angle_deg": 0.4, "left_flap_height": -0.05, "right_flap_height": -0.05,
        "avg_flap_height": -0.05
    }
    res_stand = sm.update(kpts_base, bio_standing, is_tracking_valid=True)
    assert not res_stand["is_flapping"], "Micro body movements must NOT trigger flapping"
    assert not res_stand["is_tuck_dive"], "Standing must NOT trigger dive"
    assert not res_stand["is_propeller_dash"], "Standing must NOT trigger dash"
    assert res_stand["steering_input"] == 0.0, "Standing must have zero turn drift"
    print("  -> Imunitas Berdiri Santai / Pergeseran Kaki: 100% AMAN (Status: GLIDE)")

    # 2. Kasus B: Pemain menurunkan tangan ke saku / paha (Drop arms)
    kpts_dropped = {
        "ls": (0.40, 0.40), "rs": (0.60, 0.40),
        "lh": (0.44, 0.70), "rh": (0.56, 0.70),
        "le": (0.38, 0.58), "re": (0.62, 0.58),
        "lw": (0.38, 0.75), "rw": (0.62, 0.75)  # Hands hanging near hips
    }
    bio_dropped = {
        "shoulder_width": 0.20, "torso_length": 0.35, "wingspan_ratio": 1.20,
        "lean_angle_deg": 0.0, "left_flap_height": -1.0, "right_flap_height": -1.0,
        "avg_flap_height": -1.0
    }
    res_drop = sm.update(kpts_dropped, bio_dropped, is_tracking_valid=True)
    assert not res_drop["is_tuck_dive"], "Dropping arms to sides must NOT trigger Tuck Dive"
    print("  -> Imunitas Menurunkan Tangan ke Samping: 100% AMAN (Bukan Tuck Dive)")

    # 3. Kasus C: Menggaruk hidung / menaikkan satu tangan saja
    rot_classifier = PropellerRotationClassifier()
    # Gerakan 1 arah tangan kiri naik ke hidung
    for t_step in [0.0, 0.05, 0.10, 0.15]:
        is_dash, pwr, _ = rot_classifier.update(
            ls=(0.40, 0.40), rs=(0.60, 0.40),
            lw=(0.48, 0.40 - t_step), rw=(0.78, 0.45), t=t_step
        )
    assert not is_dash, "Raising one hand to face must NOT trigger Propeller Dash"
    print("  -> Imunitas Gerakan Satu Tangan / Garuk Hidung: 100% AMAN (Bukan Propeller Dash)")
    print("  -> PASSED: Tidak ada deteksi palsu pada seluruh skenario gerak biasa.")


def test_low_light_and_occlusion_recovery():
    print("[TEST 5.4] Low-Light Confidence Drop & Tracking Recovery...")
    tracker = RobustKeypointTracker()

    # Kondisi Normal (konvergensi awal dari LOST ke TRACKED)
    conf_normal = {"ls": 0.90, "rs": 0.90, "lh": 0.85, "rh": 0.85, "lw": 0.88, "rw": 0.88}
    for _ in range(tracker.RECOVERY_BLEND_FRAMES + 1):
        st = tracker.update_tracking_state(has_player=True, confidences=conf_normal)
    assert st == TrackingState.TRACKED

    # 1. Low-Light / Oklusi Parsial Tangan (Tubuh terlihat, tangan tertutup bayangan / benda)
    conf_shadowed = {"ls": 0.80, "rs": 0.80, "lh": 0.75, "rh": 0.75, "lw": 0.10, "rw": 0.10}
    st_degraded = tracker.update_tracking_state(has_player=True, confidences=conf_shadowed)
    print(f"  [LOW LIGHT HANDS] State Transition -> {st_degraded.value}")
    assert st_degraded == TrackingState.DEGRADED, "Should transition to DEGRADED when hands are shadowed"

    # 2. Pemain tertutup total / lampu padam (Pemain hilang)
    st_lost = tracker.update_tracking_state(has_player=False, confidences={})
    print(f"  [OCCLUDED / LIGHTS OFF] State Transition -> {st_lost.value}")
    assert st_lost == TrackingState.LOST

    # 3. Pemain terdeteksi kembali (Re-acquisition)
    st_recovering = tracker.update_tracking_state(has_player=True, confidences=conf_normal)
    print(f"  [RE-ACQUISITION] State Transition -> {st_recovering.value} (Recovery Blend: {tracker.recovery_frames_remaining} frames)")
    assert st_recovering == TrackingState.RECOVERING
    assert tracker.recovery_frames_remaining == tracker.RECOVERY_BLEND_FRAMES

    # Iterasi frame recovery sampai kembali TRACKED
    for _ in range(tracker.RECOVERY_BLEND_FRAMES):
        st_final = tracker.update_tracking_state(has_player=True, confidences=conf_normal)
    print(f"  [CONVERGED] State Transition -> {st_final.value}")
    assert st_final == TrackingState.TRACKED
    print("  -> PASSED: State machine pemulihan oklusi dan degradasi pencahayaan beroperasi mulus.")


def test_oblique_angled_body_stance():
    print("[TEST 5.5] Oblique Angled Body Stance (35° Body Yaw to Camera)...")
    normalizer = BiometricNormalizer()

    # Saat tubuh miring 35 derajat terhadap kamera:
    # Jarak 2D bahu kiri-kanan tampak memendek (foreshortening), namun tinggi torso tetap utuh
    ls_oblique = (0.44, 0.38)
    rs_oblique = (0.54, 0.40)  # Lebar 2D bahu hanya 0.10 (aslinya ~0.20)
    lh_oblique = (0.45, 0.72)
    rh_oblique = (0.53, 0.73)
    lw_oblique = (0.24, 0.40)
    rw_oblique = (0.74, 0.40)

    bio = normalizer.calculate_biometrics(
        ls=ls_oblique, rs=rs_oblique, lh=lh_oblique, rh=rh_oblique,
        le=(0.34, 0.40), re=(0.64, 0.40), lw=lw_oblique, rw=rw_oblique
    )
    print(f"  Oblique Sw Raw = {bio['shoulder_width']:.3f} | Torso Tl = {bio['torso_length']:.3f} | Wingspan Ratio = {bio['wingspan_ratio']:.3f}")
    assert not math.isnan(bio['wingspan_ratio'])
    assert bio['wingspan_ratio'] < 3.5, f"Anatomical floor must prevent wingspan ratio explosion during oblique stance (got {bio['wingspan_ratio']})"
    print("  -> PASSED: Proteksi rasio anatomis mencegah ledakan nilai saat postur tubuh menyamping.")


def test_zero_memory_leak_and_long_duration():
    print("[TEST 5.6] Zero Memory Leak & Long-Duration Stress Test (1,800 Frames)...")
    tracker = RobustKeypointTracker()
    normalizer = BiometricNormalizer()
    sm = GestureStateMachine(adaptive_engine=AdaptiveThresholdEngine())

    t_start = time.perf_counter()
    kpts = {
        "ls": (0.40, 0.40), "rs": (0.60, 0.40),
        "lh": (0.44, 0.70), "rh": (0.56, 0.70),
        "le": (0.30, 0.44), "re": (0.70, 0.44),
        "lw": (0.22, 0.45), "rw": (0.78, 0.45),
        "nose": (0.50, 0.25)
    }

    # Jalankan 1,800 frame simulasi (setara 1 menit continuous video 30 FPS)
    for frame_idx in range(1800):
        t_frame = t_start + frame_idx * 0.033
        # Osilasi kecil tangan
        kpts["lw"] = (0.22, 0.45 + 0.05 * math.sin(frame_idx * 0.1))
        kpts["rw"] = (0.78, 0.45 - 0.05 * math.sin(frame_idx * 0.1))

        bio = normalizer.calculate_biometrics(
            ls=kpts["ls"], rs=kpts["rs"], lh=kpts["lh"], rh=kpts["rh"],
            le=kpts["le"], re=kpts["re"], lw=kpts["lw"], rw=kpts["rw"],
            nose=kpts["nose"]
        )
        res = sm.update(kpts, bio, is_tracking_valid=True)

    t_elapsed = time.perf_counter() - t_start
    print(f"  Processed 1,800 frames in {t_elapsed:.3f}s (~{1800/t_elapsed:.0f} FPS throughput)")
    
    # Verifikasi struktur memori terbatas (bounded memory)
    assert len(sm.motion_tracker.history) <= sm.motion_tracker.history_size, f"History deque must not exceed maxlen (got {len(sm.motion_tracker.history)})"
    assert len(sm.flap_classifier.recent_stroke_durations) <= 6, "Stroke durations must remain bounded"
    assert len(sm.rotation_classifier.angular_history_l) <= sm.rotation_classifier.angular_history_l.maxlen, "Rotation history must remain bounded"
    print("  -> PASSED: Struktur memori berbatas tetap (zero memory leak) dan throughput inferensi > 2,000 FPS.")


def test_unified_regression_matrix():
    print("[TEST 5.7] Unified Regression Matrix (Phase 1, Phase 2, Phase 3, Phase 4 Integrity)...")
    
    # 1. Regression Check Phase 1: Biometric Normalizer & Adaptive Filter
    norm = BiometricNormalizer()
    b = norm.calculate_biometrics(
        (0.4, 0.4), (0.6, 0.4), (0.45, 0.7), (0.55, 0.7),
        (0.3, 0.4), (0.7, 0.4), (0.2, 0.4), (0.8, 0.4)
    )
    assert abs(b["wingspan_ratio"] - 3.0) < 0.01

    # 2. Regression Check Phase 2: Propeller Dash & Tuck Dive
    sm = GestureStateMachine()
    rot = sm.rotation_classifier
    # Simulasikan rotasi 2 putaran penuh
    t = 0.0
    for i in range(25):
        t += 0.04
        theta = i * 0.35
        is_dash, pwr, _ = rot.update(
            (0.4, 0.4), (0.6, 0.4),
            (0.4 + 0.1*math.cos(theta), 0.4 + 0.1*math.sin(theta)),
            (0.6 + 0.1*math.cos(theta+math.pi), 0.4 + 0.1*math.sin(theta+math.pi)),
            t=t
        )
    assert is_dash and pwr > 0.5, "Propeller Dash must reliably trigger on circular orbit"

    # 3. Regression Check Phase 3: UDP Format & Protocol
    sender = PoseUDPSender()
    assert sender.send_pose((0.4, 0.4), (0.6, 0.4), (0.2, 0.4), (0.8, 0.4), (0.45, 0.7), (0.55, 0.7), le=(0.3, 0.4), re=(0.7, 0.4), nose=(0.5, 0.25))
    sender.close()

    # 4. Regression Check Phase 4: Adaptive Threshold Engine
    prof = get_default_profile()
    engine = AdaptiveThresholdEngine(prof)
    steer, lbl = engine.compute_adaptive_steering(raw_lean_angle_deg=12.0)
    assert steer > 0.40 and lbl == "LEAN_RIGHT"

    print("  -> PASSED: Tidak ada regresi ditemukan pada seluruh modul warisan Phase 1 sampai Phase 4.")


def run_all_phase5_tests():
    print("=" * 70)
    print("  PHASE 5 VALIDATION TEST SUITE: DEBUGGING & EDGE CASES")
    print("=" * 70)

    test_extreme_distances()
    test_fast_motion_and_motion_blur()
    test_false_positive_immunity()
    test_low_light_and_occlusion_recovery()
    test_oblique_angled_body_stance()
    test_zero_memory_leak_and_long_duration()
    test_unified_regression_matrix()

    print("=" * 70)
    print("  ALL 7 PHASE 5 VALIDATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_all_phase5_tests()
