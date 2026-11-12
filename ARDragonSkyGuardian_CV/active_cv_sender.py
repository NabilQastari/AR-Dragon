"""
active_cv_sender.py
Modul Pengirim Computer Vision Resmi - AR Dragon Sky Guardian (Phase 2 Upgrade).
- Model: YOLOv8n-pose (Tensor Cores CUDA GPU ~18 ms / 54 FPS)
- Stabilizer: RobustKeypointTracker dengan Adaptive One-Euro Filter & Kinematic Velocity Gating
- Normalisasi: BiometricNormalizer (Scale-, Distance-, & Position-Invariant)
- State Machine: TrackingState (TRACKED, DEGRADED, LOST, RECOVERING)
- Gesture Engine: GestureStateMachine (Phase 2):
  * Flap to Climb (Upstroke/Downstroke segmentation, frequency, amplitude-weighted power)
  * Continuous Lean (Torso spine & arm tilt with deadzone)
  * Tuck Dive (Compactness & downward elbow alignment with hold duration check)
  * Propeller Dash (Monotonic angular displacement & orbital consistency)
- Visualisasi: High-Detail CV Debug Overlay dengan Heatmap Confidence, Vektor Biometrik, & Gesture State
- Protokol: UDP 127.0.0.1:5052 (32-Float Telemetri) & UDP 127.0.0.1:5053 (PIP Video)
"""

import os
import sys
import time
import math
import argparse
import tempfile
from typing import Dict, Tuple, Optional, List, Any

import cv2
import numpy as np
import torch

os.environ['MPLCONFIGDIR'] = tempfile.gettempdir()
from ultralytics import YOLO

from udp_sender import PoseUDPSender, VideoUDPSender
from camera_stream import ThreadedCamera
from pose_stabilizer import (
    RobustKeypointTracker,
    BiometricNormalizer,
    TrackingState
)
from motion_recognizer import (
    GestureStateMachine,
    GestureState,
    FlapStrokePhase
)
from mouth_tracker import MouthTracker
from player_calibrator import PlayerCalibrator, CalibrationState


# COCO 17 Keypoint Indices
IDX_NOSE = 0
IDX_LEFT_EYE, IDX_RIGHT_EYE = 1, 2
IDX_LEFT_EAR, IDX_RIGHT_EAR = 3, 4
IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER = 5, 6
IDX_LEFT_ELBOW, IDX_RIGHT_ELBOW = 7, 8
IDX_LEFT_WRIST, IDX_RIGHT_WRIST = 9, 10
IDX_LEFT_HIP, IDX_RIGHT_HIP = 11, 12
IDX_LEFT_KNEE, IDX_RIGHT_KNEE = 13, 14
IDX_LEFT_ANKLE, IDX_RIGHT_ANKLE = 15, 16

# Skeleton connection pairs for rendering
SKELETON_CONNECTIONS = [
    (IDX_LEFT_SHOULDER, IDX_RIGHT_SHOULDER),
    (IDX_LEFT_SHOULDER, IDX_LEFT_ELBOW),
    (IDX_LEFT_ELBOW, IDX_LEFT_WRIST),
    (IDX_RIGHT_SHOULDER, IDX_RIGHT_ELBOW),
    (IDX_RIGHT_ELBOW, IDX_RIGHT_WRIST),
    (IDX_LEFT_SHOULDER, IDX_LEFT_HIP),
    (IDX_RIGHT_SHOULDER, IDX_RIGHT_HIP),
    (IDX_LEFT_HIP, IDX_RIGHT_HIP),
    (IDX_LEFT_HIP, IDX_LEFT_KNEE),
    (IDX_LEFT_KNEE, IDX_LEFT_ANKLE),
    (IDX_RIGHT_HIP, IDX_RIGHT_KNEE),
    (IDX_RIGHT_KNEE, IDX_RIGHT_ANKLE),
    (IDX_NOSE, IDX_LEFT_SHOULDER),
    (IDX_NOSE, IDX_RIGHT_SHOULDER)
]


def parse_args():
    parser = argparse.ArgumentParser(description="Active CV Sender for AR Dragon Sky Guardian (Phase 2)")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="Target UDP IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5052, help="Target UDP Pose Port (default: 5052)")
    parser.add_argument("--video-port", type=int, default=5053, help="Target UDP Video PIP Port (default: 5053)")
    parser.add_argument("--no-video-stream", action="store_true", help="Disable PIP video UDP stream")
    parser.add_argument("--cam", type=int, default=0, help="Camera Index (default: 0)")
    parser.add_argument("--width", type=int, default=1280, help="Capture Width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Capture Height (default: 720)")
    parser.add_argument("--headless", action="store_true", help="Run in headless background mode (no GUI window)")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO Pose Confidence Threshold (default: 0.25)")
    return parser.parse_args()


def draw_debug_overlay(
    frame: np.ndarray,
    all_kpts: Optional[np.ndarray],
    tracker: RobustKeypointTracker,
    biometrics: Optional[Dict],
    fps: float,
    latency_ms: float,
    tracking_state: TrackingState,
    gesture_result: Dict[str, Any],
    calib_state: CalibrationState = CalibrationState.IDLE,
    calib_progress: float = 0.0,
    calib_text: str = ""
):
    """
    CV Debug Visualization:
    Renders camera feed, skeleton with confidence color-coding, biometric lines,
    gesture state badges, and developer telemetry HUD.
    """
    h, w, _ = frame.shape

    def get_conf_color(c: float) -> Tuple[int, int, int]:
        if c >= 0.55:
            return (0, 255, 100)      # High: Vibrant Green
        elif c >= 0.25:
            return (0, 200, 255)      # Medium: Amber/Orange
        else:
            return (0, 50, 220)       # Low/Occluded: Red

    # 1. Render Skeleton Bones
    if all_kpts is not None and len(all_kpts) >= 17:
        for p1_idx, p2_idx in SKELETON_CONNECTIONS:
            x1, y1, c1 = float(all_kpts[p1_idx][0]), float(all_kpts[p1_idx][1]), float(all_kpts[p1_idx][2])
            x2, y2, c2 = float(all_kpts[p2_idx][0]), float(all_kpts[p2_idx][1]), float(all_kpts[p2_idx][2])

            if c1 >= 0.20 and c2 >= 0.20:
                pt1 = (int(x1), int(y1))
                pt2 = (int(x2), int(y2))
                bone_conf = min(c1, c2)
                color = get_conf_color(bone_conf)
                thickness = 3 if bone_conf >= 0.50 else 2
                cv2.line(frame, pt1, pt2, color, thickness, cv2.LINE_AA)

        # Render Keypoint Circles
        for idx in range(17):
            x, y, c = float(all_kpts[idx][0]), float(all_kpts[idx][1]), float(all_kpts[idx][2])
            pt = (int(x), int(y))
            color = get_conf_color(c)
            radius = 5 if c >= 0.50 else 3
            cv2.circle(frame, pt, radius, color, -1, cv2.LINE_AA)
            cv2.circle(frame, pt, radius + 2, (30, 30, 30), 1, cv2.LINE_AA)

    # 2. Render Biometric Vector Overlays
    if biometrics is not None:
        ms = (int(biometrics["mid_shoulder"][0] * w), int(biometrics["mid_shoulder"][1] * h))
        mh = (int(biometrics["mid_hip"][0] * w), int(biometrics["mid_hip"][1] * h))

        # Torso spine vector (Magenta)
        cv2.line(frame, mh, ms, (255, 0, 255), 3, cv2.LINE_AA)
        cv2.circle(frame, ms, 6, (255, 0, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, mh, 6, (255, 0, 255), -1, cv2.LINE_AA)

        # True Vertical Reference line from MidHip (Dotted white)
        vert_top = (mh[0], max(10, mh[1] - int(biometrics["torso_length"] * h * 1.1)))
        cv2.line(frame, mh, vert_top, (200, 200, 200), 1, cv2.LINE_4)

        # Shoulder width line (Cyan)
        if "ls" in tracker.last_valid_positions and "rs" in tracker.last_valid_positions:
            ls_pt = (int(tracker.last_valid_positions["ls"][0] * w), int(tracker.last_valid_positions["rs"][1] * h))
            rs_pt = (int(tracker.last_valid_positions["rs"][0] * w), int(tracker.last_valid_positions["rs"][1] * h))
            cv2.line(frame, ls_pt, rs_pt, (255, 255, 0), 2, cv2.LINE_AA)

    # 3. Developer Telemetry HUD Panel (Left Top)
    hud_w, hud_h = 380, 260
    overlay = frame.copy()
    cv2.rectangle(overlay, (15, 15), (15 + hud_w, 15 + hud_h), (18, 18, 22), -1)
    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)
    cv2.rectangle(frame, (15, 15), (15 + hud_w, 15 + hud_h), (60, 60, 75), 1)

    # State Badge Colors
    state_colors = {
        TrackingState.TRACKED: (0, 255, 100),
        TrackingState.DEGRADED: (0, 200, 255),
        TrackingState.LOST: (0, 50, 230),
        TrackingState.RECOVERING: (255, 220, 0)
    }
    st_col = state_colors.get(tracking_state, (200, 200, 200))

    cv2.putText(frame, "AR DRAGON CV TELEMETRY v6.5 (PHASE 2)", (25, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, f"TRACKING: {tracking_state.value}", (25, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.50, st_col, 2, cv2.LINE_AA)
    cv2.putText(frame, f"FPS: {fps:.1f} | Latency: {latency_ms:.1f} ms (CUDA)", (25, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 220), 1, cv2.LINE_AA)

    if biometrics is not None:
        sw = biometrics["shoulder_width"]
        tl = biometrics["torso_length"]
        wr = biometrics["wingspan_ratio"]
        lean_deg = biometrics["lean_angle_deg"]
        steer = gesture_result.get("steering_input", 0.0)

        cv2.putText(frame, f"Sw: {sw:.3f} | Tl: {tl:.3f} | Wingspan Ratio: {wr:.2f}", (25, 102),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(frame, f"Spine Lean: {lean_deg:+.1f} deg | Steering: {steer:+.2f}", (25, 122),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 200) if abs(lean_deg) > 4.0 else (180, 180, 180), 1, cv2.LINE_AA)

        # Steering bar graphic
        bar_cx = 200
        bar_y = 138
        cv2.rectangle(frame, (bar_cx - 80, bar_y - 4), (bar_cx + 80, bar_y + 4), (50, 50, 60), -1)
        steer_px = int(steer * 75)
        bar_col = (0, 255, 200) if steer != 0 else (120, 120, 120)
        cv2.rectangle(frame, (bar_cx, bar_y - 4), (bar_cx + steer_px, bar_y + 4), bar_col, -1)
        cv2.circle(frame, (bar_cx, bar_y), 3, (255, 255, 255), -1)

        # Active Gesture State
        active_st = gesture_result.get("active_state", "GLIDE")
        if active_st == GestureState.PROPELLER_DASH.value:
            mode_lbl = f"GESTURE: PROPELLER DASH (+{gesture_result.get('dash_power',0)*100:.0f}%)"
            mode_col = (255, 180, 0)
        elif active_st == GestureState.TUCK_DIVE.value:
            mode_lbl = f"GESTURE: TUCK DIVE (+{gesture_result.get('dive_power',0)*100:.0f}%)"
            mode_col = (0, 100, 255)
        elif active_st == GestureState.HOVER.value:
            mode_lbl = f"GESTURE: HOVER (Lengan Rapat + Forearm Flap: {gesture_result.get('hover_power',0)*100:.0f}%)"
            mode_col = (255, 100, 255)
        elif active_st == GestureState.GENTLE_DESCENT.value:
            mode_lbl = f"GESTURE: GENTLE DESCENT (Tucked T-Pose: {gesture_result.get('gentle_stability',0)*100:.0f}%)"
            mode_col = (0, 220, 220)
        elif active_st == GestureState.FLY_UP.value:
            mode_lbl = f"GESTURE: FLY UP (Dada Terangkat + Flap: {gesture_result.get('fly_up_power',0)*100:.0f}%)"
            mode_col = (0, 255, 120)
        elif active_st == GestureState.FLAPPING.value:
            mode_lbl = f"GESTURE: FLAP ({gesture_result.get('flap_frequency',0):.1f}Hz, {gesture_result.get('flap_power',0)*100:.0f}%)"
            mode_col = (0, 255, 100)
        else:
            mode_lbl = "GESTURE: GLIDE (Jelajah Stabil)"
            mode_col = (255, 220, 60)

        cv2.putText(frame, mode_lbl, (25, 172), cv2.FONT_HERSHEY_SIMPLEX, 0.48, mode_col, 2, cv2.LINE_AA)

        # Stroke phase indicator
        stroke = gesture_result.get("stroke_phase", "NEUTRAL")
        cv2.putText(frame, f"Stroke Phase: {stroke}", (25, 196), cv2.FONT_HERSHEY_SIMPLEX, 0.40,
                    (0, 255, 200) if stroke != "NEUTRAL" else (140, 140, 140), 1, cv2.LINE_AA)

        # Confidences row
        conf_str = f"Conf: LS={tracker.joint_confidences.get('ls',0):.2f} RS={tracker.joint_confidences.get('rs',0):.2f} LW={tracker.joint_confidences.get('lw',0):.2f} RW={tracker.joint_confidences.get('rw',0):.2f}"
        cv2.putText(frame, conf_str, (25, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (160, 160, 160), 1, cv2.LINE_AA)

        # Section 7 Biometric & Kinematic Telemetry Overlay
        chest_e = biometrics.get("chest_elevation", 1.55) if biometrics else 1.55
        u_prox = biometrics.get("upper_arm_proximity", 0.50) if biometrics else 0.50
        e_ang = biometrics.get("avg_elbow_angle", 90.0) if biometrics else 90.0
        f_spd = biometrics.get("forearm_lateral_spread", 1.0) if biometrics else 1.0
        telem_str = f"Chest={chest_e:.2f} | Prox={u_prox:.2f} | Elbow={e_ang:.0f}deg | Spread={f_spd:.2f}"
        cv2.putText(frame, telem_str, (25, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (200, 220, 255), 1, cv2.LINE_AA)

        cv2.putText(frame, f"Active State ID: {active_st}", (25, 258), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 180, 180), 1, cv2.LINE_AA)
        cv2.putText(frame, f"Kalibrasi: {calib_text} [Tekan 'C' untuk Kalibrasi]", (25, 276), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 220, 255) if calib_state != CalibrationState.IDLE else (160, 160, 160), 1, cv2.LINE_AA)
    else:
        cv2.putText(frame, "MENUNGGU TARGET PEMAIN...", (25, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 160, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, "Posisikan diri menghadap kamera.", (25, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (180, 180, 180), 1, cv2.LINE_AA)

    # 4. Calibration Center Banner (Jika sedang proses kalibrasi)
    if calib_state not in (CalibrationState.IDLE, CalibrationState.COMPLETE):
        bw, bh = 540, 52
        bx = (w - bw) // 2
        by = 22
        overlay = frame.copy()
        cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (15, 20, 35), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 220, 255), 2)
        cv2.putText(frame, calib_text, (bx + 16, by + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 2, cv2.LINE_AA)
        
        # Progress bar
        cv2.rectangle(frame, (bx + 16, by + 34), (bx + bw - 16, by + 42), (40, 45, 55), -1)
        pw = int((bw - 32) * max(0.0, min(1.0, calib_progress)))
        cv2.rectangle(frame, (bx + 16, by + 34), (bx + 16 + pw, by + 42), (0, 255, 120), -1)


def main():
    args = parse_args()

    model_path = os.path.join(os.path.dirname(__file__), "yolov8n-pose.pt")
    if not os.path.exists(model_path):
        print(f"[!] File model YOLO tidak ditemukan: {model_path}")
        return

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[*] Inisialisasi YOLOv8n-pose pada perangkat: {device}...")
    pose_model = YOLO(model_path)
    if device.startswith("cuda"):
        pose_model.to(device)

    # Warmup inference
    warmup_dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
    for _ in range(5):
        _ = pose_model(warmup_dummy, device=device, imgsz=640, verbose=False, conf=args.conf)
    if device.startswith("cuda"):
        torch.cuda.synchronize()
    print("[OK] Warmup YOLOv8n-pose selesai. Tensor Cores aktif.")

    print("[*] Menginisialisasi Mouth Tracker (Head-Crop)...")
    mouth_tracker = MouthTracker()

    print(f"[*] Membuka koneksi UDP Pose ke {args.ip}:{args.port}...")
    sender = PoseUDPSender(ip=args.ip, port=args.port)

    video_sender = None
    if not args.no_video_stream:
        print(f"[*] Membuka streaming video PIP UDP ke {args.ip}:{args.video_port}...")
        video_sender = VideoUDPSender(ip=args.ip, port=args.video_port)

    # Initialize Phase 1, Phase 2, & Phase 4 Engines
    tracker = RobustKeypointTracker()
    normalizer = BiometricNormalizer()
    calibrator = PlayerCalibrator()
    gesture_sm = GestureStateMachine(adaptive_engine=calibrator.engine)

    print(f"[*] Menyalakan kamera (MJPG 30 FPS, Cam ID {args.cam})...")
    cam = ThreadedCamera(src=args.cam, width=args.width, height=args.height, fps=30)
    time.sleep(0.4)

    print("=" * 75)
    print("🐉 ACTIVE CV SENDER (PHASE 4 UPGRADE) - AR DRAGON SKY GUARDIAN")
    print(f"   - Model           : YOLOv8n-pose (17 COCO Keypoints, CUDA GPU)")
    print(f"   - Target UDP Pose : {args.ip}:{args.port} (34 Float CSV)")
    print(f"   - Target UDP Video: {args.ip}:{args.video_port} ({'AKTIF' if video_sender else 'NONAKTIF'})")
    print(f"   - Mode Eksekusi   : {'HEADLESS (Background)' if args.headless else 'INTERAKTIF GUI PREVIEW'}")
    print(f"   - Gesture Engine  : GestureStateMachine (Glide, Flap, Tuck Dive, Propeller Dash)")
    print(f"   - Calibrator      : PlayerCalibrator & AdaptiveThresholdEngine (Tekan 'C' untuk Kalibrasi)")
    print(f"   - State Priority  : Propeller Dash > Tuck Dive > Flap > Glide")
    print("   - Tekan Ctrl+C (atau 'q'/ESC pada GUI) untuk menghentikan pengiriman")
    print("=" * 75)

    prev_time = time.time()
    fps_history: List[float] = []
    head_pos = None

    try:
        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            t_start = time.perf_counter()

            # 1. Inferensi Pose YOLOv8n-pose
            results = pose_model(frame, device=device, imgsz=640, verbose=False, conf=args.conf)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            t_infer = time.perf_counter()
            latency_ms = (t_infer - t_start) * 1000.0

            pose_detected = False
            kpts_raw = None
            confidences: Dict[str, float] = {}
            biometrics = None
            gesture_result: Dict[str, Any] = {
                "active_state": "GLIDE",
                "is_tuck_dive": False,
                "is_flapping": False,
                "is_propeller_dash": False,
                "steering_input": 0.0,
                "lean_label": "NEUTRAL",
                "flap_frequency": 0.0,
                "flap_power": 0.0,
                "dive_power": 0.0,
                "dash_power": 0.0,
                "stroke_phase": "NEUTRAL"
            }

            if results and len(results) > 0 and results[0].keypoints is not None:
                kpts_data = results[0].keypoints.data
                boxes = results[0].boxes
                if kpts_data is not None and len(kpts_data) > 0:
                    # Select primary player with largest bounding box
                    best_idx = 0
                    if boxes is not None and len(boxes) > 1:
                        max_area = 0.0
                        for b_idx, box in enumerate(boxes):
                            xyxy = box.xyxy[0].cpu().numpy()
                            area = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1])
                            if area > max_area:
                                max_area = area
                                best_idx = b_idx

                    kpts = kpts_data[best_idx].cpu().numpy()
                    kpts_raw = kpts

                    if len(kpts) >= 17:
                        def get_raw_pt(idx):
                            return float(kpts[idx][0]) / w, float(kpts[idx][1]) / h, float(kpts[idx][2])

                        raw_nose_x, raw_nose_y, c_nose = get_raw_pt(IDX_NOSE)
                        raw_ls_x, raw_ls_y, c_ls = get_raw_pt(IDX_LEFT_SHOULDER)
                        raw_rs_x, raw_rs_y, c_rs = get_raw_pt(IDX_RIGHT_SHOULDER)
                        raw_le_x, raw_le_y, c_le = get_raw_pt(IDX_LEFT_ELBOW)
                        raw_re_x, raw_re_y, c_re = get_raw_pt(IDX_RIGHT_ELBOW)
                        raw_lw_x, raw_lw_y, c_lw = get_raw_pt(IDX_LEFT_WRIST)
                        raw_rw_x, raw_rw_y, c_rw = get_raw_pt(IDX_RIGHT_WRIST)
                        raw_lh_x, raw_lh_y, c_lh = get_raw_pt(IDX_LEFT_HIP)
                        raw_rh_x, raw_rh_y, c_rh = get_raw_pt(IDX_RIGHT_HIP)

                        confidences = {
                            "nose": c_nose, "ls": c_ls, "rs": c_rs,
                            "le": c_le, "re": c_re, "lw": c_lw, "rw": c_rw,
                            "lh": c_lh, "rh": c_rh
                        }

                        # Check if core torso is sufficiently detected
                        core_conf = (c_ls + c_rs + c_lh + c_rh) / 4.0
                        if core_conf >= 0.20:
                            pose_detected = True
                            head_pos = (raw_nose_x, raw_nose_y)

                            # Filter Torso Anchors
                            clean_ls_x, clean_ls_y, _ = tracker.update_joint("ls", raw_ls_x, raw_ls_y, c_ls)
                            clean_rs_x, clean_rs_y, _ = tracker.update_joint("rs", raw_rs_x, raw_rs_y, c_rs)
                            clean_lh_x, clean_lh_y, _ = tracker.update_joint("lh", raw_lh_x, raw_lh_y, c_lh)
                            clean_rh_x, clean_rh_y, _ = tracker.update_joint("rh", raw_rh_x, raw_rh_y, c_rh)
                            clean_n_x, clean_n_y, _ = tracker.update_joint("nose", raw_nose_x, raw_nose_y, c_nose)

                            ls = (clean_ls_x, clean_ls_y)
                            rs = (clean_rs_x, clean_rs_y)
                            lh = (clean_lh_x, clean_lh_y)
                            rh = (clean_rh_x, clean_rh_y)
                            nose_pt = (clean_n_x, clean_n_y)

                            shoulder_dist = math.hypot(rs[0] - ls[0], rs[1] - ls[1])

                            # Filter Elbows
                            clean_le_x, clean_le_y, _ = tracker.update_joint(
                                "le", raw_le_x, raw_le_y, c_le,
                                shoulder_ref=ls, shoulder_width=shoulder_dist
                            )
                            clean_re_x, clean_re_y, _ = tracker.update_joint(
                                "re", raw_re_x, raw_re_y, c_re,
                                shoulder_ref=rs, shoulder_width=shoulder_dist
                            )
                            le = (clean_le_x, clean_le_y)
                            re = (clean_re_x, clean_re_y)

                            # Filter Wrists with Dynamic Anatomical Clamping & Forearm Kinematics
                            clean_lw_x, clean_lw_y, _ = tracker.update_joint(
                                "lw", raw_lw_x, raw_lw_y, c_lw,
                                shoulder_ref=ls, shoulder_width=shoulder_dist, elbow_ref=le
                            )
                            clean_rw_x, clean_rw_y, _ = tracker.update_joint(
                                "rw", raw_rw_x, raw_rw_y, c_rw,
                                shoulder_ref=rs, shoulder_width=shoulder_dist, elbow_ref=re
                            )
                            lw = (clean_lw_x, clean_lw_y)
                            rw = (clean_rw_x, clean_rw_y)

                            # 2. Calculate Scale-Invariant Biometrics
                            biometrics = normalizer.calculate_biometrics(
                                ls=ls, rs=rs, lh=lh, rh=rh,
                                le=le, re=re, lw=lw, rw=rw,
                                nose=nose_pt
                            )

                            # 3. Evaluate Phase 2 Gesture State Machine
                            current_kpts_dict = {
                                "ls": ls, "rs": rs, "lh": lh, "rh": rh,
                                "le": le, "re": re, "lw": lw, "rw": rw,
                                "nose": nose_pt
                            }
                            gesture_result = gesture_sm.update(
                                kpts=current_kpts_dict,
                                biometrics=biometrics,
                                is_tracking_valid=True
                            )

            # Update Tracker State Machine
            tracking_state = tracker.update_tracking_state(pose_detected, confidences)

            # Safe Fallback when LOST
            if tracking_state == TrackingState.LOST:
                ls = (0.42, 0.40)
                rs = (0.58, 0.40)
                lh = (0.45, 0.70)
                rh = (0.55, 0.70)
                le = (0.32, 0.42)
                re = (0.68, 0.42)
                lw = (0.22, 0.43)
                rw = (0.78, 0.43)
                nose_pt = (0.50, 0.26)
                biometrics = normalizer.calculate_biometrics(ls, rs, lh, rh, le, re, lw, rw, nose_pt)
                gesture_result = gesture_sm.update({}, biometrics, is_tracking_valid=False)

            # 4. Player Calibration Step (Phase 4)
            current_kpts = current_kpts_dict if pose_detected else None
            calib_state, calib_prog, calib_text = calibrator.update(biometrics, current_kpts)

            # 5. Mouth Aspect Ratio / Water Breath Tracker
            is_water_breathing = False
            mouth_score = 0.0
            if pose_detected and mouth_tracker.available:
                is_water_breathing, mouth_score, _ = mouth_tracker.process_crop(frame, head_pos)

            # 6. Telemetri UDP ke Unity (34-float CSV: Pose + Biometrik + Gestur Phase 2 + Kalibrasi Phase 4)
            udp_mouth_val = 1.0 if is_water_breathing else mouth_score
            tracking_state_float = 1.0 if tracking_state == TrackingState.TRACKED else (0.5 if tracking_state == TrackingState.DEGRADED else 0.0)

            # Map state to ID: 0=Glide, 1=Flap, 2=Dive, 3=Dash, 4=Hover, 5=GentleDescent, 6=FlyUp
            state_id_map = {
                GestureState.NEUTRAL_GLIDE.value: 0.0,
                GestureState.FLAPPING.value: 1.0,
                GestureState.TUCK_DIVE.value: 2.0,
                GestureState.PROPELLER_DASH.value: 3.0,
                GestureState.HOVER.value: 4.0,
                GestureState.GENTLE_DESCENT.value: 5.0,
                GestureState.FLY_UP.value: 6.0
            }
            active_id = state_id_map.get(gesture_result["active_state"], 0.0)

            # Body pitch decoupled orientation
            body_pitch = 0.0
            if biometrics is not None and nose_pt is not None:
                head_dist = biometrics["mid_shoulder"][1] - nose_pt[1]
                head_ratio = head_dist / max(0.05, biometrics["shoulder_width"])
                head_signal = np.clip((head_ratio - 0.48) / 0.14, -1.0, 1.0)
                if abs(head_signal) < 0.20:
                    head_signal = 0.0
                body_pitch = float(head_signal)

            sender.send_pose(
                ls=ls, rs=rs, lw=lw, rw=rw, lh=lh, rh=rh,
                mouth_open=udp_mouth_val,
                le=le, re=re,
                is_dive=1.0 if gesture_result["is_tuck_dive"] else 0.0,
                is_flap=1.0 if gesture_result["is_flapping"] else 0.0,
                flap_freq=gesture_result["flap_frequency"],
                flap_power=gesture_result["flap_power"],
                body_pitch=body_pitch,
                nose=nose_pt,
                wingspan_ratio=biometrics["wingspan_ratio"] if biometrics else 1.2,
                flap_height=biometrics["avg_flap_height"] if biometrics else 0.0,
                lean_angle_deg=biometrics["lean_angle_deg"] if biometrics else 0.0,
                tracking_state=tracking_state_float,
                is_dash=1.0 if gesture_result["is_propeller_dash"] else 0.0,
                dash_power=gesture_result["dash_power"],
                steering_input=gesture_result["steering_input"],
                active_state_id=active_id,
                calib_state_id=float(calib_state.value),
                calib_progress=float(calib_prog),
                is_hover=1.0 if gesture_result.get("is_hover", False) else 0.0,
                is_gentle_descent=1.0 if gesture_result.get("is_gentle_descent", False) else 0.0,
                is_fly_up=1.0 if gesture_result.get("is_fly_up", False) else 0.0,
                chest_elevation=biometrics["chest_elevation"] if biometrics else 1.55,
                forearm_flap_power=gesture_result.get("hover_power", 0.0)
            )

            # FPS calculation
            curr_time = time.time()
            dt = curr_time - prev_time
            prev_time = curr_time
            fps = 1.0 / dt if dt > 0 else 30.0
            fps_history.append(fps)
            if len(fps_history) > 30:
                fps_history.pop(0)
            avg_fps = sum(fps_history) / len(fps_history)

            # 7. Render CV Debug Visualization (Section 2.6 & Section 4.1)
            if not args.headless or video_sender is not None:
                draw_debug_overlay(
                    frame=frame,
                    all_kpts=kpts_raw,
                    tracker=tracker,
                    biometrics=biometrics,
                    fps=avg_fps,
                    latency_ms=latency_ms,
                    tracking_state=tracking_state,
                    gesture_result=gesture_result,
                    calib_state=calib_state,
                    calib_progress=calib_prog,
                    calib_text=calib_text
                )

            # Send Video Preview to Unity PIP (Port 5053)
            if video_sender is not None:
                video_sender.send_frame(frame)

            # Display GUI window if not headless
            if not args.headless:
                cv2.imshow("AR Dragon Sky Guardian - CV Debug Overlay (Phase 2)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    print("\n[*] Dihentikan oleh pengguna.")
                    break
                elif key == ord('c') or key == ord('C'):
                    calibrator.start_calibration()

    except KeyboardInterrupt:
        print("\n[*] Menghentikan Active CV Sender...")
    finally:
        cam.release()
        sender.close()
        if video_sender is not None:
            video_sender.close()
        if not args.headless:
            cv2.destroyAllWindows()
        print("[*] CV Pipeline dihentikan secara bersih.")


if __name__ == "__main__":
    main()
