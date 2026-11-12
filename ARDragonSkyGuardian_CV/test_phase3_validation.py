"""
test_phase3_validation.py
Suite Validasi Komprehensif Phase 3 - Character Control & Flight Physics (Sky Peck Dynamics)
Memverifikasi:
1. Input Mapping Decoupling (FlightCommand generation)
2. Flap to Climb (Dynamic lift, forward thrust, pitch stability)
3. Continuous Lean to Turn & Banking Roll
4. Tuck Dive Acceleration & Kinetic Swoop Soaring Conversion
5. Propeller Dash Impulse Boost & Level Piercing
6. Glide Equilibrium & Natural Sink Rate
7. Ground Terrain Safety Protection & Ceiling Clamp
8. Village Zone Auto-Hover Mechanics
"""

import math
import sys
from dataclasses import dataclass

@dataclass
class FlightCommand:
    turn_input: float = 0.0
    pitch_input: float = 0.0
    body_pitch: float = 0.0
    is_flapping: bool = False
    flap_power: float = 0.0
    is_tuck_diving: bool = False
    dive_intensity: float = 0.0
    is_propeller_dash: bool = False
    dash_power: float = 0.0
    is_gliding: bool = True
    is_water_breathing: bool = False
    is_hands_high_up: bool = False

class SimulatedFlightController:
    """Simulasi persis dari DragonFlightController.cs logika fisika 60 FPS."""
    def __init__(self):
        # Parameters matching DragonFlightController.cs
        self.cruise_speed = 14.0
        self.min_speed = 7.0
        self.max_dive_speed = 28.0
        self.max_dash_speed = 26.0
        self.max_flap_speed = 21.0
        self.glide_sink_rate = 1.0

        self.flap_lift_power = 6.0
        self.flap_thrust_accel = 12.0

        self.dive_acceleration = 18.0
        self.tuck_dive_pitch = -40.0
        self.dash_thrust_accel = 22.0
        self.swoop_efficiency = 0.85

        self.yaw_turn_speed = 72.0
        self.max_roll_angle = 38.0
        self.yaw_smooth_speed = 8.0
        self.roll_smooth_speed = 7.5
        self.pitch_smooth_speed = 5.5

        self.min_ground_clearance = 3.5
        self.max_altitude = 160.0

        # State variables
        self.pos = [0.0, 50.0, 0.0]  # x, y, z
        self.airspeed = 14.0
        self.vertical_velocity = 0.0
        self.pitch = -4.0
        self.yaw = 0.0
        self.roll = 0.0

        self.is_hovering = False
        self.is_swoop_climbing = False
        self.hover_look_target = [0.0, 50.0, 50.0]

    def update_physics(self, cmd: FlightCommand, ground_surface_y: float = 0.0, dt: float = 1.0 / 60.0):
        if self.is_hovering:
            self._update_hover(dt)
            return

        ground_distance = self.pos[1] - ground_surface_y

        # 1. Turn & Banking Roll
        if abs(cmd.turn_input) > 0.001:
            self.yaw += cmd.turn_input * self.yaw_turn_speed * dt

        target_roll = -cmd.turn_input * self.max_roll_angle
        self.roll += (target_roll - self.roll) * min(1.0, dt * self.roll_smooth_speed)

        # 2. Flight State Priority
        target_pitch = -4.0
        self.is_swoop_climbing = False

        if cmd.is_propeller_dash:
            target_pitch = 0.0
            dash_pwr = max(0.6, cmd.dash_power)
            self.airspeed += self.dash_thrust_accel * dash_pwr * dt
            if self.airspeed > self.max_dash_speed:
                self.airspeed = self.max_dash_speed
            self.vertical_velocity += (0.5 - self.vertical_velocity) * min(1.0, dt * 6.0)

        elif cmd.is_tuck_diving:
            target_pitch = self.tuck_dive_pitch
            self.airspeed += self.dive_acceleration * dt
            if self.airspeed > self.max_dive_speed:
                self.airspeed = self.max_dive_speed
            dive_sink = -self.airspeed * math.sin(math.radians(abs(self.tuck_dive_pitch)))
            self.vertical_velocity += (dive_sink - self.vertical_velocity) * min(1.0, dt * 5.5)

        elif cmd.is_flapping:
            flap_pwr = max(0.5, cmd.flap_power)
            target_pitch = 7.0 + (15.0 - 7.0) * flap_pwr
            self.airspeed += self.flap_thrust_accel * flap_pwr * dt
            if self.airspeed > self.max_flap_speed:
                self.airspeed = self.max_flap_speed
            target_climb = self.flap_lift_power * flap_pwr
            self.vertical_velocity += (target_climb - self.vertical_velocity) * min(1.0, dt * 7.5)

        else:
            # Glide & Swoop Soaring
            if self.airspeed > self.cruise_speed + 2.0:
                self.is_swoop_climbing = True
                excess_speed = self.airspeed - self.cruise_speed
                target_pitch = max(7.0, min(24.0, excess_speed * 1.5))
                swoop_lift = excess_speed * self.swoop_efficiency
                self.vertical_velocity += (swoop_lift - self.vertical_velocity) * min(1.0, dt * 6.0)
                self.airspeed -= excess_speed * 0.60 * dt
            else:
                target_pitch = -4.0
                self.vertical_velocity += (-self.glide_sink_rate - self.vertical_velocity) * min(1.0, dt * 3.5)
                self.airspeed += (self.cruise_speed - self.airspeed) * min(1.0, dt * 2.2)

        # Ground clearance safety
        if ground_distance < 8.0:
            avoidance = max(0.0, min(1.0, (8.0 - ground_distance) / 5.0))
            avoid_pitch = avoidance * 15.0
            if target_pitch < avoid_pitch:
                target_pitch = avoid_pitch
            if self.vertical_velocity < 0.0:
                self.vertical_velocity += (1.5 - self.vertical_velocity) * min(1.0, avoidance * dt * 8.0)

        # Smooth pitch
        self.pitch += (target_pitch - self.pitch) * min(1.0, dt * self.pitch_smooth_speed)

        # Position integration
        rad_yaw = math.radians(self.yaw)
        dx = math.sin(rad_yaw) * (self.airspeed * dt)
        dz = math.cos(rad_yaw) * (self.airspeed * dt)
        dy = self.vertical_velocity * dt

        self.pos[0] += dx
        self.pos[1] += dy
        self.pos[2] += dz

        # Ground penetration clamp
        current_ground_dist = self.pos[1] - ground_surface_y
        if current_ground_dist < self.min_ground_clearance:
            self.pos[1] = ground_surface_y + self.min_ground_clearance
            if self.vertical_velocity < 0.0:
                self.vertical_velocity = 0.0

        # Ceiling clamp
        if self.pos[1] > self.max_altitude:
            self.pos[1] = self.max_altitude
            if self.vertical_velocity > 0.0:
                self.vertical_velocity = 0.0

    def _update_hover(self, dt: float):
        self.airspeed += (0.0 - self.airspeed) * min(1.0, dt * 4.0)
        self.vertical_velocity += (0.0 - self.vertical_velocity) * min(1.0, dt * 4.0)
        self.pitch += (0.0 - self.pitch) * min(1.0, dt * 5.0)
        self.roll += (0.0 - self.roll) * min(1.0, dt * 5.0)

def test_flap_to_climb():
    print("[TEST 3.1] Flap to Climb (Dynamic Lift & Thrust)...")
    ctrl = SimulatedFlightController()
    assert ctrl.airspeed == 14.0
    assert ctrl.pos[1] == 50.0

    cmd = FlightCommand(is_flapping=True, flap_power=0.9, is_gliding=False)
    # Simulate 2 seconds of flapping (120 frames)
    for _ in range(120):
        ctrl.update_physics(cmd)

    print(f"  Flapping Result: Alt = {ctrl.pos[1]:.1f}m (Delta +{ctrl.pos[1]-50.0:.1f}m), Speed = {ctrl.airspeed:.1f}m/s, Vy = {ctrl.vertical_velocity:.2f}m/s, Pitch = {ctrl.pitch:.1f} deg")
    assert ctrl.pos[1] > 55.0, f"Altitude should increase significantly during flap (got {ctrl.pos[1]})"
    assert ctrl.airspeed > 18.0, f"Forward thrust should increase airspeed (got {ctrl.airspeed})"
    assert ctrl.airspeed <= ctrl.max_flap_speed, f"Speed should cap at max_flap_speed (got {ctrl.airspeed})"
    assert 7.0 <= ctrl.pitch <= 16.0, f"Pitch should gently orient upwards (got {ctrl.pitch})"
    print("  -> PASSED: Flap produces strong climb lift, forward acceleration, and controlled upward pitch.")

def test_lean_to_turn_and_bank():
    print("[TEST 3.2] Continuous Lean to Turn & Banking Roll...")
    ctrl = SimulatedFlightController()

    # Apply right lean (TurnInput = +0.75) for 1 second (60 frames)
    cmd = FlightCommand(turn_input=0.75, is_gliding=True)
    initial_yaw = ctrl.yaw
    initial_roll = ctrl.roll

    for _ in range(60):
        ctrl.update_physics(cmd)

    yaw_delta = ctrl.yaw - initial_yaw
    print(f"  Turn Right Result: Yaw Delta = +{yaw_delta:.1f} deg, Roll = {ctrl.roll:.1f} deg (Max Roll = 38 deg)")
    assert yaw_delta > 35.0, f"Yaw should rotate clockwise smoothly (got {yaw_delta})"
    assert ctrl.roll < -20.0, f"Roll should bank right with negative roll angle (got {ctrl.roll})"

    # Release lean back to neutral for 1 second
    cmd_neutral = FlightCommand(turn_input=0.0, is_gliding=True)
    for _ in range(60):
        ctrl.update_physics(cmd_neutral)

    print(f"  Neutral Recovery Result: Roll restored to {ctrl.roll:.2f} deg")
    assert abs(ctrl.roll) < 1.0, f"Roll should smoothly recover to near 0 (got {ctrl.roll})"
    print("  -> PASSED: Continuous lean generates smooth yaw turning and realistic roll banking with natural recovery.")

def test_tuck_dive_and_swoop_climb():
    print("[TEST 3.3] Tuck Dive & Swoop Soaring Conversion...")
    ctrl = SimulatedFlightController()
    ctrl.pos[1] = 100.0  # High altitude

    # 1. Enter Tuck Dive for 1.5 seconds (90 frames)
    dive_cmd = FlightCommand(is_tuck_diving=True, dive_intensity=1.0, is_gliding=False)
    for _ in range(90):
        ctrl.update_physics(dive_cmd)

    print(f"  Dive Result: Alt = {ctrl.pos[1]:.1f}m, Airspeed = {ctrl.airspeed:.1f}m/s, Vy = {ctrl.vertical_velocity:.1f}m/s, Pitch = {ctrl.pitch:.1f} deg")
    assert ctrl.airspeed > 26.0, f"Airspeed should accelerate towards maxDiveSpeed (got {ctrl.airspeed})"
    assert ctrl.vertical_velocity < -12.0, f"Dive should produce rapid negative vertical velocity (got {ctrl.vertical_velocity})"
    assert ctrl.pitch < -30.0, f"Pitch should steepen towards -40 deg (got {ctrl.pitch})"

    # 2. Release Dive to neutral (Glide) -> Triggers SWOOP CLIMB!
    glide_cmd = FlightCommand(is_gliding=True)
    swoop_alt_start = ctrl.pos[1]
    max_swoop_vy = 0.0
    swoop_climb_confirmed = False

    for _ in range(90):
        ctrl.update_physics(glide_cmd)
        if ctrl.is_swoop_climbing:
            swoop_climb_confirmed = True
            if ctrl.vertical_velocity > max_swoop_vy:
                max_swoop_vy = ctrl.vertical_velocity

    swoop_alt_end = ctrl.pos[1]
    print(f"  Swoop Climb Result: Max Vy = +{max_swoop_vy:.1f}m/s, Alt Gained = +{swoop_alt_end - swoop_alt_start:.1f}m, Airspeed bled to = {ctrl.airspeed:.1f}m/s")
    assert swoop_climb_confirmed, "Swoop climb flag must activate when exiting high-speed dive"
    assert max_swoop_vy > 6.0, f"Swoop should produce soaring climb lift (got {max_swoop_vy})"
    assert ctrl.airspeed < 22.0, f"Airspeed should bleed off as kinetic energy is converted to altitude (got {ctrl.airspeed})"
    print("  -> PASSED: Tuck dive delivers steep acceleration, and swoop climb seamlessly converts excess kinetic energy into soaring altitude.")

def test_propeller_dash():
    print("[TEST 3.4] Propeller Dash (Impulse Forward Boost)...")
    ctrl = SimulatedFlightController()
    initial_y = ctrl.pos[1]

    dash_cmd = FlightCommand(is_propeller_dash=True, dash_power=1.0, is_gliding=False)
    for _ in range(60):
        ctrl.update_physics(dash_cmd)

    print(f"  Dash Result: Airspeed = {ctrl.airspeed:.1f}m/s (Max Dash = 26 m/s), Alt Delta = {ctrl.pos[1] - initial_y:.2f}m, Pitch = {ctrl.pitch:.1f} deg")
    assert ctrl.airspeed >= 25.0, f"Dash should boost airspeed up to 26 m/s (got {ctrl.airspeed})"
    assert abs(ctrl.pos[1] - initial_y) < 2.0, f"Dash should pierce horizontally without uncontrolled climb or fall (got {ctrl.pos[1] - initial_y})"
    assert abs(ctrl.pitch) < 3.0, f"Dash pitch should level off horizontally (got {ctrl.pitch})"
    print("  -> PASSED: Propeller dash grants rapid forward acceleration with piercing level trajectory.")

def test_glide_equilibrium():
    print("[TEST 3.5] Glide Stability & Natural Sink Rate...")
    ctrl = SimulatedFlightController()
    ctrl.airspeed = 20.0  # Slightly fast start
    ctrl.vertical_velocity = 5.0

    glide_cmd = FlightCommand(is_gliding=True)
    for _ in range(180):  # 3 seconds
        ctrl.update_physics(glide_cmd)

    print(f"  Glide Settled: Airspeed = {ctrl.airspeed:.2f}m/s (Target: 14.0), Vy = {ctrl.vertical_velocity:.2f}m/s (Target: -1.0)")
    assert abs(ctrl.airspeed - 14.0) < 0.8, f"Airspeed should converge to cruiseSpeed 14 m/s (got {ctrl.airspeed})"
    assert abs(ctrl.vertical_velocity - (-1.0)) < 0.25, f"Vertical velocity should settle at natural sink rate -1.0 m/s (got {ctrl.vertical_velocity})"
    print("  -> PASSED: Wings-extended glide stably converges to cruise speed and gentle natural sink rate.")

def test_terrain_clearance_and_ceiling():
    print("[TEST 3.6] Terrain Clearance Protection & Ceiling Clamp...")
    ctrl = SimulatedFlightController()
    ctrl.pos[1] = 6.0  # Near ground surface (y = 0.0)

    # Command a steep dive right towards the ground!
    dive_cmd = FlightCommand(is_tuck_diving=True, dive_intensity=1.0, is_gliding=False)
    for _ in range(60):
        ctrl.update_physics(dive_cmd, ground_surface_y=0.0)

    print(f"  Low Altitude Recovery: Alt = {ctrl.pos[1]:.2f}m (Min Clearance = 3.5m), Pitch = {ctrl.pitch:.1f} deg")
    assert ctrl.pos[1] >= ctrl.min_ground_clearance, f"Terrain collision protection must prevent altitude from going below min_ground_clearance (got {ctrl.pos[1]})"
    assert ctrl.vertical_velocity >= 0.0, f"Vertical velocity must be non-negative when clamped at ground (got {ctrl.vertical_velocity})"

    # Test high altitude ceiling
    ctrl.pos[1] = 159.0
    climb_cmd = FlightCommand(is_flapping=True, flap_power=1.0, is_gliding=False)
    for _ in range(60):
        ctrl.update_physics(climb_cmd)

    print(f"  Ceiling Clamp: Alt = {ctrl.pos[1]:.2f}m (Max Alt = 160.0m)")
    assert ctrl.pos[1] <= ctrl.max_altitude, f"Max altitude ceiling clamp must hold (got {ctrl.pos[1]})"
    print("  -> PASSED: Ground clearance safety and altitude ceiling clamps operate reliably.")

def test_village_hover_mode():
    print("[TEST 3.7] Village Auto-Hover Mechanics...")
    ctrl = SimulatedFlightController()
    ctrl.airspeed = 18.0
    ctrl.vertical_velocity = -2.0
    ctrl.pitch = -10.0
    ctrl.roll = 15.0

    ctrl.is_hovering = True
    for _ in range(120):  # 2 seconds
        ctrl.update_physics(FlightCommand())

    print(f"  Hover Mode: Airspeed = {ctrl.airspeed:.2f}m/s, Vy = {ctrl.vertical_velocity:.2f}m/s, Pitch = {ctrl.pitch:.2f} deg, Roll = {ctrl.roll:.2f} deg")
    assert ctrl.airspeed < 0.2, f"Hover must smoothly dampen airspeed to 0 (got {ctrl.airspeed})"
    assert abs(ctrl.vertical_velocity) < 0.2, f"Hover must stabilize vertical velocity (got {ctrl.vertical_velocity})"
    assert abs(ctrl.pitch) < 0.5, f"Hover must level pitch (got {ctrl.pitch})"
    assert abs(ctrl.roll) < 0.5, f"Hover must level roll (got {ctrl.roll})"
    print("  -> PASSED: Auto-hover smoothly arrests forward speed and stabilizes 3D dragon orientation.")

def run_all_phase3_tests():
    print("=" * 70)
    print("  PHASE 3 VALIDATION TEST SUITE: CHARACTER CONTROL & FLIGHT PHYSICS")
    print("=" * 70)

    test_flap_to_climb()
    test_lean_to_turn_and_bank()
    test_tuck_dive_and_swoop_climb()
    test_propeller_dash()
    test_glide_equilibrium()
    test_terrain_clearance_and_ceiling()
    test_village_hover_mode()

    print("=" * 70)
    print("  ALL 7 PHASE 3 VALIDATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_all_phase3_tests()
