"""
test_additional_gestures.py
Suite Validasi Mendalam Fitur Tambahan Kontrol Terbang (Section 8 Test Scenarios)
Master Development Plan: Body Motion Recognition & Character Flight Physics

Skenario Pengujian:
1. Chest raised tanpa flapping (Harus TIDAK mentrigger Fly Up, tetap Glide)
2. Chest raised dengan flapping (Harus mentrigger FLY UP)
3. Upper arms tucked tanpa gerakan tangan dan tanpa forearms extended (Harus TIDAK mentrigger Hover / Gentle Descent)
4. Upper arms tucked dengan forearm flapping (Harus mentrigger HOVER)
5. Upper arms tucked dengan forearms extended tanpa flapping (Harus mentrigger GENTLE DESCENT / Tucked T-Pose)
6. Hover lalu berhenti mengepak (Harus rilis dari Hover ke Glide)
7. Hover lalu beralih ke gentle descent (Transisi mulus Hover -> Gentle Descent)
8. Gentle descent lalu kembali ke hover (Transisi mulus Gentle Descent -> Hover)
9. Gentle descent lalu melakukan normal dive (Transisi mulus Gentle Descent -> Normal Dive / Tuck Dive)
10. Fly Up lalu kembali ke normal flight (Transisi mulus Fly Up -> Normal Flight)
"""

import math
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pose_stabilizer import BiometricNormalizer, RobustKeypointTracker
from motion_recognizer import (
    GestureStateMachine,
    GestureState,
    FlapStrokePhase,
    FlyUpClassifier,
    HoverClassifier,
    GentleDescentClassifier
)


def make_kpts(ls, rs, lh, rh, le, re, lw, rw, nose=(0.50, 0.25)):
    return {
        "ls": ls, "rs": rs, "lh": lh, "rh": rh,
        "le": le, "re": re, "lw": lw, "rw": rw,
        "nose": nose
    }


def test_scenario_1_chest_raised_no_flap():
    print("\n[SKENARIO 1] Chest Raised Tanpa Flapping...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    # Dada diangkat ke atas (Shoulder naik dari 0.40 ke 0.34, Torso memanjang)
    ls, rs = (0.40, 0.34), (0.60, 0.34)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.28, 0.40), (0.72, 0.40)
    lw, rw = (0.16, 0.40), (0.84, 0.40) # Tangan diam membentang (Glide)

    k = make_kpts(ls, rs, lh, rh, le, re, lw, rw)
    b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)

    res = None
    for _ in range(15):
        res = sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.01)

    print(f"  -> Chest Elevation: {b['chest_elevation']:.2f} (Ambang: >= 1.74)")
    print(f"  -> Flap Active: {res['is_flapping']}, Active State: {res['active_state']}")
    assert b['chest_elevation'] >= 1.74, "Chest elevation harus terdeteksi di atas ambang batas"
    assert res['active_state'] == GestureState.NEUTRAL_GLIDE.value, f"Harus tetap GLIDE, didapat: {res['active_state']}"
    assert not res['is_fly_up'], "TIDAK boleh memicu FLY_UP tanpa adanya flapping aktif!"
    print("  -> PASS: Dada terangkat tanpa kepakan tidak memicu Fly Up.")


def test_scenario_2_chest_raised_with_flap():
    print("\n[SKENARIO 2] Chest Raised Dengan Flapping...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    # Dada diangkat ke atas + Flapping vertikal berulang
    ls, rs = (0.40, 0.34), (0.60, 0.34)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.28, 0.42), (0.72, 0.42)

    res = None
    for i in range(35):
        y_osc = math.sin(i * 0.45) * 0.30
        lw = (0.18, 0.36 + y_osc)
        rw = (0.82, 0.36 + y_osc)
        k = make_kpts(ls, rs, lh, rh, le, re, lw, rw)
        b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)
        res = sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.015)

    print(f"  -> Chest Elevation: {b['chest_elevation']:.2f}")
    print(f"  -> Active State: {res['active_state']} (Fly Up Power: {res['fly_up_power']*100:.1f}%)")
    assert res['active_state'] == GestureState.FLY_UP.value, f"Harus terdeteksi FLY_UP, didapat: {res['active_state']}"
    assert res['is_fly_up'], "is_fly_up flag harus True"
    assert res['fly_up_power'] > 0.30, "Fly Up power harus terisi proporsional"
    print("  -> PASS: Dada terangkat dengan kepakan aktif berhasil memicu Fly Up.")


def test_scenario_3_upper_arms_tucked_no_motion():
    print("\n[SKENARIO 3] Upper Arms Tucked Tanpa Gerakan Tangan (Bukan T-Pose)...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    # Lengan atas rapat ke dada, tangan menggantung lemas ke bawah (bukan forearms extended)
    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.41, 0.54), (0.59, 0.54) # Siku rapat ke dada (Prox = 0.05)
    lw, rw = (0.42, 0.65), (0.58, 0.65) # Tangan menggantung ke bawah

    k = make_kpts(ls, rs, lh, rh, le, re, lw, rw)
    b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)

    res = None
    for _ in range(15):
        res = sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.01)

    print(f"  -> Upper Arm Proximity: {b['upper_arm_proximity']:.2f} (Tucked: {b['is_upper_arms_tucked']})")
    print(f"  -> Forearms Extended T-Pose: {b['is_forearms_extended']}")
    print(f"  -> Active State: {res['active_state']}")
    assert b['is_upper_arms_tucked'], "Lengan atas harus terdeteksi rapat ke dada"
    assert not b['is_forearms_extended'], "Lengan menggantung ke bawah bukan T-pose"
    assert res['active_state'] == GestureState.NEUTRAL_GLIDE.value, f"Harus tetap GLIDE, didapat: {res['active_state']}"
    assert not res['is_hover'] and not res['is_gentle_descent']
    print("  -> PASS: Lengan atas rapat tanpa ekstensi T-pose atau kepakan tidak memicu Hover / Gentle Descent.")


def test_scenario_4_upper_arms_tucked_with_forearm_flapping():
    print("\n[SKENARIO 4] Upper Arms Tucked Dengan Forearm Flapping (Hover Mode)...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    # Siku tetap rapat ke dada (stasioner), pergelangan tangan mengepak naik-turun
    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.41, 0.54), (0.59, 0.54)

    res = None
    for i in range(30):
        y_osc = math.sin(i * 0.55) * 0.18
        lw = (0.35, 0.52 + y_osc)
        rw = (0.65, 0.52 + y_osc)
        k = make_kpts(ls, rs, lh, rh, le, re, lw, rw)
        b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)
        res = sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.015)

    print(f"  -> Upper Arm Proximity: {b['upper_arm_proximity']:.2f} | Siku Rapat: {b['is_upper_arms_tucked']}")
    print(f"  -> Active State: {res['active_state']} (Hover Power: {res['hover_power']*100:.1f}%)")
    assert res['active_state'] == GestureState.HOVER.value, f"Harus terdeteksi HOVER, didapat: {res['active_state']}"
    assert res['is_hover'], "is_hover flag harus True"
    assert res['hover_power'] > 0.35, "Hover power harus terisi"
    print("  -> PASS: Pengepakan lengan bawah dengan lengan atas rapat sukses memicu Hover Mode.")


def test_scenario_5_tucked_t_pose_gentle_descent():
    print("\n[SKENARIO 5] Tucked T-Pose Tanpa Flapping (Gentle Descent)...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    # Lengan atas rapat ke dada, siku ditekuk 90°, lengan bawah direntangkan ke samping (T-pose lengan bawah)
    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.41, 0.54), (0.59, 0.54) # Siku rapat
    lw, rw = (0.22, 0.54), (0.78, 0.54) # Pergelangan merentang ke lateral samping

    k = make_kpts(ls, rs, lh, rh, le, re, lw, rw)
    b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)

    res = None
    # Tahan selama >120ms (minimum hold duration)
    for _ in range(20):
        res = sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.015)

    print(f"  -> Prox: {b['upper_arm_proximity']:.2f} | Elbow Angle: {b['avg_elbow_angle']:.1f}° | Spread: {b['forearm_lateral_spread']:.2f}")
    print(f"  -> Forearms Extended T-Pose: {b['is_forearms_extended']}")
    print(f"  -> Active State: {res['active_state']} (Stabilitas: {res['gentle_stability']*100:.1f}%)")
    assert b['is_forearms_extended'], "Pose T-pose lengan bawah harus terdeteksi"
    assert res['active_state'] == GestureState.GENTLE_DESCENT.value, f"Harus terdeteksi GENTLE_DESCENT, didapat: {res['active_state']}"
    assert res['is_gentle_descent'], "is_gentle_descent flag harus True"
    assert res['gentle_stability'] > 0.40
    print("  -> PASS: Tucked T-pose tanpa kepakan sukses memicu Gentle Descent.")


def test_scenario_6_hover_stops_flapping_to_glide():
    print("\n[SKENARIO 6] Hover Lalu Berhenti Mengepak & Melepas Lengan (Kembali ke Glide)...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.41, 0.54), (0.59, 0.54)

    # 1. Hover aktif
    for i in range(25):
        y_osc = math.sin(i * 0.55) * 0.18
        lw = (0.35, 0.52 + y_osc)
        rw = (0.65, 0.52 + y_osc)
        k = make_kpts(ls, rs, lh, rh, le, re, lw, rw)
        b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)
        sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.01)

    assert sm.current_state == GestureState.HOVER

    # 2. Berhenti mengepak dan bentangkan sayap santai (Glide)
    le_glide, re_glide = (0.30, 0.42), (0.70, 0.42)
    lw_glide, rw_glide = (0.16, 0.42), (0.84, 0.42)
    k_glide = make_kpts(ls, rs, lh, rh, le_glide, re_glide, lw_glide, rw_glide)
    b_glide = normalizer.calculate_biometrics(ls, rs, lh, rh, le_glide, re_glide, lw_glide, rw_glide)

    res = None
    for _ in range(25):
        res = sm.update(k_glide, b_glide, is_tracking_valid=True)
        time.sleep(0.015)

    print(f"  -> State Akhir: {res['active_state']}")
    assert res['active_state'] == GestureState.NEUTRAL_GLIDE.value, f"Harus kembali ke GLIDE, didapat: {res['active_state']}"
    assert not res['is_hover']
    print("  -> PASS: Berhenti mengepak dari Hover berhasil kembali ke Glide.")


def test_scenario_7_hover_to_gentle_descent_transition():
    print("\n[SKENARIO 7] Transisi Mulus: Hover -> Gentle Descent...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.41, 0.54), (0.59, 0.54)

    # 1. Pengepakan Hover
    for i in range(25):
        y_osc = math.sin(i * 0.55) * 0.18
        lw = (0.35, 0.52 + y_osc)
        rw = (0.65, 0.52 + y_osc)
        k = make_kpts(ls, rs, lh, rh, le, re, lw, rw)
        b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)
        sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.01)

    assert sm.current_state == GestureState.HOVER
    print(f"  -> Status Fase 1: {sm.current_state.value}")

    # 2. Hentikan kepakan, rentangkan lengan bawah membentuk T (Tucked T-Pose)
    lw_t, rw_t = (0.22, 0.54), (0.78, 0.54)
    k_t = make_kpts(ls, rs, lh, rh, le, re, lw_t, rw_t)
    b_t = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_t, rw_t)

    res = None
    for _ in range(25):
        res = sm.update(k_t, b_t, is_tracking_valid=True)
        time.sleep(0.015)

    print(f"  -> Status Fase 2 (Kepakan berhenti di T-pose): {res['active_state']}")
    assert res['active_state'] == GestureState.GENTLE_DESCENT.value, f"Harus bertransisi ke GENTLE_DESCENT, didapat: {res['active_state']}"
    assert res['is_gentle_descent']
    print("  -> PASS: Transisi mulus dari Hover ke Gentle Descent terverifikasi.")


def test_scenario_8_gentle_descent_to_hover_transition():
    print("\n[SKENARIO 8] Transisi Mulus: Gentle Descent -> Hover...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.41, 0.54), (0.59, 0.54)
    lw_t, rw_t = (0.22, 0.54), (0.78, 0.54)

    # 1. Gentle Descent diam
    k_t = make_kpts(ls, rs, lh, rh, le, re, lw_t, rw_t)
    b_t = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_t, rw_t)
    for _ in range(20):
        sm.update(k_t, b_t, is_tracking_valid=True)
        time.sleep(0.015)

    assert sm.current_state == GestureState.GENTLE_DESCENT
    print(f"  -> Status Fase 1: {sm.current_state.value}")

    # 2. Mulai mengepakkan lengan bawah
    res = None
    for i in range(25):
        y_osc = math.sin(i * 0.55) * 0.18
        lw = (0.35, 0.52 + y_osc)
        rw = (0.65, 0.52 + y_osc)
        k = make_kpts(ls, rs, lh, rh, le, re, lw, rw)
        b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)
        res = sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.015)

    print(f"  -> Status Fase 2 (Mulai forearm flapping): {res['active_state']}")
    assert res['active_state'] == GestureState.HOVER.value, f"Harus bertransisi ke HOVER, didapat: {res['active_state']}"
    assert res['is_hover']
    print("  -> PASS: Transisi mulus dari Gentle Descent ke Hover terverifikasi.")


def test_scenario_9_gentle_descent_to_normal_dive():
    print("\n[SKENARIO 9] Transisi: Gentle Descent -> Normal Dive (Tuck Dive)...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.41, 0.54), (0.59, 0.54)
    lw_t, rw_t = (0.22, 0.54), (0.78, 0.54)

    # 1. Gentle Descent
    k_t = make_kpts(ls, rs, lh, rh, le, re, lw_t, rw_t)
    b_t = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_t, rw_t)
    for _ in range(20):
        sm.update(k_t, b_t, is_tracking_valid=True)
        time.sleep(0.015)

    assert sm.current_state == GestureState.GENTLE_DESCENT
    print(f"  -> Status Fase 1: {sm.current_state.value}")

    # 2. Tarik kedua tangan rapat ke dada/sternum (Normal Dive)
    le_dive, re_dive = (0.38, 0.60), (0.62, 0.60)
    lw_dive, rw_dive = (0.47, 0.45), (0.53, 0.45) # Wingspan compact
    k_dive = make_kpts(ls, rs, lh, rh, le_dive, re_dive, lw_dive, rw_dive)
    b_dive = normalizer.calculate_biometrics(ls, rs, lh, rh, le_dive, re_dive, lw_dive, rw_dive)

    res = None
    for _ in range(25):
        res = sm.update(k_dive, b_dive, is_tracking_valid=True)
        time.sleep(0.015)

    print(f"  -> Status Fase 2 (Rapatkan tangan ke sternum): {res['active_state']}")
    assert res['active_state'] == GestureState.TUCK_DIVE.value, f"Harus bertransisi ke TUCK_DIVE, didapat: {res['active_state']}"
    assert res['is_tuck_dive']
    print("  -> PASS: Transisi dari Gentle Descent ke Normal Dive (Tuck Dive) terverifikasi.")


def test_scenario_10_fly_up_to_normal_flight():
    print("\n[SKENARIO 10] Transisi: Fly Up -> Normal Flight...")
    sm = GestureStateMachine()
    normalizer = BiometricNormalizer()

    lh, rh = (0.42, 0.72), (0.58, 0.72)
    le, re = (0.28, 0.42), (0.72, 0.42)

    # 1. Fly Up aktif (Chest raised + flapping)
    ls_raised, rs_raised = (0.40, 0.34), (0.60, 0.34)
    for i in range(25):
        y_osc = math.sin(i * 0.45) * 0.30
        lw = (0.18, 0.36 + y_osc)
        rw = (0.82, 0.36 + y_osc)
        k = make_kpts(ls_raised, rs_raised, lh, rh, le, re, lw, rw)
        b = normalizer.calculate_biometrics(ls_raised, rs_raised, lh, rh, le, re, lw, rw)
        sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.015)

    assert sm.current_state == GestureState.FLY_UP
    print(f"  -> Status Fase 1: {sm.current_state.value}")

    # 2. Turunkan dada ke posisi normal sambil tetap mengepak (Normal Flight / Flap to Climb)
    ls_norm, rs_norm = (0.40, 0.40), (0.60, 0.40) # Shoulder kembali ke posisi 0.40
    res = None
    for i in range(25):
        y_osc = math.sin(i * 0.45) * 0.30
        lw = (0.18, 0.42 + y_osc)
        rw = (0.82, 0.42 + y_osc)
        k = make_kpts(ls_norm, rs_norm, lh, rh, le, re, lw, rw)
        b = normalizer.calculate_biometrics(ls_norm, rs_norm, lh, rh, le, re, lw, rw)
        res = sm.update(k, b, is_tracking_valid=True)
        time.sleep(0.015)

    print(f"  -> Status Fase 2 (Dada normal + tetap kepak): {res['active_state']}")
    assert res['active_state'] == GestureState.FLAPPING.value, f"Harus kembali ke FLAP_TO_CLIMB, didapat: {res['active_state']}"
    assert not res['is_fly_up']
    assert res['is_flapping']
    print("  -> PASS: Transisi dari Fly Up ke Normal Flight terverifikasi mulus.")


def run_all_tests():
    print("=" * 70)
    print("🚀 MENJALANKAN SUITE UJI FITUR TAMBAHAN KONTROL TERBANG (PHASE A)")
    print("=" * 70)

    t0 = time.time()
    test_scenario_1_chest_raised_no_flap()
    test_scenario_2_chest_raised_with_flap()
    test_scenario_3_upper_arms_tucked_no_motion()
    test_scenario_4_upper_arms_tucked_with_forearm_flapping()
    test_scenario_5_tucked_t_pose_gentle_descent()
    test_scenario_6_hover_stops_flapping_to_glide()
    test_scenario_7_hover_to_gentle_descent_transition()
    test_scenario_8_gentle_descent_to_hover_transition()
    test_scenario_9_gentle_descent_to_normal_dive()
    test_scenario_10_fly_up_to_normal_flight()

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"🎉 SELURUH 10 SKENARIO UJI BERHASIL 100% TERVERIFIKASI! (Total: {elapsed:.2f} detik)")
    print("=" * 70)


if __name__ == '__main__':
    run_all_tests()
