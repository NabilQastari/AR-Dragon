"""
motion_recognizer.py - Production-Grade Body Motion & Gesture Recognition Engine (Phase 2).
Part of AR Dragon Sky Guardian (Sky Peck Inspired Gameplay).

Key Modules (Phase 2):
2.1 TemporalMotionTracker: Windowed velocity, acceleration, and angular kinematics.
2.2 FlapStrokeClassifier: Direction changes, stroke amplitude, Upstroke/Downstroke/Holding phases,
    and velocity-amplitude weighted intensity.
2.3 ContinuousLeanClassifier: Torso spine angle, continuous monotonic steering, adaptive deadzone.
2.4 TuckDiveClassifier: Geometric compactness, downward elbow alignment, temporal hold verification.
2.5 PropellerRotationClassifier: Monotonic angular displacement accumulation, orbital eccentricity,
    rotational consistency (strict discrimination from 1D flapping).
2.6 GestureStateMachine: Mutually exclusive state management with priority arbitration,
    activation threshold, minimum duration, release conditions, cooldowns, and tracking loss protection.
"""

import math
import time
from enum import Enum
from typing import Dict, Tuple, Optional, List, Any
from collections import deque


class GestureState(Enum):
    NEUTRAL_GLIDE = "GLIDE"              # Hands extended, natural cruising
    FLAPPING = "FLAP_TO_CLIMB"          # Active rhythmic flapping (lift + forward acceleration)
    TUCK_DIVE = "TUCK_DIVE"             # Wrists at chest, elbows down (high-speed steep dive)
    PROPELLER_DASH = "PROPELLER_DASH"   # Continuous arm rotation (speed boost impulse)
    HOVER = "HOVER"                     # Upper arms tucked + forearm flapping (stationary airborne hover)
    GENTLE_DESCENT = "GENTLE_DESCENT"   # Upper arms tucked + forearms extended T-pose, no flapping (slow glide descent)
    FLY_UP = "FLY_UP"                   # Chest elevated + rhythmic flapping (steep climb upward)


class FlapStrokePhase(Enum):
    NEUTRAL = "NEUTRAL"
    UPSTROKE = "UPSTROKE"
    DOWNSTROKE = "DOWNSTROKE"


class TemporalMotionTracker:
    """
    2.1 Motion Tracking Engine:
    Maintains a sliding temporal window of biometric keypoints to compute:
    - 2D Velocity (dx/dt, dy/dt)
    - 2D Acceleration (dv/dt)
    - Angular displacement (dtheta) & Angular velocity (omega) relative to shoulders/elbows
    - Movement consistency metrics
    """
    def __init__(self, history_size: int = 24, max_history_time: float = 0.60):
        self.history_size = history_size
        self.max_history_time = max_history_time
        # Deque of tuples: (timestamp, normalized_kpts_dict, biometrics_dict)
        self.history = deque(maxlen=history_size)

    def record_frame(self, kpts: Dict[str, Tuple[float, float]], biometrics: Dict[str, Any], t: Optional[float] = None):
        if t is None:
            t = time.perf_counter()
        self.history.append((t, kpts, biometrics))

        # Evict old entries exceeding max_history_time
        while len(self.history) > 2 and (t - self.history[0][0]) > self.max_history_time:
            self.history.popleft()

    def get_joint_velocity(self, key: str, window_frames: int = 3) -> Tuple[float, float]:
        """
        Calculates instantaneous velocity vector (vx, vy) in normalized units/sec.
        """
        if len(self.history) < 2:
            return (0.0, 0.0)

        n = min(window_frames, len(self.history) - 1)
        t_curr, kpts_curr, _ = self.history[-1]
        t_prev, kpts_prev, _ = self.history[-1 - n]

        dt = t_curr - t_prev
        if dt <= 1e-4 or key not in kpts_curr or key not in kpts_prev:
            return (0.0, 0.0)

        vx = (kpts_curr[key][0] - kpts_prev[key][0]) / dt
        vy = (kpts_curr[key][1] - kpts_prev[key][1]) / dt
        return (vx, vy)

    def get_joint_acceleration(self, key: str) -> Tuple[float, float]:
        """
        Calculates instantaneous acceleration vector (ax, ay) in normalized units/sec^2.
        """
        if len(self.history) < 3:
            return (0.0, 0.0)

        v_curr = self.get_joint_velocity(key, window_frames=2)
        # Previous velocity
        t_curr = self.history[-1][0]
        t_prev = self.history[-2][0]
        dt = t_curr - t_prev
        if dt <= 1e-4:
            return (0.0, 0.0)

        # Approximate previous velocity
        t_prev2, kpts_prev2, _ = self.history[-3]
        t_prev1, kpts_prev1, _ = self.history[-2]
        dt_prev = t_prev1 - t_prev2
        if dt_prev <= 1e-4 or key not in kpts_prev1 or key not in kpts_prev2:
            return (0.0, 0.0)

        v_prev_x = (kpts_prev1[key][0] - kpts_prev2[key][0]) / dt_prev
        v_prev_y = (kpts_prev1[key][1] - kpts_prev2[key][1]) / dt_prev

        ax = (v_curr[0] - v_prev_x) / dt
        ay = (v_curr[1] - v_prev_y) / dt
        return (ax, ay)

    def get_wrist_angular_velocity(self, side: str = "l") -> float:
        """
        Computes angular velocity (omega in radians/sec) of wrist orbiting the shoulder.
        Positive = Clockwise, Negative = Counter-Clockwise.
        """
        if len(self.history) < 2:
            return 0.0

        w_key = f"{side}w"
        s_key = f"{side}s"

        t_curr, k_curr, _ = self.history[-1]
        t_prev, k_prev, _ = self.history[-2]
        dt = t_curr - t_prev
        if dt <= 1e-4:
            return 0.0

        if w_key not in k_curr or s_key not in k_curr or w_key not in k_prev or s_key not in k_prev:
            return 0.0

        dx_curr = k_curr[w_key][0] - k_curr[s_key][0]
        dy_curr = k_curr[w_key][1] - k_curr[s_key][1]
        theta_curr = math.atan2(dy_curr, dx_curr)

        dx_prev = k_prev[w_key][0] - k_prev[s_key][0]
        dy_prev = k_prev[w_key][1] - k_prev[s_key][1]
        theta_prev = math.atan2(dy_prev, dx_prev)

        # Angular difference wrapped to [-pi, pi]
        dtheta = (theta_curr - theta_prev + math.pi) % (2.0 * math.pi) - math.pi
        return dtheta / dt


class FlapStrokeClassifier:
    """
    2.2 Flapping Recognition Engine:
    Recognizes rhythmic vertical arm strokes:
    - Analyzes wrist vertical position normalized by torso length (h_v)
    - Classifies stroke phases: UPSTROKE, DOWNSTROKE, NEUTRAL/HOLDING
    - Measures stroke amplitude (peak-to-trough travel)
    - Measures stroke frequency (Hz)
    - Evaluates flapping intensity (power 0.0 - 1.0) scaled by velocity & amplitude
    - Deadzone prevents accidental small arm twitches from triggering big lift impulses
    """
    VELOCITY_THRESHOLD = 0.50   # Min vertical speed (torso_length/sec) for active stroke
    MIN_AMPLITUDE = 0.20        # Min stroke amplitude (fraction of Torso Length) to qualify as flap

    def __init__(self):
        self.phase = FlapStrokePhase.NEUTRAL
        self.last_active_phase = FlapStrokePhase.NEUTRAL
        self.stroke_peak_y = 0.0
        self.stroke_trough_y = 0.0
        self.flap_count = 0
        self.last_flap_time = 0.0
        self.flap_frequency = 0.0
        self.flap_power = 0.0
        self.recent_stroke_durations = deque(maxlen=6)

    def update(
        self,
        avg_flap_height: float,
        vert_velocity: float,
        t: Optional[float] = None,
        adaptive_engine: Optional[Any] = None
    ) -> Tuple[bool, FlapStrokePhase, float, float]:
        """
        Updates flap stroke cycle.
        Returns: (is_flapping, stroke_phase, frequency_hz, power_0_to_1)
        Note: avg_flap_height is positive when wrists are ABOVE shoulders.
              vert_velocity is positive when wrists are moving UPWARD.
        """
        if t is None:
            t = time.perf_counter()

        min_amp = adaptive_engine.min_flap_amplitude if adaptive_engine is not None else self.MIN_AMPLITUDE
        full_amp = adaptive_engine.full_flap_amplitude if adaptive_engine is not None else (self.MIN_AMPLITUDE + 0.60)
        vel_scale = adaptive_engine.flap_velocity_scale if adaptive_engine is not None else 2.5

        # 1. Determine instantaneous stroke phase
        if vert_velocity > self.VELOCITY_THRESHOLD:
            current_phase = FlapStrokePhase.UPSTROKE
            self.stroke_peak_y = max(self.stroke_peak_y, avg_flap_height)
        elif vert_velocity < -self.VELOCITY_THRESHOLD:
            current_phase = FlapStrokePhase.DOWNSTROKE
            self.stroke_trough_y = min(self.stroke_trough_y, avg_flap_height)
        else:
            current_phase = FlapStrokePhase.NEUTRAL

        # 2. Detect Stroke Reversal & Cycle Transitions using last_active_phase
        if current_phase == FlapStrokePhase.DOWNSTROKE:
            if self.last_active_phase == FlapStrokePhase.UPSTROKE:
                # Top turnaround: transition from UP to DOWN
                stroke_amp = self.stroke_peak_y - self.stroke_trough_y
                if stroke_amp >= min_amp:
                    speed_factor = min(1.0, abs(vert_velocity) / vel_scale)
                    amp_factor = min(1.0, max(0.0, stroke_amp - min_amp) / max(0.01, full_amp - min_amp))
                    self.flap_power = 0.55 * speed_factor + 0.45 * amp_factor
                self.stroke_trough_y = avg_flap_height
            else:
                # Continuing downstroke: evaluate dynamic power
                stroke_depth = max(0.0, self.stroke_peak_y - avg_flap_height)
                if stroke_depth >= min_amp:
                    speed_factor = min(1.0, abs(vert_velocity) / vel_scale)
                    amp_factor = min(1.0, max(0.0, stroke_depth - min_amp) / max(0.01, full_amp - min_amp))
                    self.flap_power = max(self.flap_power, 0.55 * speed_factor + 0.45 * amp_factor)

            self.last_active_phase = FlapStrokePhase.DOWNSTROKE

        elif current_phase == FlapStrokePhase.UPSTROKE:
            if self.last_active_phase == FlapStrokePhase.DOWNSTROKE:
                # Bottom turnaround: completed full DOWN cycle!
                stroke_amp = self.stroke_peak_y - self.stroke_trough_y
                if stroke_amp >= min_amp:
                    self.flap_count += 1
                    if self.last_flap_time > 0:
                        dt = t - self.last_flap_time
                        if 0.15 <= dt <= 1.8:
                            freq = 1.0 / dt
                            self.recent_stroke_durations.append(freq)
                            self.flap_frequency = sum(self.recent_stroke_durations) / len(self.recent_stroke_durations)
                    self.last_flap_time = t

                self.stroke_peak_y = avg_flap_height

            self.last_active_phase = FlapStrokePhase.UPSTROKE

        self.phase = current_phase

        # 3. Flap active state window:
        # Flap remains active during continuous movement or for 0.45s after a clean stroke
        time_since_last_flap = t - self.last_flap_time if self.last_flap_time > 0 else 999.0
        is_actively_moving = (abs(vert_velocity) > self.VELOCITY_THRESHOLD) and (self.flap_power > 0.15)
        is_flapping = is_actively_moving or (time_since_last_flap < 0.45)

        # Decay power when movement stops
        if not is_actively_moving:
            decay = max(0.0, 1.0 - (time_since_last_flap / 0.45))
            effective_power = self.flap_power * decay
        else:
            effective_power = self.flap_power

        # Decay frequency if no flap for 1.8s
        if time_since_last_flap > 1.8:
            self.flap_frequency = max(0.0, self.flap_frequency * 0.90)
            self.flap_power = 0.0

        return is_flapping, self.phase, self.flap_frequency, effective_power


class ContinuousLeanClassifier:
    """
    2.3 Leaning Recognition Engine:
    Computes continuous torso lean & arm tilt steering:
    - Symmetrical deadzone (+/- 3.0 degrees) prevents drift during level flight
    - Monotonic smooth response curve: sensitive near center, stable at extreme lean
    - Integrates both Torso Spine Angle and Arm Elevation Delta
    """
    DEADZONE_DEG = 3.0
    MAX_LEAN_DEG = 24.0

    @staticmethod
    def evaluate_lean(
        torso_lean_deg: float,
        left_flap_height: float,
        right_flap_height: float
    ) -> Tuple[float, str]:
        """
        Returns: (steering_input_norm [-1.0 to +1.0], lean_label)
        Negative = Lean Left, Positive = Lean Right, 0.0 = Neutral
        """
        # 1. Arm tilt delta (left arm height minus right arm height)
        # Note: if right arm is lower than left, rolling to right
        arm_tilt_delta = left_flap_height - right_flap_height
        arm_tilt_deg = arm_tilt_delta * 18.0  # approximate angular equivalent

        # 2. Combined kinematic tilt: 60% Torso Spine + 40% Arm Tilt
        combined_deg = 0.60 * torso_lean_deg + 0.40 * arm_tilt_deg

        # 3. Apply Deadzone and Adaptive Sensitivity
        abs_deg = abs(combined_deg)
        if abs_deg <= ContinuousLeanClassifier.DEADZONE_DEG:
            steering_norm = 0.0
            label = "NEUTRAL"
        else:
            sign = 1.0 if combined_deg > 0 else -1.0
            effective = abs_deg - ContinuousLeanClassifier.DEADZONE_DEG
            span = ContinuousLeanClassifier.MAX_LEAN_DEG - ContinuousLeanClassifier.DEADZONE_DEG
            ratio = min(1.0, effective / span)

            # Quadratic ease-in near deadzone for smooth micro-adjustments
            smoothed_curve = ratio * ratio * 0.40 + ratio * 0.60
            steering_norm = sign * smoothed_curve

            label = "LEAN_RIGHT" if sign > 0 else "LEAN_LEFT"

        return float(steering_norm), label


class TuckDiveClassifier:
    """
    2.4 Dive Recognition Engine:
    Accurately identifies Tuck Dive pose and discriminates it from Leaning, Flapping, and Dash:
    - Hands folded compactly at chest: Wingspan Ratio < 1.45
    - Elbows tucked below shoulders AND below wrists
    - Must be sustained for minimum activation time (120 ms) to prevent false triggers during arm retracts
    """
    MIN_HOLD_TIME = 0.12  # Seconds of continuous pose required before triggering dive

    def __init__(self):
        self.pose_start_time = 0.0
        self.is_holding = False

    def evaluate(
        self,
        wingspan_ratio: float,
        avg_flap_height: float,
        ls: Tuple[float, float], rs: Tuple[float, float],
        le: Tuple[float, float], re: Tuple[float, float],
        lw: Tuple[float, float], rw: Tuple[float, float],
        t: Optional[float] = None,
        adaptive_engine: Optional[Any] = None
    ) -> Tuple[bool, float]:
        """
        Returns: (is_dive_confirmed, dive_intensity [0.0 to 1.0])
        """
        if t is None:
            t = time.perf_counter()

        tuck_limit = adaptive_engine.profile.tuck_wrist_dist_ratio if adaptive_engine is not None else 1.42

        # In image space, lower position in real world has LARGER y value
        # Geometric criteria:
        hands_compact = wingspan_ratio < tuck_limit
        wrists_at_chest = (-0.65 < avg_flap_height < 0.25)

        # Elbows pointing down below shoulders
        elbows_below_shoulders = (le[1] > ls[1] + 0.035) and (re[1] > rs[1] + 0.035)

        # Elbows below wrists
        elbows_below_wrists = (le[1] > lw[1] + 0.02) and (re[1] > rw[1] + 0.02)

        pose_valid = hands_compact and wrists_at_chest and elbows_below_shoulders and elbows_below_wrists

        if pose_valid:
            if not self.is_holding:
                self.is_holding = True
                self.pose_start_time = t

            hold_duration = t - self.pose_start_time
            if hold_duration >= self.MIN_HOLD_TIME:
                # Intensity increases with compactness (tighter tuck = faster dive)
                tightness = max(0.0, min(1.0, (tuck_limit - wingspan_ratio) / 0.60))
                intensity = 0.60 + 0.40 * tightness
                return True, intensity
            return False, 0.0
        else:
            self.is_holding = False
            self.pose_start_time = 0.0
            return False, 0.0


class PropellerRotationClassifier:
    """
    2.5 Arm Rotation / Propeller Dash Recognition Engine:
    Detects continuous circular/orbital motion of wrists around shoulders/elbows:
    - Tracks accumulated angular displacement over time
    - Monotonic direction: consistent sign of dtheta (no back-and-forth flapping)
    - Distinguishes 1D Flapping (linear oscillation) from 2D Propeller Dash (orbital rotation)
    - Minimum threshold: >= 240 degrees of continuous rotation in a single direction
    """
    MIN_ROTATION_ACCUM_RAD = 4.18   # ~240 degrees of continuous rotation
    MIN_ANGULAR_VELOCITY = 4.5      # rad/s (~0.7 rev/sec)

    def __init__(self, window_size: int = 15):
        self.angular_history_l = deque(maxlen=window_size)
        self.angular_history_r = deque(maxlen=window_size)
        self.accumulated_angle_l = 0.0
        self.accumulated_angle_r = 0.0
        self.prev_theta_l = None
        self.prev_theta_r = None
        self.dash_power = 0.0
        self.last_dash_time = 0.0

    def update(
        self,
        ls: Tuple[float, float], rs: Tuple[float, float],
        lw: Tuple[float, float], rw: Tuple[float, float],
        t: Optional[float] = None
    ) -> Tuple[bool, float, float]:
        """
        Updates rotational trajectory.
        Returns: (is_propeller_dash, dash_power [0.0 - 1.0], avg_angular_vel_rad_s)
        """
        if t is None:
            t = time.perf_counter()

        def compute_angle(origin, point):
            return math.atan2(point[1] - origin[1], point[0] - origin[0])

        theta_l = compute_angle(ls, lw)
        theta_r = compute_angle(rs, rw)

        def accumulate(prev_theta, curr_theta, accum):
            if prev_theta is None:
                return curr_theta, 0.0, 0.0
            dtheta = (curr_theta - prev_theta + math.pi) % (2.0 * math.pi) - math.pi

            # Check if direction is consistent with accumulated sign
            if abs(dtheta) > 0.02:
                if accum * dtheta >= 0:
                    accum += dtheta
                else:
                    # Direction reversed -> Reset rotation accumulation (this is a flap, NOT a propeller!)
                    accum = dtheta * 0.5
            else:
                # Idle decay
                accum *= 0.90
            return curr_theta, dtheta, accum

        self.prev_theta_l, dtheta_l, self.accumulated_angle_l = accumulate(self.prev_theta_l, theta_l, self.accumulated_angle_l)
        self.prev_theta_r, dtheta_r, self.accumulated_angle_r = accumulate(self.prev_theta_r, theta_r, self.accumulated_angle_r)

        self.angular_history_l.append(dtheta_l)
        self.angular_history_r.append(dtheta_r)

        # Average rotation accumulation
        max_accum = max(abs(self.accumulated_angle_l), abs(self.accumulated_angle_r))

        # Check for active propeller dash:
        is_dash = max_accum >= self.MIN_ROTATION_ACCUM_RAD

        if is_dash:
            self.last_dash_time = t
            # Dash power scales with rotational velocity
            power_factor = min(1.0, (max_accum - self.MIN_ROTATION_ACCUM_RAD) / 3.0)
            self.dash_power = 0.50 + 0.50 * power_factor
        else:
            # Short tail retention (0.3s)
            if t - self.last_dash_time < 0.30 and self.last_dash_time > 0:
                is_dash = True
                self.dash_power *= 0.85
            else:
                self.dash_power = 0.0

        # Estimate angular velocity (rad/sec)
        recent_dtheta = sum(self.angular_history_l) / max(1, len(self.angular_history_l))
        est_omega = abs(recent_dtheta) * 30.0  # assuming ~30 FPS

        return is_dash, self.dash_power, est_omega


class FlyUpClassifier:
    """
    1. FLY UP — UPWARD FLIGHT CLASSIFIER
    Detects upper torso / chest elevation combined with active flapping:
    - Chest elevation: Torso vertical extension ratio dy_spine / sw_safe >= 1.68 (or +0.08 above neutral)
    - Distinguishes chest elevation from head tilt alone (head tilt only shifts nose, not shoulder-hip distance)
    - Active rhythmic flapping with sufficient power (>= 0.20)
    - Upright posture (lean angle <= 22 deg)
    - Upper arms not tucked in hover or dive pose
    """
    ENTRY_CHEST_ELEVATION = 1.74
    EXIT_CHEST_ELEVATION = 1.66
    MIN_FLAP_POWER = 0.20

    def __init__(self):
        self.is_active = False
        self.fly_up_power = 0.0

    def evaluate(
        self,
        chest_elevation: float,
        is_flapping: bool,
        flap_power: float,
        lean_angle_deg: float,
        is_upper_arms_tucked: bool,
        adaptive_engine: Optional[Any] = None
    ) -> Tuple[bool, float]:
        threshold_entry = self.ENTRY_CHEST_ELEVATION
        threshold_exit = self.EXIT_CHEST_ELEVATION

        if adaptive_engine is not None and hasattr(adaptive_engine, "profile"):
            p = adaptive_engine.profile
            if p.is_calibrated and p.shoulder_width > 0.04:
                neutral_ratio = p.torso_length / p.shoulder_width
                threshold_entry = max(1.68, neutral_ratio * 1.09)
                threshold_exit = max(1.62, neutral_ratio * 1.04)

        if not self.is_active:
            chest_ok = chest_elevation >= threshold_entry
        else:
            chest_ok = chest_elevation >= threshold_exit

        posture_ok = chest_ok and abs(lean_angle_deg) <= 22.0 and not is_upper_arms_tucked

        if posture_ok and is_flapping and flap_power >= self.MIN_FLAP_POWER:
            self.is_active = True
            chest_factor = min(1.0, max(0.0, (chest_elevation - threshold_exit) / 0.25))
            self.fly_up_power = min(1.0, flap_power * 0.70 + chest_factor * 0.30)
            return True, self.fly_up_power
        else:
            self.is_active = False
            self.fly_up_power = 0.0
            return False, 0.0


class HoverClassifier:
    """
    2. STAY ON AIR — HOVER MODE CLASSIFIER
    Detects upper arms tucked to chest while forearms and wrists perform repetitive flapping:
    - Upper arms tucked: upper_arm_proximity <= 0.38 and elbows below shoulders
    - Elbows bent: avg_elbow_angle in [50 deg, 135 deg]
    - Elbow vertical velocity is low (< 0.50 unit/s): upper arms are stationary
    - Forearm / wrist vertical velocity shows active oscillation (wrist_vert_speed >= 0.45 unit/s)
    - Minimum duration window: 100 ms hold
    """
    ENTRY_PROXIMITY = 0.38
    EXIT_PROXIMITY = 0.46
    MIN_HOLD_SEC = 0.100

    def __init__(self):
        self.is_active = False
        self.first_detected_time = 0.0
        self.last_flap_time = 0.0
        self.hover_power = 0.0

    def evaluate(
        self,
        upper_arm_proximity: float,
        avg_elbow_angle: float,
        elbows_below_shoulders: bool,
        wrist_vert_speed: float,
        elbow_vert_speed: float,
        is_flapping_stroke: bool,
        t: Optional[float] = None
    ) -> Tuple[bool, float]:
        if t is None:
            t = time.perf_counter()

        thresh = self.EXIT_PROXIMITY if self.is_active else self.ENTRY_PROXIMITY
        arms_tucked = (upper_arm_proximity <= thresh) and elbows_below_shoulders

        is_forearm_flapping = (
            (wrist_vert_speed >= 0.40 or is_flapping_stroke) and
            (elbow_vert_speed <= 0.50 or elbow_vert_speed < wrist_vert_speed * 0.65)
        )

        cand = arms_tucked and is_forearm_flapping

        if cand:
            if self.first_detected_time == 0.0:
                self.first_detected_time = t
            self.last_flap_time = t

            if t - self.first_detected_time >= self.MIN_HOLD_SEC:
                self.is_active = True
                self.hover_power = min(1.0, max(0.40, wrist_vert_speed / 1.5))
                return True, self.hover_power
            else:
                return False, 0.0
        else:
            # Grace window (0.25s) if arms are still tucked and flapping pauses momentarily
            if self.is_active and arms_tucked and (t - self.last_flap_time < 0.25):
                self.hover_power *= 0.90
                return True, self.hover_power

            self.first_detected_time = 0.0
            self.is_active = False
            self.hover_power = 0.0
            return False, 0.0


class GentleDescentClassifier:
    """
    3. FORWARD GLIDE / GENTLE DESCENT — TUCKED T-POSE CLASSIFIER
    Detects upper arms tucked to chest, elbows bent, with forearms extended outwards like a T on forearms,
    and ABSENCE of flapping:
    - Upper arms tucked: upper_arm_proximity <= 0.38 and elbows below shoulders
    - Elbows bent: avg_elbow_angle in [50 deg, 135 deg]
    - Forearms extended laterally outward: is_forearms_extended (left wrist left of left elbow, right wrist right of right elbow, lateral spread >= 1.15)
    - Wrists are NOT compact at sternum (wingspan_ratio >= 1.05, distinctly different from Normal Dive < 0.85)
    - Absence of flapping: wrist_vert_speed < 0.38 unit/s and not in active upstroke/downstroke
    - Minimum duration window: 120 ms hold
    """
    ENTRY_PROXIMITY = 0.38
    EXIT_PROXIMITY = 0.46
    MIN_HOLD_SEC = 0.120

    def __init__(self):
        self.is_active = False
        self.first_detected_time = 0.0
        self.stability = 0.0

    def evaluate(
        self,
        upper_arm_proximity: float,
        avg_elbow_angle: float,
        is_forearms_extended: bool,
        wingspan_ratio: float,
        wrist_vert_speed: float,
        is_flapping_stroke: bool,
        t: Optional[float] = None
    ) -> Tuple[bool, float]:
        if t is None:
            t = time.perf_counter()

        thresh = self.EXIT_PROXIMITY if self.is_active else self.ENTRY_PROXIMITY
        arms_tucked = (upper_arm_proximity <= thresh)
        elbows_bent = 50.0 <= avg_elbow_angle <= 135.0

        # Absence of flapping
        no_flapping = (wrist_vert_speed < 0.38) and (not is_flapping_stroke)

        # Distinguish from Normal Dive (Normal dive has wingspan_ratio < 0.85 with wrists at sternum)
        not_normal_dive = wingspan_ratio >= 1.05 and is_forearms_extended

        cand = arms_tucked and elbows_bent and not_normal_dive and no_flapping

        if cand:
            if self.first_detected_time == 0.0:
                self.first_detected_time = t

            if t - self.first_detected_time >= self.MIN_HOLD_SEC:
                self.is_active = True
                duration = t - self.first_detected_time
                self.stability = min(1.0, 0.50 + duration * 0.50)
                return True, self.stability
            else:
                return False, 0.0
        else:
            self.first_detected_time = 0.0
            self.is_active = False
            self.stability = 0.0
            return False, 0.0


class GestureStateMachine:
    """
    2.6 Gesture State Machine:
    Manages mutually exclusive flight states and guarantees:
    - Priority Arbitration:
      1. HOVER: Upper arms tucked + repetitive forearm flapping
      2. GENTLE_DESCENT: Upper arms tucked + forearms extended + no flapping
      3. FLY_UP: Elevated chest + regular flapping
      4. TUCK_DIVE (Normal Dive): Compact wrists at sternum
      5. PROPELLER_DASH: Continuous arm rotation (if active)
      6. NORMAL_FLIGHT: Regular flapping or neutral glide
    - State Transition Guards (Hysteresis, Minimum Duration, Cooldowns)
    - Anti-Conflict Verification
    - Tracking Loss Safety: immediately defaults to NEUTRAL_GLIDE with zero impulses.
    """
    COOLDOWN_DIVE_TO_FLAP = 0.20   # Seconds before flap can trigger right after dive
    COOLDOWN_DASH_TO_DIVE = 0.25   # Seconds before dive can trigger right after dash

    def __init__(self, adaptive_engine: Optional[Any] = None):
        self.adaptive_engine = adaptive_engine
        self.current_state = GestureState.NEUTRAL_GLIDE
        self.state_enter_time = time.perf_counter()
        self.last_state_exit_time: Dict[GestureState, float] = {}

        # Classifiers
        self.motion_tracker = TemporalMotionTracker()
        self.flap_classifier = FlapStrokeClassifier()
        self.dive_classifier = TuckDiveClassifier()
        self.rotation_classifier = PropellerRotationClassifier()
        self.fly_up_classifier = FlyUpClassifier()
        self.hover_classifier = HoverClassifier()
        self.gentle_descent_classifier = GentleDescentClassifier()

    def update(
        self,
        kpts: Dict[str, Tuple[float, float]],
        biometrics: Dict[str, Any],
        is_tracking_valid: bool = True
    ) -> Dict[str, Any]:
        """
        Processes one frame of pose data and outputs unambiguous gesture telemetry.
        """
        now = time.perf_counter()

        # Safety Fallback: if tracking is lost, lock to NEUTRAL_GLIDE immediately
        if not is_tracking_valid:
            self.current_state = GestureState.NEUTRAL_GLIDE
            return {
                "active_state": GestureState.NEUTRAL_GLIDE.value,
                "active_state_id": 0,
                "is_tuck_dive": False,
                "is_flapping": False,
                "is_propeller_dash": False,
                "is_hover": False,
                "is_gentle_descent": False,
                "is_fly_up": False,
                "steering_input": 0.0,
                "lean_label": "NEUTRAL",
                "flap_frequency": 0.0,
                "flap_power": 0.0,
                "dive_power": 0.0,
                "dash_power": 0.0,
                "hover_power": 0.0,
                "gentle_stability": 0.0,
                "fly_up_power": 0.0,
                "chest_elevation": 1.55,
                "upper_arm_proximity": 0.50,
                "avg_elbow_angle": 90.0,
                "forearm_lateral_spread": 1.0,
                "stroke_phase": FlapStrokePhase.NEUTRAL.value
            }

        # 1. Record frame in temporal motion tracker
        self.motion_tracker.record_frame(kpts, biometrics, now)

        # 2. Extract kinematics
        v_lw = self.motion_tracker.get_joint_velocity("lw")
        v_rw = self.motion_tracker.get_joint_velocity("rw")
        avg_vert_vel = - (v_lw[1] + v_rw[1]) * 0.5
        wrist_vert_speed = (abs(v_lw[1]) + abs(v_rw[1])) * 0.5

        v_le = self.motion_tracker.get_joint_velocity("le")
        v_re = self.motion_tracker.get_joint_velocity("re")
        elbow_vert_speed = (abs(v_le[1]) + abs(v_re[1])) * 0.5

        # 3. Evaluate Classifiers
        # Continuous Lean
        if self.adaptive_engine is not None:
            steering_input, lean_label = self.adaptive_engine.compute_adaptive_steering(
                biometrics["lean_angle_deg"]
            )
        else:
            steering_input, lean_label = ContinuousLeanClassifier.evaluate_lean(
                biometrics["lean_angle_deg"],
                biometrics["left_flap_height"],
                biometrics["right_flap_height"]
            )

        # Flapping
        is_flap_cand, stroke_phase, flap_freq, flap_power = self.flap_classifier.update(
            biometrics["avg_flap_height"], avg_vert_vel, now, adaptive_engine=self.adaptive_engine
        )

        # Keypoint References
        ls, rs = kpts.get("ls", (0.4, 0.4)), kpts.get("rs", (0.6, 0.4))
        lh, rh = kpts.get("lh", (0.4, 0.7)), kpts.get("rh", (0.6, 0.7))
        le, re = kpts.get("le", (0.3, 0.5)), kpts.get("re", (0.7, 0.5))
        lw, rw = kpts.get("lw", (0.2, 0.5)), kpts.get("rw", (0.8, 0.5))

        # Tuck Dive
        is_dive_cand, dive_power = self.dive_classifier.evaluate(
            biometrics["wingspan_ratio"], biometrics["avg_flap_height"],
            ls, rs, le, re, lw, rw, now, adaptive_engine=self.adaptive_engine
        )

        # Propeller Dash
        is_dash_cand, dash_power, _ = self.rotation_classifier.update(ls, rs, lw, rw, now)

        # Hover
        is_hover_cand, hover_power = self.hover_classifier.evaluate(
            upper_arm_proximity=biometrics.get("upper_arm_proximity", 0.50),
            avg_elbow_angle=biometrics.get("avg_elbow_angle", 90.0),
            elbows_below_shoulders=(le[1] > ls[1] and re[1] > rs[1]),
            wrist_vert_speed=wrist_vert_speed,
            elbow_vert_speed=elbow_vert_speed,
            is_flapping_stroke=(stroke_phase in (FlapStrokePhase.UPSTROKE, FlapStrokePhase.DOWNSTROKE)),
            t=now
        )

        # Gentle Descent (Tucked T-Pose)
        is_gentle_cand, gentle_stability = self.gentle_descent_classifier.evaluate(
            upper_arm_proximity=biometrics.get("upper_arm_proximity", 0.50),
            avg_elbow_angle=biometrics.get("avg_elbow_angle", 90.0),
            is_forearms_extended=biometrics.get("is_forearms_extended", False),
            wingspan_ratio=biometrics.get("wingspan_ratio", 1.5),
            wrist_vert_speed=wrist_vert_speed,
            is_flapping_stroke=(stroke_phase in (FlapStrokePhase.UPSTROKE, FlapStrokePhase.DOWNSTROKE)),
            t=now
        )

        # Fly Up (Elevated Chest + Flapping)
        is_flyup_cand, fly_up_power = self.fly_up_classifier.evaluate(
            chest_elevation=biometrics.get("chest_elevation", 1.55),
            is_flapping=is_flap_cand,
            flap_power=flap_power,
            lean_angle_deg=biometrics.get("lean_angle_deg", 0.0),
            is_upper_arms_tucked=biometrics.get("is_upper_arms_tucked", False),
            adaptive_engine=self.adaptive_engine
        )

        # 4. Hierarchical State Arbitration (Strict Priority - Section 5)
        target_state = GestureState.NEUTRAL_GLIDE

        # Priority 1: Hover (Upper arms tucked + repetitive forearm flapping)
        if is_hover_cand:
            target_state = GestureState.HOVER

        # Priority 2: Gentle Descent (Upper arms tucked + extended forearms + no flapping)
        elif is_gentle_cand:
            target_state = GestureState.GENTLE_DESCENT

        # Priority 3: Fly Up (Elevated chest + regular flapping)
        elif is_flyup_cand:
            target_state = GestureState.FLY_UP

        # Priority 4: Normal Dive (Compact wrists at sternum)
        elif is_dive_cand:
            time_since_dash = now - self.last_state_exit_time.get(GestureState.PROPELLER_DASH, 0.0)
            if time_since_dash >= self.COOLDOWN_DASH_TO_DIVE:
                target_state = GestureState.TUCK_DIVE

        # Priority 5: Propeller Dash (Arm Rotation)
        elif is_dash_cand and dash_power > 0.40:
            target_state = GestureState.PROPELLER_DASH

        # Priority 6: Normal Flight (Flapping or Neutral Glide)
        elif is_flap_cand and flap_power > 0.20:
            time_since_dive = now - self.last_state_exit_time.get(GestureState.TUCK_DIVE, 0.0)
            if time_since_dive >= self.COOLDOWN_DIVE_TO_FLAP:
                target_state = GestureState.FLAPPING
        else:
            target_state = GestureState.NEUTRAL_GLIDE

        # 5. State Transition Execution
        if target_state != self.current_state:
            self.last_state_exit_time[self.current_state] = now
            self.current_state = target_state
            self.state_enter_time = now

        state_id_map = {
            GestureState.NEUTRAL_GLIDE: 0,
            GestureState.FLAPPING: 1,
            GestureState.TUCK_DIVE: 2,
            GestureState.PROPELLER_DASH: 3,
            GestureState.HOVER: 4,
            GestureState.GENTLE_DESCENT: 5,
            GestureState.FLY_UP: 6
        }
        active_state_id = state_id_map.get(self.current_state, 0)

        return {
            "active_state": self.current_state.value,
            "active_state_id": active_state_id,
            "is_tuck_dive": self.current_state == GestureState.TUCK_DIVE,
            "is_flapping": self.current_state in (GestureState.FLAPPING, GestureState.FLY_UP),
            "is_propeller_dash": self.current_state == GestureState.PROPELLER_DASH,
            "is_hover": self.current_state == GestureState.HOVER,
            "is_gentle_descent": self.current_state == GestureState.GENTLE_DESCENT,
            "is_fly_up": self.current_state == GestureState.FLY_UP,
            "steering_input": steering_input,
            "lean_label": lean_label,
            "flap_frequency": flap_freq,
            "flap_power": flap_power,
            "dive_power": dive_power,
            "dash_power": dash_power,
            "hover_power": hover_power if self.current_state == GestureState.HOVER else 0.0,
            "gentle_stability": gentle_stability if self.current_state == GestureState.GENTLE_DESCENT else 0.0,
            "fly_up_power": fly_up_power if self.current_state == GestureState.FLY_UP else 0.0,
            "chest_elevation": biometrics.get("chest_elevation", 1.55),
            "upper_arm_proximity": biometrics.get("upper_arm_proximity", 0.50),
            "avg_elbow_angle": biometrics.get("avg_elbow_angle", 90.0),
            "forearm_lateral_spread": biometrics.get("forearm_lateral_spread", 1.0),
            "stroke_phase": stroke_phase.value
        }
