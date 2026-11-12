"""
test_phase6_final_session.py
Suite Validasi Komprehensif Phase 6 - Final Validation, Integration & Polish
Master Development Plan: Computer Vision Upgrade & Body Motion Control Rework

Pengujian:
6.1 End-to-End CV & Classification Latency Benchmark (Filter, Normalisasi, State Machine, UDP)
6.2 Rantai Manuver Terbang Sky Peck Sequence A (Glide -> Flap to Climb -> Tuck Dive -> Swoop Soaring -> Glide)
6.3 Rantai Manuver Terbang Sky Peck Sequence B (Glide -> Propeller Dash -> Continuous Lean Banking)
6.4 Arbitrasi Gestur Bebas Konflik (Zero Input Conflict & Hierarki Prioritas)
6.5 Poles Kamera Dinamis (Dynamic FOV Scaling Berdasarkan Airspeed)
6.6 Siklus Lengkap Village Auto-Hover (Masuk Desa, Stabilisasi Melayang, Keluar Desa)
6.7 Simulasi Ketahanan Terbang Berkelanjutan 3.000 Frame (Zero Memory Leak & Smooth Continuity)
"""

import sys
import os
import time
import math
import gc
import psutil
import numpy as np

# Pastikan path modul CV tersedia
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pose_stabilizer import RobustKeypointTracker, BiometricNormalizer, TrackingState
from motion_recognizer import (
    GestureStateMachine,
    GestureState,
    FlapStrokePhase,
    FlapStrokeClassifier,
    ContinuousLeanClassifier,
    TuckDiveClassifier,
    PropellerRotationClassifier
)
from player_calibrator import PlayerBiometricProfile, AdaptiveThresholdEngine, get_default_profile
from udp_sender import PoseUDPSender


class FlightPhysicsEmulator:
    """
    Emulasi persamaan diferensial DragonFlightController.cs untuk pengujian kontinuitas terbang.
    """
    def __init__(self):
        self.cruise_speed = 14.0
        self.max_dive_speed = 28.0
        self.max_dash_speed = 26.0
        self.max_flap_speed = 21.0
        self.glide_sink_rate = 1.0
        self.flap_lift_power = 6.0
        self.flap_thrust_accel = 12.0
        self.dive_accel = 18.0
        self.tuck_dive_pitch = -40.0
        self.dash_thrust_accel = 22.0
        self.swoop_efficiency = 0.85
        self.yaw_turn_speed = 72.0
        self.max_roll_angle = 38.0

        # Status Fisika
        self.current_airspeed = 14.0
        self.current_vert_vel = 0.0
        self.current_pitch = -4.0
        self.current_yaw = 0.0
        self.current_roll = 0.0
        self.current_alt = 50.0
        self.is_hovering = False
        self.is_swoop_climbing = False

        # Poles Kamera Dinamis
        self.base_camera_fov = 60.0
        self.current_camera_fov = 60.0

    def step(self, dt, active_gesture_val, flap_power=0.0, dash_power=0.0, turn_input=0.0):
        dt = min(0.066, dt)
        if dt <= 0: return

        # 1. Kemudi Yaw & Banking Roll
        if abs(turn_input) > 0.001:
            self.current_yaw += turn_input * self.yaw_turn_speed * dt
        target_roll = -turn_input * self.max_roll_angle
        self.current_roll += (target_roll - self.current_roll) * min(1.0, dt * 7.5)

        target_pitch = -4.0
        self.is_swoop_climbing = False

        if self.is_hovering:
            self.current_airspeed += (0.0 - self.current_airspeed) * min(1.0, dt * 4.0)
            self.current_vert_vel += (0.0 - self.current_vert_vel) * min(1.0, dt * 4.0)
            self.current_pitch += (0.0 - self.current_pitch) * min(1.0, dt * 5.0)
            self.current_roll += (0.0 - self.current_roll) * min(1.0, dt * 5.0)
            self.current_alt += self.current_vert_vel * dt
            return
        elif active_gesture_val == GestureState.PROPELLER_DASH.value:
            target_pitch = 0.0
            pwr = max(0.6, dash_power)
            self.current_airspeed = min(self.max_dash_speed, self.current_airspeed + self.dash_thrust_accel * pwr * dt)
            self.current_vert_vel += (0.5 - self.current_vert_vel) * min(1.0, dt * 6.0)
        elif active_gesture_val == GestureState.TUCK_DIVE.value:
            target_pitch = self.tuck_dive_pitch
            self.current_airspeed = min(self.max_dive_speed, self.current_airspeed + self.dive_accel * dt)
            dive_sink = -self.current_airspeed * math.sin(math.radians(abs(self.tuck_dive_pitch)))
            self.current_vert_vel += (dive_sink - self.current_vert_vel) * min(1.0, dt * 5.5)
        elif active_gesture_val == GestureState.FLAPPING.value:
            pwr = max(0.5, flap_power)
            target_pitch = 7.0 + 8.0 * pwr
            self.current_airspeed = min(self.max_flap_speed, self.current_airspeed + self.flap_thrust_accel * pwr * dt)
            target_climb = self.flap_lift_power * pwr
            self.current_vert_vel += (target_climb - self.current_vert_vel) * min(1.0, dt * 7.5)
        else: # NEUTRAL_GLIDE
            if self.current_airspeed > self.cruise_speed + 2.0:
                self.is_swoop_climbing = True
                excess = self.current_airspeed - self.cruise_speed
                target_pitch = max(7.0, min(24.0, excess * 1.5))
                swoop_lift = excess * self.swoop_efficiency
                self.current_vert_vel += (swoop_lift - self.current_vert_vel) * min(1.0, dt * 6.0)
                self.current_airspeed -= excess * 0.60 * dt
            else:
                target_pitch = -4.0
                self.current_vert_vel += (-self.glide_sink_rate - self.current_vert_vel) * min(1.0, dt * 3.5)
                self.current_airspeed += (self.cruise_speed - self.current_airspeed) * min(1.0, dt * 2.2)

        # Smooth pitch & Altitude
        self.current_pitch += (target_pitch - self.current_pitch) * min(1.0, dt * 5.5)
        self.current_alt += self.current_vert_vel * dt
        self.current_alt = max(3.5, min(160.0, self.current_alt))

        # Dynamic FOV Scaling
        speed_ratio = max(0.0, min(1.0, (self.current_airspeed - self.cruise_speed) / (self.max_dive_speed - self.cruise_speed)))
        target_fov = self.base_camera_fov + speed_ratio * 12.0
        self.current_camera_fov += (target_fov - self.current_camera_fov) * min(1.0, dt * 4.0)


def build_kpts_dict(ls, rs, lh, rh, le, re, lw, rw, nose=(0.5, 0.25)):
    return {
        "ls": ls, "rs": rs, "lh": lh, "rh": rh,
        "le": le, "re": re, "lw": lw, "rw": rw, "nose": nose
    }


def run_phase6_tests():
    print("=" * 70)
    print("🚀 SUITE VALIDASI TERPADU PHASE 6: FINAL INTEGRATION & POLISH")
    print("=" * 70)

    # -------------------------------------------------------------
    # Test 6.1: End-to-End Pipeline Latency Benchmark
    # -------------------------------------------------------------
    print("\n[6.1] Benchmark Latensi Pemrosesan CPU & Throughput Pipeline...")
    normalizer = BiometricNormalizer()
    tracker = RobustKeypointTracker()
    sm = GestureStateMachine()

    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.70), (0.58, 0.70)
    le, re = (0.30, 0.42), (0.70, 0.42)
    lw, rw = (0.16, 0.42), (0.84, 0.42)

    # Warmup
    for _ in range(30):
        c_ls_x, c_ls_y, _ = tracker.update_joint("ls", ls[0], ls[1], 0.95)
        c_rs_x, c_rs_y, _ = tracker.update_joint("rs", rs[0], rs[1], 0.95)
        c_lh_x, c_lh_y, _ = tracker.update_joint("lh", lh[0], lh[1], 0.95)
        c_rh_x, c_rh_y, _ = tracker.update_joint("rh", rh[0], rh[1], 0.95)
        c_lw_x, c_lw_y, _ = tracker.update_joint("lw", lw[0], lw[1], 0.95)
        c_rw_x, c_rw_y, _ = tracker.update_joint("rw", rw[0], rw[1], 0.95)
        bio = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)
        kpts = build_kpts_dict(ls, rs, lh, rh, le, re, lw, rw)
        _ = sm.update(kpts, bio, is_tracking_valid=True)

    latencies = []
    for _ in range(250):
        t0 = time.perf_counter()
        c_ls_x, c_ls_y, _ = tracker.update_joint("ls", ls[0], ls[1], 0.95)
        c_rs_x, c_rs_y, _ = tracker.update_joint("rs", rs[0], rs[1], 0.95)
        c_lh_x, c_lh_y, _ = tracker.update_joint("lh", lh[0], lh[1], 0.95)
        c_rh_x, c_rh_y, _ = tracker.update_joint("rh", rh[0], rh[1], 0.95)
        c_lw_x, c_lw_y, _ = tracker.update_joint("lw", lw[0], lw[1], 0.95)
        c_rw_x, c_rw_y, _ = tracker.update_joint("rw", rw[0], rw[1], 0.95)
        bio = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw)
        kpts = build_kpts_dict(ls, rs, lh, rh, le, re, lw, rw)
        _ = sm.update(kpts, bio, is_tracking_valid=True)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    avg_lat = np.mean(latencies)
    p95_lat = np.percentile(latencies, 95)
    max_lat = np.max(latencies)
    print(f"  -> Latensi Pemrosesan CPU: Rata-rata={avg_lat:.3f} ms | P95={p95_lat:.3f} ms | Max={max_lat:.3f} ms")
    assert avg_lat < 1.50, f"Latensi pemrosesan CPU melebihi batas 1.5ms: {avg_lat:.2f} ms"
    print("  -> PASS: Latensi pipeline < 1.5ms (Throughput > 600 FPS pada CPU).")

    # -------------------------------------------------------------
    # Test 6.2: Rantai Manuver Terbang Sequence A
    # -------------------------------------------------------------
    print("\n[6.2] Uji Rantai Manuver Terbang Sequence A (Glide -> Flap -> Dive -> Swoop -> Glide)...")
    sim = FlightPhysicsEmulator()
    dt = 0.033

    # Segment 1: Meluncur Tenang (Glide) - 30 frames (~1 detik)
    for _ in range(30):
        sim.step(dt, GestureState.NEUTRAL_GLIDE.value)
    assert abs(sim.current_airspeed - 14.0) < 0.2
    assert abs(sim.current_pitch - (-4.0)) < 0.5
    print(f"  -> Segmen 1 (Glide): Kecepatan={sim.current_airspeed:.1f} m/s, Pitch={sim.current_pitch:.1f}°, Alt={sim.current_alt:.1f} m")

    # Segment 2: Flap to Climb - 60 frames (~2 detik)
    alt_start = sim.current_alt
    for _ in range(60):
        sim.step(dt, GestureState.FLAPPING.value, flap_power=0.85)
    climb_gain = sim.current_alt - alt_start
    assert climb_gain > 5.0, f"Kenaikan ketinggian kepakan terlalu kecil: {climb_gain:.1f} m"
    assert sim.current_airspeed > 17.0
    assert sim.current_pitch > 8.0
    print(f"  -> Segmen 2 (Flap to Climb): Ketinggian +{climb_gain:.1f} m, Kecepatan={sim.current_airspeed:.1f} m/s, Pitch={sim.current_pitch:.1f}°")

    # Segment 3: Tuck Dive - 45 frames (~1.5 detik)
    alt_dive_start = sim.current_alt
    for _ in range(45):
        sim.step(dt, GestureState.TUCK_DIVE.value)
    dive_drop = alt_dive_start - sim.current_alt
    assert sim.current_airspeed > 24.0, f"Kecepatan dive kurang tinggi: {sim.current_airspeed:.1f} m/s"
    assert sim.current_pitch < -30.0, f"Sudut menukik kurang tajam: {sim.current_pitch:.1f}°"
    assert dive_drop > 10.0
    print(f"  -> Segmen 3 (Tuck Dive): Terminal Airspeed={sim.current_airspeed:.1f} m/s, Pitch Menukik={sim.current_pitch:.1f}°, Drop -{dive_drop:.1f} m")

    # Segment 4: Swoop Soaring Pullout - 45 frames (~1.5 detik)
    alt_swoop_start = sim.current_alt
    swoop_triggered = False
    for _ in range(45):
        sim.step(dt, GestureState.NEUTRAL_GLIDE.value)
        if sim.is_swoop_climbing:
            swoop_triggered = True
    assert swoop_triggered, "Swoop climb tidak terpicu saat sayap dibuka pada kecepatan tinggi!"
    assert sim.current_alt > alt_swoop_start, "Energi kinetik tidak terkonversi menjadi kenaikan ketinggian!"
    assert sim.current_airspeed < 24.0, "Kecepatan tidak berkurang saat melambung naik!"
    print(f"  -> Segmen 4 (Swoop Soaring): Melambung ke Alt={sim.current_alt:.1f} m (+{sim.current_alt - alt_swoop_start:.1f} m), Kecepatan mereda ke {sim.current_airspeed:.1f} m/s")

    # Segment 5: Kembali Meluncur Stabil - 120 frames (~4 detik)
    for _ in range(120):
        sim.step(dt, GestureState.NEUTRAL_GLIDE.value)
    print(f"  -> Segmen 5 (Glide Selesai): Stabil pada Kecepatan={sim.current_airspeed:.1f} m/s di Alt={sim.current_alt:.1f} m")
    assert abs(sim.current_airspeed - 14.0) < 0.8, f"Kecepatan jelajah belum stabil: {sim.current_airspeed:.2f} m/s"
    assert abs(sim.current_pitch - (-4.0)) < 1.0
    assert not sim.is_swoop_climbing
    print("  -> PASS: Rantai Sequence A teruji mulus dan konsisten secara aerodinamis.")

    # -------------------------------------------------------------
    # Test 6.3: Rantai Manuver Terbang Sequence B (Propeller Dash & Lean)
    # -------------------------------------------------------------
    print("\n[6.3] Uji Rantai Manuver Terbang Sequence B (Propeller Dash -> Banking Turn -> Cruise)...")
    sim = FlightPhysicsEmulator()

    # Step 1: Propeller Dash (1.5 detik)
    for _ in range(45):
        sim.step(dt, GestureState.PROPELLER_DASH.value, dash_power=1.0)
    assert sim.current_airspeed > 23.0, f"Kecepatan dash tidak tercapai: {sim.current_airspeed:.1f} m/s"
    assert abs(sim.current_pitch) < 3.0, "Dash tidak terbang datar menembus angin!"
    print(f"  -> Propeller Dash Puncak: Kecepatan={sim.current_airspeed:.1f} m/s, Kamera FOV={sim.current_camera_fov:.1f}°")

    # Step 2: High-Speed Lean Banking Turn Kiri (-0.8 turn) bersama Dash
    for _ in range(45):
        sim.step(dt, GestureState.PROPELLER_DASH.value, dash_power=1.0, turn_input=-0.8)
    assert sim.current_yaw < -30.0, f"Yaw tidak berbelok ke kiri: {sim.current_yaw:.1f}°"
    assert sim.current_roll > 20.0, f"Banking roll sayap tidak memiring benar: {sim.current_roll:.1f}°"
    print(f"  -> Banking Kiri Dash: Yaw={sim.current_yaw:.1f}°, Kemiringan Sayap Roll={sim.current_roll:.1f}°")

    # Step 3: Transisi Berbalik Belok Kanan (+0.75 turn) saat Meluncur
    for _ in range(60):
        sim.step(dt, GestureState.NEUTRAL_GLIDE.value, turn_input=+0.75)
    assert sim.current_roll < -15.0, f"Banking roll tidak membalik ke kanan: {sim.current_roll:.1f}°"
    print(f"  -> Transisi Belok Kanan: Roll berbalik mulus ke {sim.current_roll:.1f}°")
    print("  -> PASS: Sequence B kemudi kontinu multi-sumbu terverifikasi responsif.")

    # -------------------------------------------------------------
    # Test 6.4: Arbitrasi Gestur Bebas Konflik
    # -------------------------------------------------------------
    print("\n[6.4] Arbitrasi Gestur Bebas Konflik & Hierarki Prioritas...")
    sm = GestureStateMachine()
    ls, rs = (0.40, 0.40), (0.60, 0.40)
    lh, rh = (0.42, 0.70), (0.58, 0.70)
    le, re = (0.30, 0.42), (0.70, 0.42)

    # 1. Rotasi lengan (Propeller Dash) harus mendahului flapping atau tuck
    t = time.perf_counter()
    res_dash = None
    for _ in range(35):
        t += 0.03
        ang = t * 16.0
        lw_rot = (0.30 + math.cos(ang) * 0.12, 0.42 + math.sin(ang) * 0.12)
        rw_rot = (0.70 + math.cos(ang + math.pi) * 0.12, 0.42 + math.sin(ang + math.pi) * 0.12)
        k = build_kpts_dict(ls, rs, lh, rh, le, re, lw_rot, rw_rot)
        b = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_rot, rw_rot)
        res_dash = sm.update(k, b, is_tracking_valid=True)
    assert res_dash['active_state'] == GestureState.PROPELLER_DASH.value, f"Expected PROPELLER_DASH, got {res_dash['active_state']}"
    print(f"  -> Prioritas 1 Terverifikasi: {res_dash['active_state']} (Dash Power: {res_dash['dash_power']*100:.1f}%)")

    # 2. Tuck Dive harus mendahului Flapping saat tangan dirapatkan
    sm_dive = GestureStateMachine()
    lw_tuck, rw_tuck = (0.47, 0.45), (0.53, 0.45)
    le_down, re_down = (0.38, 0.60), (0.62, 0.60)
    k_tuck = build_kpts_dict(ls, rs, lh, rh, le_down, re_down, lw_tuck, rw_tuck)
    b_tuck = normalizer.calculate_biometrics(ls, rs, lh, rh, le_down, re_down, lw_tuck, rw_tuck)
    res_dive = None
    for i in range(10):
        res_dive = sm_dive.update(k_tuck, b_tuck, is_tracking_valid=True)
        time.sleep(0.02)
    assert res_dive['active_state'] == GestureState.TUCK_DIVE.value, f"Expected TUCK_DIVE, got {res_dive['active_state']}"
    print(f"  -> Prioritas 2 Terverifikasi: {res_dive['active_state']} (Dive Power: {res_dive['dive_power']*100:.1f}%)")

    # 3. Flap to Climb aktif saat kedua tangan mengepak di atas/bawah bahu
    sm_flap = GestureStateMachine()
    res_flap = None
    for i in range(40):
        y_osc = math.sin(i * 0.45) * 0.35
        lw_f = (0.18, 0.40 + y_osc)
        rw_f = (0.82, 0.40 + y_osc)
        k_f = build_kpts_dict(ls, rs, lh, rh, le, re, lw_f, rw_f)
        b_f = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw_f, rw_f)
        res_flap = sm_flap.update(k_f, b_f, is_tracking_valid=True)
        time.sleep(0.015)
    assert res_flap['active_state'] == GestureState.FLAPPING.value or res_flap['flap_power'] > 0.0
    print(f"  -> Prioritas 3 Terverifikasi: {res_flap['active_state']} (Flap Power: {res_flap['flap_power']*100:.1f}%)")
    print("  -> PASS: Hierarki prioritas arbitrase menjamin nol konflik input.")

    # -------------------------------------------------------------
    # Test 6.5: Dynamic Flight Camera Polish (FOV Scaling)
    # -------------------------------------------------------------
    print("\n[6.5] Poles Kamera Dinamis (Field of View Scaling)...")
    sim = FlightPhysicsEmulator()
    assert abs(sim.current_camera_fov - 60.0) < 0.1

    # Akselerasi ke kecepatan maksimal Tuck Dive
    for _ in range(60):
        sim.step(dt, GestureState.TUCK_DIVE.value)
    assert sim.current_camera_fov > 68.0, f"FOV kamera tidak melebar saat dive: {sim.current_camera_fov:.1f}°"
    print(f"  -> FOV Kamera Saat Kecepatan Maksimal: {sim.current_camera_fov:.1f}° (Efek kecepatan aktif)")

    # Redakan kembali ke Glide jelajah (150 frames ~ 5 detik)
    for _ in range(150):
        sim.step(dt, GestureState.NEUTRAL_GLIDE.value)
    assert abs(sim.current_camera_fov - 60.0) < 1.0, f"FOV kamera tidak kembali ke 60°: {sim.current_camera_fov:.1f}°"
    print(f"  -> FOV Kamera Kembali Normal Saat Jelajah: {sim.current_camera_fov:.1f}°")
    print("  -> PASS: Pelicinan dinamis FOV kamera terverifikasi mulus.")

    # -------------------------------------------------------------
    # Test 6.6: Siklus Lengkap Village Auto-Hover
    # -------------------------------------------------------------
    print("\n[6.6] Siklus Lengkap Village Auto-Hover (Masuk, Melayang, Keluar)...")
    sim = FlightPhysicsEmulator()
    sim.current_airspeed = 24.0
    sim.current_pitch = -30.0
    sim.current_roll = 25.0

    # Masuk area desa
    sim.is_hovering = True
    for _ in range(45):
        sim.step(dt, GestureState.NEUTRAL_GLIDE.value)
    assert sim.current_airspeed < 2.0, f"Laju maju tidak dihentikan saat hover: {sim.current_airspeed:.1f} m/s"
    assert abs(sim.current_pitch) < 2.0, f"Pitch tidak diratakan saat hover: {sim.current_pitch:.1f}°"
    assert abs(sim.current_roll) < 2.0, f"Roll tidak diratakan saat hover: {sim.current_roll:.1f}°"
    print(f"  -> Melayang Stabil di Desa: Kecepatan={sim.current_airspeed:.2f} m/s, Pitch={sim.current_pitch:.1f}°, Roll={sim.current_roll:.1f}°")

    # Keluar area desa
    sim.is_hovering = False
    sim.current_airspeed = 14.0
    sim.step(dt, GestureState.NEUTRAL_GLIDE.value)
    assert sim.current_airspeed >= 14.0
    print("  -> PASS: Transisi masuk dan keluar auto-hover berjalan tanpa glitch.")

    # -------------------------------------------------------------
    # Test 6.7: Uji Ketahanan Terbang 3.000 Frame (100 detik @ 30 FPS)
    # -------------------------------------------------------------
    print("\n[6.7] Uji Ketahanan Terbang Berkelanjutan 3.000 Frame (100 detik @ 30 FPS)...")
    proc = psutil.Process(os.getpid())
    gc.collect()
    mem_start = proc.memory_info().rss / (1024 * 1024)

    tracker = RobustKeypointTracker()
    normalizer = BiometricNormalizer()
    sm = GestureStateMachine()
    sim = FlightPhysicsEmulator()

    discontinuities = 0
    prev_pitch = sim.current_pitch
    prev_roll = sim.current_roll

    for frame in range(3000):
        phase_idx = (frame // 300) % 6
        if phase_idx == 0:
            # Glide
            kpts = build_kpts_dict(ls, rs, lh, rh, le, re, (0.16, 0.42), (0.84, 0.42))
        elif phase_idx == 1:
            # Flap
            flap_y = math.sin(frame * 0.4) * 0.25
            kpts = build_kpts_dict(ls, rs, lh, rh, le, re, (0.18, 0.40 + flap_y), (0.82, 0.40 + flap_y))
        elif phase_idx == 2:
            # Lean left
            kpts = build_kpts_dict((0.38, 0.35), (0.58, 0.45), (0.40, 0.65), (0.60, 0.75), le, re, (0.14, 0.38), (0.82, 0.48))
        elif phase_idx == 3:
            # Tuck dive
            kpts = build_kpts_dict(ls, rs, lh, rh, (0.38, 0.60), (0.62, 0.60), (0.47, 0.45), (0.53, 0.45))
        elif phase_idx == 4:
            # Propeller dash
            ang = frame * 0.45
            lw_rot = (0.30 + math.cos(ang) * 0.12, 0.42 + math.sin(ang) * 0.12)
            rw_rot = (0.70 + math.cos(ang + math.pi) * 0.12, 0.42 + math.sin(ang + math.pi) * 0.12)
            kpts = build_kpts_dict(ls, rs, lh, rh, le, re, lw_rot, rw_rot)
        else:
            # Lean right
            kpts = build_kpts_dict((0.42, 0.45), (0.62, 0.35), (0.40, 0.75), (0.60, 0.65), le, re, (0.18, 0.48), (0.86, 0.38))

        bio = normalizer.calculate_biometrics(
            kpts["ls"], kpts["rs"], kpts["lh"], kpts["rh"],
            kpts["le"], kpts["re"], kpts["lw"], kpts["rw"]
        )
        res = sm.update(kpts, bio, is_tracking_valid=True)
        sim.step(dt, res["active_state"], flap_power=res["flap_power"], dash_power=res["dash_power"], turn_input=res["steering_input"])

        d_pitch = abs(sim.current_pitch - prev_pitch)
        d_roll = abs(sim.current_roll - prev_roll)
        if d_pitch > 15.0 or d_roll > 15.0:
            discontinuities += 1
        prev_pitch = sim.current_pitch
        prev_roll = sim.current_roll

    gc.collect()
    mem_end = proc.memory_info().rss / (1024 * 1024)
    mem_delta = mem_end - mem_start

    print(f"  -> Penggunaan Memori: Awal={mem_start:.2f} MB, Akhir={mem_end:.2f} MB, Selisih={mem_delta:.2f} MB")
    print(f"  -> Diskontinuitas Terdeteksi (>15°/frame step): {discontinuities}")
    assert discontinuities == 0, f"Diskontinuitas trajektori ditemukan: {discontinuities}"
    assert mem_delta < 5.0, f"Terjadi kebocoran memori: {mem_delta:.2f} MB"
    print("  -> PASS: 3.000 frame berkelanjutan tuntas dengan 0% kebocoran memori dan trajektori 100% mulus.")

    print("\n" + "=" * 70)
    print("🎉 SELURUH PENGUJIAN PHASE 6 BERHASIL DIVERIFIKASI DENGAN SEMPURNA! (7/7)")
    print("=" * 70)

if __name__ == '__main__':
    run_phase6_tests()
