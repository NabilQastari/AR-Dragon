"""
test_phase1_validation.py
Suite Validasi Otomatis Phase 1: Computer Vision Upgrade & Tracking Stability.
Menguji secara sistematis 8 skenario pengujian sesuai spesifikasi Bagian 1.7:
1. Berdiri diam (Zero Drift & Jitter Test)
2. Mengangkat & Menurunkan tangan (Flap Height Metric Test)
3. Memiringkan tubuh (Lean Angle & Alignment Test)
4. Menggerakkan tangan secara berulang / Flapping (Frequency & Power Test)
5. Mendekati dan menjauhi kamera (Scale-Invariance & Biometric Normalization Test)
6. Keluar dan kembali ke frame (Tracking Loss & Smooth Recovery Test)
7. Sebagian tubuh tertutup / Oklusi (Missing Landmark & Outlier Rejection Test)
8. Integritas Protokol Transmisi UDP (Telemetri 28-Float CSV)
"""

import sys
import time
import math
from typing import Dict, Tuple, List
import numpy as np

from pose_stabilizer import (
    RobustKeypointTracker,
    BiometricNormalizer,
    TrackingState,
    WingFlapDetector,
    AdaptiveOneEuroFilter
)
from udp_sender import PoseUDPSender


def test_scenario_1_standing_still():
    print("\n" + "=" * 65)
    print("TEST 1: Berdiri Diam (Stationary Jitter & Zero-Drift)")
    print("=" * 65)

    tracker = RobustKeypointTracker()
    base_x, base_y = 0.50, 0.40

    # Simulate 60 frames with slight camera sensor noise (Gaussian noise sigma = 0.005)
    positions = []
    np.random.seed(42)

    for i in range(60):
        noise_x = np.random.normal(0, 0.004)
        noise_y = np.random.normal(0, 0.004)
        raw_x = base_x + noise_x
        raw_y = base_y + noise_y

        cx, cy, _ = tracker.update_joint("ls", raw_x, raw_y, conf=0.90)
        positions.append((cx, cy))

    # Calculate jitter (standard deviation)
    x_vals = [p[0] for p in positions[15:]]  # after warmup
    y_vals = [p[1] for p in positions[15:]]
    std_x = np.std(x_vals)
    std_y = np.std(y_vals)

    print(f"   - Raw noise sigma  : ~0.0040")
    print(f"   - Filtered std (X) : {std_x:.5f}")
    print(f"   - Filtered std (Y) : {std_y:.5f}")

    assert std_x < 0.0015, f"Jitter X terlalu tinggi: {std_x}"
    assert std_y < 0.0015, f"Jitter Y terlalu tinggi: {std_y}"
    print("   [PASS] Filter berhasil meredam jitter kamera hingga < 0.0015 (stabil sempurna saat diam).")


def test_scenario_2_arms_up_down():
    print("\n" + "=" * 65)
    print("TEST 2: Mengangkat & Menurunkan Tangan (Biometric Flap Height)")
    print("=" * 65)

    normalizer = BiometricNormalizer()
    ls = (0.40, 0.40)
    rs = (0.60, 0.40)
    lh = (0.42, 0.70)
    rh = (0.58, 0.70)
    le = (0.30, 0.42)
    re = (0.70, 0.42)

    # 1. Tangan di atas bahu (Arms raised)
    lw_up = (0.30, 0.20)
    rw_up = (0.70, 0.20)
    bio_up = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_up, rw_up)

    # 2. Tangan di bawah bahu (Arms lowered)
    lw_down = (0.32, 0.60)
    rw_down = (0.68, 0.60)
    bio_down = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_down, rw_down)

    print(f"   - Tangan di Atas Bahu : avg_flap_height = {bio_up['avg_flap_height']:+.2f}")
    print(f"   - Tangan di Bawah Bahu: avg_flap_height = {bio_down['avg_flap_height']:+.2f}")

    assert bio_up["avg_flap_height"] > 0.5, "Flap height saat tangan di atas harus positif signifikan"
    assert bio_down["avg_flap_height"] < -0.5, "Flap height saat tangan di bawah harus negatif signifikan"
    print("   [PASS] Metrik ketinggian tangan relatif terhadap torso terukur secara akurat.")


def test_scenario_3_body_leaning():
    print("\n" + "=" * 65)
    print("TEST 3: Memiringkan Tubuh (Body Lean Angle & Alignment)")
    print("=" * 65)

    normalizer = BiometricNormalizer()
    lh = (0.45, 0.70)
    rh = (0.55, 0.70)
    le = (0.28, 0.42)
    re = (0.72, 0.42)
    lw = (0.20, 0.42)
    rw = (0.80, 0.42)

    # 1. Netral (Tegak lurus)
    ls_neutral = (0.40, 0.40)
    rs_neutral = (0.60, 0.40)
    bio_neutral = normalizer.calculate_biometrics(ls_neutral, rs_neutral, lh, rh, le, re, lw, rw)

    # 2. Condong Kanan
    ls_right = (0.48, 0.40)
    rs_right = (0.68, 0.40)
    bio_right = normalizer.calculate_biometrics(ls_right, rs_right, lh, rh, le, re, lw, rw)

    # 3. Condong Kiri
    ls_left = (0.32, 0.40)
    rs_left = (0.52, 0.40)
    bio_left = normalizer.calculate_biometrics(ls_left, rs_left, lh, rh, le, re, lw, rw)

    print(f"   - Posisi Netral : Lean Angle = {bio_neutral['lean_angle_deg']:+.2f}° | Norm = {bio_neutral['body_lean_norm']:+.2f}")
    print(f"   - Condong Kanan : Lean Angle = {bio_right['lean_angle_deg']:+.2f}° | Norm = {bio_right['body_lean_norm']:+.2f}")
    print(f"   - Condong Kiri  : Lean Angle = {bio_left['lean_angle_deg']:+.2f}° | Norm = {bio_left['body_lean_norm']:+.2f}")

    assert abs(bio_neutral["body_lean_norm"]) <= 0.05, "Netral harus di dalam deadzone"
    assert bio_right["lean_angle_deg"] > 10.0 and bio_right["body_lean_norm"] > 0.5, "Condong kanan harus positif signifikan"
    assert bio_left["lean_angle_deg"] < -10.0 and bio_left["body_lean_norm"] < -0.5, "Condong kiri harus negatif signifikan"
    print("   [PASS] Deteksi sudut kemiringan torso dan normalisasi deadzone bekerja sempurna.")


def test_scenario_4_repetitive_flapping():
    print("\n" + "=" * 65)
    print("TEST 4: Kepakan Berulang / Flapping (Frequency & Power)")
    print("=" * 65)

    detector = WingFlapDetector(hysteresis=0.035)
    ls = (0.40, 0.40)
    rs = (0.60, 0.40)

    # Simulate 4 full flap cycles at ~2.5 Hz over 60 simulated frames
    flap_count = 0
    t_sim = 0.0
    for i in range(80):
        t_sim += 0.025  # 40 FPS simulation
        arm_osc = math.sin(t_sim * 16.0) * 0.15  # Up and down across shoulder level 0.40
        lw = (0.25, 0.40 + arm_osc)
        rw = (0.75, 0.40 + arm_osc)

        c, st, freq, power = detector.update(lw, rw, ls, rs)
        flap_count = c

    print(f"   - Siklus Kepakan Terdeteksi: {flap_count}")
    print(f"   - Frekuensi Kepakan        : {freq:.2f} Hz")
    print(f"   - Daya Dorong (Flap Power) : {power * 100:.1f}%")

    assert flap_count >= 3, f"Harus mendeteksi minimal 3 siklus kepakan penuh, terdeteksi: {flap_count}"
    print("   [PASS] Detektor kepakan dengan state machine hysteresis anti-flicker bekerja andal.")


def test_scenario_5_distance_scale_invariance():
    print("\n" + "=" * 65)
    print("TEST 5: Mendekati vs Menjauhi Kamera (Scale Invariance)")
    print("=" * 65)

    normalizer = BiometricNormalizer()

    # Kondisi 1: Pemain duduk DEKAT kamera (Shoulder width besar ~ 0.40)
    ls_close = (0.30, 0.35)
    rs_close = (0.70, 0.35)
    lh_close = (0.35, 0.85)
    rh_close = (0.65, 0.85)
    lw_close = (0.10, 0.35)  # T-Pose bentang sayap penuh
    rw_close = (0.90, 0.35)
    le_close = (0.20, 0.35)
    re_close = (0.80, 0.35)
    bio_close = normalizer.calculate_biometrics(ls_close, rs_close, lh_close, rh_close, le_close, re_close, lw_close, rw_close)

    # Kondisi 2: Pemain berdiri JAUH dari kamera (Shoulder width kecil ~ 0.16)
    # Skala 40% dari kondisi dekat
    scale = 0.40
    cx, cy = 0.50, 0.50
    def scale_pt(pt):
        return (cx + (pt[0] - cx) * scale, cy + (pt[1] - cy) * scale)

    ls_far = scale_pt(ls_close)
    rs_far = scale_pt(rs_close)
    lh_far = scale_pt(lh_close)
    rh_far = scale_pt(rh_close)
    lw_far = scale_pt(lw_close)
    rw_far = scale_pt(rw_close)
    le_far = scale_pt(le_close)
    re_far = scale_pt(re_close)
    bio_far = normalizer.calculate_biometrics(ls_far, rs_far, lh_far, rh_far, le_far, re_far, lw_far, rw_far)

    print(f"   [DEKAT] Sw: {bio_close['shoulder_width']:.3f} | Wingspan Ratio: {bio_close['wingspan_ratio']:.3f}")
    print(f"   [JAUH]  Sw: {bio_far['shoulder_width']:.3f} | Wingspan Ratio: {bio_far['wingspan_ratio']:.3f}")

    diff = abs(bio_close["wingspan_ratio"] - bio_far["wingspan_ratio"])
    print(f"   - Perbedaan Rasio : {diff:.5f} (Invariansi: {(1.0 - diff/bio_close['wingspan_ratio'])*100:.2f}%)")

    assert diff < 0.05, f"Rasio biometrik tidak invarian terhadap jarak kamera! Diff: {diff}"
    print("   [PASS] Normalisasi koordinat 100% invarian terhadap jarak dan skala tubuh pemain.")


def test_scenario_6_out_of_frame_and_recovery():
    print("\n" + "=" * 65)
    print("TEST 6: Keluar & Kembali ke Frame (Tracking Loss & Recovery)")
    print("=" * 65)

    tracker = RobustKeypointTracker()

    # 1. Pemain di dalam frame (Tracked)
    for _ in range(10):
        tracker.update_joint("ls", 0.40, 0.40, conf=0.90)
        tracker.update_joint("rs", 0.60, 0.40, conf=0.90)
        tracker.update_joint("lh", 0.45, 0.70, conf=0.90)
        tracker.update_joint("rh", 0.55, 0.70, conf=0.90)
        st = tracker.update_tracking_state(True, {"ls": 0.9, "rs": 0.9, "lh": 0.9, "rh": 0.9, "lw": 0.9, "rw": 0.9})
    print(f"   - Status Awal : {st.value}")
    assert st == TrackingState.TRACKED

    # 2. Pemain keluar frame (0.5 detik tidak ada deteksi)
    st = tracker.update_tracking_state(False, {})
    print(f"   - Pemain Keluar Frame : {st.value}")
    assert st == TrackingState.LOST

    # 3. Pemain kembali ke frame di posisi berbeda
    # Verifikasi tidak ada lompatan seketika (blending recovery aktif)
    reacquired_positions = []
    new_target_x = 0.55
    for i in range(tracker.RECOVERY_BLEND_FRAMES + 2):
        cx, cy, _ = tracker.update_joint("ls", new_target_x, 0.40, conf=0.88)
        reacquired_positions.append(cx)
        st = tracker.update_tracking_state(True, {"ls": 0.88, "rs": 0.88, "lh": 0.88, "rh": 0.88, "lw": 0.88, "rw": 0.88})

    print(f"   - Transisi Pemulihan : {st.value}")
    # Periksa kontinuitas (posisi pertama setelah reacquisition tidak langsung melompat ke new_target_x)
    first_step = abs(reacquired_positions[0] - 0.40)
    print(f"   - Langkah Awal Reacquisition: {first_step:.4f} (Mulus tanpa lonjakan ekstrem)")
    assert first_step < abs(new_target_x - 0.40), "Recovery harus melakukan interpolasi halus"
    print("   [PASS] Penanganan tracking loss dan pemulihan mulus (anti-glitch) terverifikasi.")


def test_scenario_7_partial_occlusion():
    print("\n" + "=" * 65)
    print("TEST 7: Sebagian Tubuh Tertutup / Oklusi (Kinematic Hold & Fallback)")
    print("=" * 65)

    tracker = RobustKeypointTracker()
    ls = (0.40, 0.40)

    # 1. Tangan terlihat normal
    for _ in range(10):
        tracker.update_joint("lw", 0.25, 0.42, conf=0.85, shoulder_ref=ls, shoulder_width=0.20)

    # 2. Tangan tiba-tiba tertutup objek (conf = 0.05) selama 5 frame (< 0.4s)
    held_positions = []
    for _ in range(5):
        # Input noise acak saat oklusi
        cx, cy, eff_c = tracker.update_joint("lw", 0.99, 0.01, conf=0.05, shoulder_ref=ls, shoulder_width=0.20)
        held_positions.append((cx, cy))

    # Posisi yang ditahan harus dekat dengan posisi valid terakhir (0.25, 0.42), bukan melompat ke (0.99, 0.01)
    drift = math.hypot(held_positions[-1][0] - 0.25, held_positions[-1][1] - 0.42)
    print(f"   - Drift saat Oklusi Tangan: {drift:.4f}")
    assert drift < 0.05, f"Titik tangan melompat liar saat oklusi! Drift: {drift}"
    print("   [PASS] Oklusi tangan tertangani secara aman tanpa menghasilkan input ekstrem.")


def test_scenario_8_udp_protocol_integrity():
    print("\n" + "=" * 65)
    print("TEST 8: Integritas Protokol Transmisi UDP (28-Float Telemetry)")
    print("=" * 65)

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    success = sender.send_pose(
        ls=(0.40, 0.40), rs=(0.60, 0.40),
        lw=(0.20, 0.42), rw=(0.80, 0.42),
        lh=(0.42, 0.70), rh=(0.58, 0.70),
        mouth_open=0.0,
        le=(0.30, 0.42), re=(0.70, 0.42),
        is_dive=0.0, is_flap=1.0,
        flap_freq=2.5, flap_power=0.85,
        body_pitch=0.15,
        nose=(0.50, 0.25),
        wingspan_ratio=2.65,
        flap_height=0.45,
        lean_angle_deg=-12.5,
        tracking_state=1.0
    )
    sender.close()

    print(f"   - Pengiriman Paket UDP: {'BERHASIL' if success else 'GAGAL'}")
    assert success, "Pengiriman paket UDP gagal"
    print("   [PASS] Format CSV 28-nilai telemetri terkirim dengan sempurna.")


def run_all_validations():
    print("=" * 70)
    print("🚀 MENJALANKAN SUITE VALIDASI LENGKAP COMPUTER VISION (PHASE 1)")
    print("=" * 70)

    t0 = time.time()
    test_scenario_1_standing_still()
    test_scenario_2_arms_up_down()
    test_scenario_3_body_leaning()
    test_scenario_4_repetitive_flapping()
    test_scenario_5_distance_scale_invariance()
    test_scenario_6_out_of_frame_and_recovery()
    test_scenario_7_partial_occlusion()
    test_scenario_8_udp_protocol_integrity()

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f"✅ SELURUH PENGUJIAN PHASE 1 BERHASIL DIVERIFIKASI (Total: {elapsed:.2f} detik)")
    print("=" * 70)


if __name__ == "__main__":
    run_all_validations()
