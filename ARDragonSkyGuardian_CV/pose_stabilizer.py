"""
pose_stabilizer.py - Upgraded Computer Vision Tracking Stability & Biometrics Normalization Engine.
Part of AR Dragon Sky Guardian (Sky Peck Inspired Gameplay).

Key Improvements (Phase 1):
1. AdaptiveOneEuroFilter: Velocity-adaptive frequency cutoff with joint-differentiated tuning
   (Smooth/stable for torso anchors, responsive/agile for wrists).
2. BiometricNormalizer: 100% scale-, distance-, and position-invariant metric calculation:
   - Shoulder Width (Sw)
   - Torso Length (Tl)
   - Wingspan Ratio (Wr = Wrist-to-Wrist / Sw)
   - Flap Height Ratio (Wrist Height relative to Shoulder / Tl)
   - Body Lean Angle (degrees & normalized) based on MidHip-to-MidShoulder vector
   - Shoulder-to-Hip Alignment & Twist
3. RobustKeypointTracker:
   - Confidence-gated filtering (rejection of noise below threshold)
   - Kinematic outlier rejection (acceleration/step bounds)
   - Missing landmark handling with graceful decay & timeout buffer
   - Tracking state machine (TRACKED, DEGRADED, LOST, RECOVERING)
   - Recovery blending (prevents sudden teleportation spikes)
"""

import math
import time
from enum import Enum
from typing import Dict, Tuple, Optional, List, Any


class TrackingState(Enum):
    TRACKED = "TRACKED"          # All key joints confident
    DEGRADED = "DEGRADED"        # Some extremities occluded or low confidence, using kinematic hold
    LOST = "LOST"                # Subject missing or out of frame, gracefully transitioned to neutral
    RECOVERING = "RECOVERING"    # Re-acquired after being lost, applying smooth convergence


class AdaptiveOneEuroFilter:
    """
    Adaptive One-Euro Filter with differentiated velocity sensitivity:
    - At low speeds: high smoothing (min_cutoff) eliminating jitter.
    - At high speeds: dynamic cutoff increases proportionally with speed (beta), eliminating latency.
    """
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.3, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    def _smoothing_factor(self, dt: float, cutoff: float) -> float:
        r = 2.0 * math.pi * cutoff * dt
        return r / (r + 1.0)

    def filter(self, x: float, t: Optional[float] = None) -> float:
        if t is None:
            t = time.perf_counter()

        if self.x_prev is None:
            self.x_prev = x
            self.t_prev = t
            return x

        dt = t - self.t_prev
        if dt <= 1e-5:
            return self.x_prev

        # Compute derivative (velocity)
        dx = (x - self.x_prev) / dt
        edx = self._smoothing_factor(dt, self.d_cutoff)
        dx_hat = edx * dx + (1.0 - edx) * self.dx_prev

        # Adaptive cutoff frequency based on velocity
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        ex = self._smoothing_factor(dt, cutoff)
        x_hat = ex * x + (1.0 - ex) * self.x_prev

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat

    def reset(self):
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None


class BiometricNormalizer:
    """
    1.3 Coordinate Normalization Engine:
    Converts raw pixel coordinates into body-relative dimensionless ratios:
    - Completely invariant to camera distance (z-depth)
    - Invariant to user height and body proportions
    - Invariant to user offset from camera frame center
    """

    @staticmethod
    def calculate_biometrics(
        ls: Tuple[float, float], rs: Tuple[float, float],
        lh: Tuple[float, float], rh: Tuple[float, float],
        le: Tuple[float, float], re: Tuple[float, float],
        lw: Tuple[float, float], rw: Tuple[float, float],
        nose: Optional[Tuple[float, float]] = None
    ) -> Dict[str, Any]:
        """
        Calculates all scale-invariant biometric metrics from normalized (0-1) coordinates.
        Note: In image coordinates, y increases downward.
        """
        # 1. Centers of mass
        mid_shoulder = ((ls[0] + rs[0]) * 0.5, (ls[1] + rs[1]) * 0.5)
        mid_hip = ((lh[0] + rh[0]) * 0.5, (lh[1] + rh[1]) * 0.5)

        # 2. Key biometric scales
        # Torso Length (Tl)
        torso_length = math.hypot(mid_shoulder[0] - mid_hip[0], mid_shoulder[1] - mid_hip[1])
        tl_safe = max(0.06, torso_length)

        # Shoulder Width (Sw) with anatomical lower-bound guard for oblique / yawed body angles
        shoulder_width = math.hypot(rs[0] - ls[0], rs[1] - ls[1])
        sw_safe = max(0.04, max(shoulder_width, tl_safe * 0.45))

        # 3. Wingspan Metrics
        wrist_wrist_dist = math.hypot(rw[0] - lw[0], rw[1] - lw[1])
        wingspan_ratio = wrist_wrist_dist / sw_safe

        # 4. Flap Height Ratios (Wrist height relative to Shoulder, scaled by Torso Length)
        # Note: In screen coords, higher position has LOWER y value.
        # Positive value means wrist is ABOVE shoulder.
        left_flap_height = (ls[1] - lw[1]) / tl_safe
        right_flap_height = (rs[1] - rw[1]) / tl_safe
        avg_flap_height = (left_flap_height + right_flap_height) * 0.5

        # 5. Body Lean Angle (Degrees & Normalized)
        # Vector from MidHip to MidShoulder
        dx_spine = mid_shoulder[0] - mid_hip[0]
        dy_spine = mid_hip[1] - mid_shoulder[1]  # positive when upright (shoulder above hip)

        # Angle from true vertical in degrees (positive = leaning right, negative = leaning left)
        if dy_spine > 0.001:
            lean_angle_deg = math.degrees(math.atan2(dx_spine, dy_spine))
        else:
            lean_angle_deg = 0.0

        # Normalized lean based on shoulder width displacement (-1.0 to +1.0)
        # Deadzone: ~2.5 degrees or 0.04 Sw
        torso_offset_ratio = dx_spine / sw_safe
        if abs(torso_offset_ratio) < 0.04:
            body_lean_norm = 0.0
        else:
            sign = 1.0 if torso_offset_ratio > 0 else -1.0
            effective = abs(torso_offset_ratio) - 0.04
            # 0.40 Sw offset corresponds to maximum ~25-30 deg lean
            body_lean_norm = sign * min(1.0, effective / 0.36)

        # 6. Shoulder-to-Hip Alignment & Twist
        # Angle of shoulder line vs horizontal
        shoulder_angle_deg = math.degrees(math.atan2(rs[1] - ls[1], rs[0] - ls[0]))
        hip_angle_deg = math.degrees(math.atan2(rh[1] - lh[1], rh[0] - lh[0]))
        alignment_twist_deg = shoulder_angle_deg - hip_angle_deg

        # 7. Arm Extension Ratio (Shoulder to Wrist / Max Arm Length)
        # Approximate human arm length is ~1.25 - 1.45 * Shoulder Width
        max_arm_len = sw_safe * 1.35
        left_arm_reach = math.hypot(lw[0] - ls[0], lw[1] - ls[1])
        right_arm_reach = math.hypot(rw[0] - rs[0], rw[1] - rs[1])
        left_extension_ratio = min(1.2, left_arm_reach / max_arm_len)
        right_extension_ratio = min(1.2, right_arm_reach / max_arm_len)

        # 8. Head position relative to torso
        head_neck_ratio = 0.0
        if nose is not None:
            nose_shoulder_dist = mid_shoulder[1] - nose[1]
            head_neck_ratio = nose_shoulder_dist / sw_safe

        # 9. Chest Elevation (Upper Torso Extension)
        # Vertical distance from mid-hip to mid-shoulder scaled by safe shoulder width
        chest_elevation = max(0.5, dy_spine / sw_safe)

        # 10. Upper Arm Proximity to Torso (Elbow horizontal proximity to Shoulder line)
        dist_le_torso = abs(le[0] - ls[0]) / sw_safe
        dist_re_torso = abs(re[0] - rs[0]) / sw_safe
        upper_arm_proximity = (dist_le_torso + dist_re_torso) * 0.5
        is_upper_arms_tucked = (upper_arm_proximity <= 0.38) and (le[1] > ls[1]) and (re[1] > rs[1])

        # 11. Elbow Angles (Angle formed by Shoulder -> Elbow -> Wrist)
        def compute_elbow_angle(shoulder: Tuple[float, float], elbow: Tuple[float, float], wrist: Tuple[float, float]) -> float:
            v1_x, v1_y = shoulder[0] - elbow[0], shoulder[1] - elbow[1]
            v2_x, v2_y = wrist[0] - elbow[0], wrist[1] - elbow[1]
            m1 = math.hypot(v1_x, v1_y)
            m2 = math.hypot(v2_x, v2_y)
            if m1 < 1e-4 or m2 < 1e-4:
                return 90.0
            dot = v1_x * v2_x + v1_y * v2_y
            cos_val = max(-1.0, min(1.0, dot / (m1 * m2)))
            return math.degrees(math.acos(cos_val))

        left_elbow_angle = compute_elbow_angle(ls, le, lw)
        right_elbow_angle = compute_elbow_angle(rs, re, rw)
        avg_elbow_angle = (left_elbow_angle + right_elbow_angle) * 0.5

        # 12. Forearm Lateral Spread & Orientation (for Tucked T-Pose / Gentle Descent)
        left_forearm_lateral = (le[0] - lw[0]) / sw_safe
        right_forearm_lateral = (rw[0] - re[0]) / sw_safe
        forearm_lateral_spread = (rw[0] - lw[0]) / sw_safe

        left_forearm_angle = math.degrees(math.atan2(lw[1] - le[1], lw[0] - le[0]))
        right_forearm_angle = math.degrees(math.atan2(rw[1] - re[1], rw[0] - re[0]))

        is_forearms_extended = (
            left_forearm_lateral > 0.12 and right_forearm_lateral > 0.12 and
            forearm_lateral_spread >= 1.15 and
            (45.0 <= avg_elbow_angle <= 140.0)
        )

        return {
            "shoulder_width": shoulder_width,
            "torso_length": torso_length,
            "mid_shoulder": mid_shoulder,
            "mid_hip": mid_hip,
            "wrist_wrist_dist": wrist_wrist_dist,
            "wingspan_ratio": wingspan_ratio,
            "left_flap_height": left_flap_height,
            "right_flap_height": right_flap_height,
            "avg_flap_height": avg_flap_height,
            "lean_angle_deg": lean_angle_deg,
            "body_lean_norm": body_lean_norm,
            "shoulder_angle_deg": shoulder_angle_deg,
            "hip_angle_deg": hip_angle_deg,
            "alignment_twist_deg": alignment_twist_deg,
            "left_extension_ratio": left_extension_ratio,
            "right_extension_ratio": right_extension_ratio,
            "head_neck_ratio": head_neck_ratio,
            "chest_elevation": chest_elevation,
            "upper_arm_proximity": upper_arm_proximity,
            "is_upper_arms_tucked": is_upper_arms_tucked,
            "left_elbow_angle": left_elbow_angle,
            "right_elbow_angle": right_elbow_angle,
            "avg_elbow_angle": avg_elbow_angle,
            "left_forearm_lateral": left_forearm_lateral,
            "right_forearm_lateral": right_forearm_lateral,
            "forearm_lateral_spread": forearm_lateral_spread,
            "left_forearm_angle": left_forearm_angle,
            "right_forearm_angle": right_forearm_angle,
            "is_forearms_extended": is_forearms_extended
        }


class RobustKeypointTracker:
    """
    1.4 Tracking Stability Engine:
    Handles noise filtering, confidence gating, outlier rejection, missing landmarks,
    and smooth recovery blending.
    """

    CONFIDENCE_HIGH = 0.50
    CONFIDENCE_MIN = 0.25
    MISSING_TIMEOUT_SEC = 0.40  # Time before missing landmark decays to neutral
    RECOVERY_BLEND_FRAMES = 6   # Smooth convergence frames when re-acquiring lost point

    def __init__(self):
        # Joint-specific tuning:
        # Anchors (Torso): lower min_cutoff, higher stability
        # Extremities (Wrists): higher min_cutoff and higher beta, rapid response
        joint_configs = {
            "ls": (0.8, 0.15),
            "rs": (0.8, 0.15),
            "lh": (0.7, 0.12),
            "rh": (0.7, 0.12),
            "le": (1.1, 0.25),
            "re": (1.1, 0.25),
            "lw": (1.4, 0.45),
            "rw": (1.4, 0.45),
            "nose": (0.8, 0.15)
        }

        self.filters_x = {k: AdaptiveOneEuroFilter(min_cutoff=c[0], beta=c[1]) for k, c in joint_configs.items()}
        self.filters_y = {k: AdaptiveOneEuroFilter(min_cutoff=c[0], beta=c[1]) for k, c in joint_configs.items()}

        self.last_valid_positions: Dict[str, Tuple[float, float]] = {}
        self.last_valid_times: Dict[str, float] = {}
        self.joint_confidences: Dict[str, float] = {}
        self.recovery_frames_remaining = 0
        self.tracking_state = TrackingState.LOST
        self.state_change_time = time.perf_counter()

    def update_joint(
        self,
        key: str,
        raw_x: float,
        raw_y: float,
        conf: float,
        shoulder_ref: Optional[Tuple[float, float]] = None,
        shoulder_width: Optional[float] = None,
        elbow_ref: Optional[Tuple[float, float]] = None
    ) -> Tuple[float, float, float]:
        """
        Updates and filters a single keypoint with outlier rejection, anatomical clamping,
        and missing landmark fallback.
        Returns: (filtered_x, filtered_y, effective_confidence)
        """
        now = time.perf_counter()
        raw_x = max(0.005, min(0.995, raw_x))
        raw_y = max(0.005, min(0.995, raw_y))
        self.joint_confidences[key] = conf

        # 1. Missing / Low-Confidence Handling
        if conf < self.CONFIDENCE_MIN:
            if key in self.last_valid_positions:
                prev_x, prev_y = self.last_valid_positions[key]
                time_lost = now - self.last_valid_times.get(key, now)

                if time_lost < self.MISSING_TIMEOUT_SEC:
                    # Graceful hold within timeout window
                    # If kinematic chain anchor is available (elbow/shoulder), maintain relative posture
                    decay = max(0.0, 1.0 - (time_lost / self.MISSING_TIMEOUT_SEC))
                    return prev_x, prev_y, conf * decay
                else:
                    # Timed out: return neutral relative position if shoulder is known
                    if shoulder_ref is not None:
                        # Neutral arm rests slightly below shoulder
                        neutral_x = shoulder_ref[0] + (-0.15 if "l" in key else 0.15)
                        neutral_y = shoulder_ref[1] + 0.12
                        return neutral_x, neutral_y, 0.0
                    return prev_x, prev_y, 0.0
            else:
                return raw_x, raw_y, 0.0

        # 2. Anatomical Clamping (Constraint check)
        if shoulder_ref is not None and key in ["lw", "rw"]:
            sx, sy = shoulder_ref
            arm_dist = math.hypot(raw_x - sx, raw_y - sy)
            sw = shoulder_width if (shoulder_width is not None and shoulder_width > 0.05) else 0.22
            max_arm_reach = sw * 1.50

            if arm_dist > max_arm_reach:
                scale = max_arm_reach / arm_dist
                raw_x = sx + (raw_x - sx) * scale
                raw_y = sy + (raw_y - sy) * scale

        # 3. Kinematic Forearm Clamping if elbow is available
        if elbow_ref is not None and key in ["lw", "rw"] and conf < self.CONFIDENCE_HIGH:
            ex, ey = elbow_ref
            forearm_dist = math.hypot(raw_x - ex, raw_y - ey)
            sw = shoulder_width if (shoulder_width is not None and shoulder_width > 0.05) else 0.22
            max_forearm = sw * 0.85
            if forearm_dist > max_forearm:
                scale = max_forearm / forearm_dist
                raw_x = ex + (raw_x - ex) * scale
                raw_y = ey + (raw_y - ey) * scale

        # 4. Outlier Rejection (Velocity gating with distance scaling)
        if key in self.last_valid_positions:
            prev_x, prev_y = self.last_valid_positions[key]
            dt = max(0.001, now - self.last_valid_times.get(key, now))
            step = math.hypot(raw_x - prev_x, raw_y - prev_y)

            # Scale speed allowance with shoulder width (closer players exhibit larger screen displacement)
            sw_scale = max(0.65, min(2.5, (shoulder_width if shoulder_width else 0.22) / 0.20))
            max_step = ((3.2 * sw_scale) * dt) if key in ["lw", "rw"] else ((1.8 * sw_scale) * dt)
            if step > max_step:
                if conf < self.CONFIDENCE_HIGH:
                    # Reject high-speed glitch on low/medium confidence
                    return prev_x, prev_y, conf * 0.5
                else:
                    # Genuine fast motion with high confidence: clamp max step
                    scale = max_step / step
                    raw_x = prev_x + (raw_x - prev_x) * scale
                    raw_y = prev_y + (raw_y - prev_y) * scale

        # 5. Recovery Blending (after being lost)
        if self.recovery_frames_remaining > 0 and key in self.last_valid_positions:
            blend_alpha = 1.0 - (self.recovery_frames_remaining / self.RECOVERY_BLEND_FRAMES)
            prev_x, prev_y = self.last_valid_positions[key]
            raw_x = prev_x * (1.0 - blend_alpha) + raw_x * blend_alpha
            raw_y = prev_y * (1.0 - blend_alpha) + raw_y * blend_alpha

        # 6. Adaptive One-Euro Filter Pass
        clean_x = self.filters_x[key].filter(raw_x, now)
        clean_y = self.filters_y[key].filter(raw_y, now)

        clean_x = max(0.0, min(1.0, clean_x))
        clean_y = max(0.0, min(1.0, clean_y))

        self.last_valid_positions[key] = (clean_x, clean_y)
        self.last_valid_times[key] = now

        return clean_x, clean_y, conf

    def update_tracking_state(self, has_player: bool, confidences: Dict[str, float]) -> TrackingState:
        """
        Determines overall tracking state machine:
        TRACKED -> DEGRADED -> LOST -> RECOVERING -> TRACKED
        """
        now = time.perf_counter()

        if not has_player:
            if self.tracking_state != TrackingState.LOST:
                self.tracking_state = TrackingState.LOST
                self.state_change_time = now
            return self.tracking_state

        # Check core anchors (shoulders + hips)
        torso_confs = [
            confidences.get("ls", 0.0), confidences.get("rs", 0.0),
            confidences.get("lh", 0.0), confidences.get("rh", 0.0)
        ]
        avg_torso_conf = sum(torso_confs) / len(torso_confs) if torso_confs else 0.0

        wrist_confs = [confidences.get("lw", 0.0), confidences.get("rw", 0.0)]
        min_wrist_conf = min(wrist_confs) if wrist_confs else 0.0

        if avg_torso_conf < 0.25:
            # Torso lost
            new_state = TrackingState.LOST
        elif min_wrist_conf < self.CONFIDENCE_MIN:
            # Torso confident but wrists occluded
            new_state = TrackingState.DEGRADED
        else:
            if self.tracking_state == TrackingState.LOST:
                new_state = TrackingState.RECOVERING
                self.recovery_frames_remaining = self.RECOVERY_BLEND_FRAMES
            elif self.tracking_state == TrackingState.RECOVERING:
                self.recovery_frames_remaining -= 1
                new_state = TrackingState.RECOVERING if self.recovery_frames_remaining > 0 else TrackingState.TRACKED
            else:
                new_state = TrackingState.TRACKED

        if new_state != self.tracking_state:
            self.tracking_state = new_state
            self.state_change_time = now

        return self.tracking_state

    def reset(self):
        for f in self.filters_x.values():
            f.reset()
        for f in self.filters_y.values():
            f.reset()
        self.last_valid_positions.clear()
        self.last_valid_times.clear()
        self.joint_confidences.clear()
        self.recovery_frames_remaining = 0
        self.tracking_state = TrackingState.LOST


# Backward-compatible wrapper for existing imports
class PoseStabilizer:
    """
    Drop-in compatibility layer wrapping RobustKeypointTracker and BiometricNormalizer.
    """
    def __init__(self):
        self.tracker = RobustKeypointTracker()
        self.normalizer = BiometricNormalizer()

    def update_point(
        self,
        key: str,
        raw_x: float,
        raw_y: float,
        conf: float = 1.0,
        shoulder_ref: Optional[Tuple[float, float]] = None,
        shoulder_width: Optional[float] = None,
        elbow_ref: Optional[Tuple[float, float]] = None
    ) -> Tuple[float, float]:
        cx, cy, _ = self.tracker.update_joint(
            key, raw_x, raw_y, conf,
            shoulder_ref=shoulder_ref,
            shoulder_width=shoulder_width,
            elbow_ref=elbow_ref
        )
        return cx, cy

    def reset(self):
        self.tracker.reset()


class WingFlapDetector:
    """
    Wing Flap Detector with Hysteresis & Biometric Flap Height:
    - Sits as input recognition layer
    - Preserved for compatibility with existing modules
    """
    STATE_DOWN = 0
    STATE_GOING_UP = 1
    STATE_UP = 2
    STATE_GOING_DOWN = 3

    def __init__(self, hysteresis: float = 0.035):
        self.hysteresis = hysteresis
        self.state = self.STATE_DOWN
        self.flap_count = 0
        self.last_flap_time = 0.0
        self.flap_frequency = 0.0
        self.flap_history: List[float] = []
        self.last_y = 0.5
        self.flap_power = 0.0

    def update(
        self, lw: Tuple[float, float], rw: Tuple[float, float],
        ls: Tuple[float, float], rs: Tuple[float, float]
    ) -> Tuple[int, str, float, float]:
        now = time.perf_counter()
        avg_wrist_y = (lw[1] + rw[1]) * 0.5
        avg_shoulder_y = (ls[1] + rs[1]) * 0.5

        dy = abs(avg_wrist_y - self.last_y)
        self.last_y = avg_wrist_y
        self.flap_power = min(1.0, dy * 14.0)

        up_threshold = avg_shoulder_y - self.hysteresis
        down_threshold = avg_shoulder_y + self.hysteresis

        is_clearly_above = (lw[1] < up_threshold) and (rw[1] < up_threshold)
        is_clearly_below = (lw[1] > down_threshold) and (rw[1] > down_threshold)

        status_str = "SEJAJAR BAHU"

        if self.state == self.STATE_DOWN:
            status_str = "SAYAP DI BAWAH"
            if is_clearly_above:
                self.state = self.STATE_UP
        elif self.state == self.STATE_UP:
            status_str = "SAYAP DI ATAS"
            if is_clearly_below:
                self.flap_count += 1
                self.state = self.STATE_DOWN
                if self.last_flap_time > 0:
                    dt = now - self.last_flap_time
                    if dt > 0.12:
                        freq = 1.0 / dt
                        self.flap_history.append(freq)
                        if len(self.flap_history) > 5:
                            self.flap_history.pop(0)
                        self.flap_frequency = sum(self.flap_history) / len(self.flap_history)
                self.last_flap_time = now

        if now - self.last_flap_time > 2.0:
            self.flap_frequency = max(0.0, self.flap_frequency * 0.9)

        return self.flap_count, status_str, self.flap_frequency, self.flap_power


def compute_smooth_tilt(
    lw: Tuple[float, float], rw: Tuple[float, float],
    deadzone: float = 0.035, max_tilt: float = 0.28
) -> Tuple[float, float]:
    """
    Computes smoothed arm tilt with deadzone:
    - Positive = right turn
    - Negative = left turn
    """
    raw_diff = lw[1] - rw[1]
    if abs(raw_diff) <= deadzone:
        normalized_tilt = 0.0
    else:
        sign = 1.0 if raw_diff > 0 else -1.0
        effective = abs(raw_diff) - deadzone
        range_val = max(0.01, max_tilt - deadzone)
        normalized_tilt = sign * min(1.0, effective / range_val)

    return raw_diff, normalized_tilt
