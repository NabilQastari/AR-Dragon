"""
test_send_dummy_udp.py
Skrip pengujian transmisi data sintetis (dummy) ke Unity via UDP port 5052 (Pose) & 5053 (Video PIP).
Mensimulasikan 5 mode mekanik Sky Peck (Phase 2):
1. GLIDE (0-4s): Tangan merentang mendatar, jelajah stabil dengan sink rate alami
2. FLAP TO CLIMB (4-8s): Mengepakkan tangan naik-turun -> Daya angkat vertikal mendaki
3. TUCK TO DIVE (8-12s): Tangan di dada, siku ke bawah -> Menukik curam kecepatan tinggi
4. PROPELLER DASH (12-16s): Rotasi orbital pergelangan tangan kontinu -> Dorongan dash maju
5. SWOOP CLIMB & LEAN (16-20s): Buka sayap setelah dive -> Melambung naik (Swoop) + Lean to Bank Turn
"""

import time
import math
import cv2
import numpy as np
from udp_sender import PoseUDPSender, VideoUDPSender

def main():
    print("=" * 70)
    print("🚀 PENGIRIM PAKET UDP SINTETIS (PHASE 2 GESTURE STATE MACHINE)")
    print("   - Target Pose UDP : 127.0.0.1:5052 (CSV 32 Float)")
    print("   - Target Video PIP: 127.0.0.1:5053 (JPEG Frame)")
    print("   - Siklus: Glide -> Flap -> Tuck Dive -> Propeller Dash -> Lean Turn")
    print("   - Tekan Ctrl+C untuk berhenti")
    print("=" * 70)

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    video_sender = VideoUDPSender(ip="127.0.0.1", port=5053, width=320, height=180)
    t = 0.0

    vw, vh = 320, 180

    try:
        while True:
            t += 0.05
            cycle = t % 20.0  # 5 fase x 4 detik

            # Bahu & Pinggul dasar
            ls = [0.40, 0.38]
            rs = [0.60, 0.38]
            lh = [0.44, 0.72]
            rh = [0.56, 0.72]

            tilt_wave = math.cos(t * 1.5) * 0.08
            is_dive = 0.0
            is_flap = 0.0
            is_dash = 0.0
            flap_freq = 0.0
            flap_power = 0.0
            dash_power = 0.0
            steering_input = 0.0
            active_state_id = 0.0  # 0=Glide, 1=Flap, 2=Dive, 3=Dash

            if cycle < 4.0:
                # 1. GLIDE (Sayap terbentang mendatar, meluncur stabil)
                mode_name = "SKY PECK: GLIDE (Meluncur Jelajah)"
                mode_color = (255, 220, 60)
                le = (0.28, 0.40)
                re = (0.72, 0.40)
                lw = (0.16, 0.41)
                rw = (0.84, 0.41)
                active_state_id = 0.0

            elif cycle < 8.0:
                # 2. FLAP TO CLIMB (Mengepakkan tangan: daya angkat vertikal naik)
                mode_name = "SKY PECK: FLAP TO CLIMB ↑ (Mendaki Vertikal)"
                mode_color = (0, 255, 120)
                flap_osc = math.sin(t * 12.0) * 0.20
                le = (0.30, 0.42 + flap_osc * 0.5)
                re = (0.70, 0.42 + flap_osc * 0.5)
                lw = (0.20, 0.40 + flap_osc)
                rw = (0.80, 0.40 + flap_osc)
                is_flap = 1.0
                flap_freq = 2.2
                flap_power = 0.88
                active_state_id = 1.0

            elif cycle < 12.0:
                # 3. TUCK TO DIVE (Tangan mengepal rapat di dada, siku ke bawah)
                mode_name = "SKY PECK: TUCK DIVE ↓↓ (Menukik Cepat)"
                mode_color = (0, 100, 255)
                le = (0.34, 0.56)
                re = (0.66, 0.56)
                lw = (0.43, 0.43)
                rw = (0.57, 0.43)
                is_dive = 1.0
                active_state_id = 2.0

            elif cycle < 16.0:
                # 4. PROPELLER DASH (Rotasi orbital tangan berputar kontinu)
                mode_name = "SKY PECK: PROPELLER DASH ⚡ (Dorongan Cepat)"
                mode_color = (255, 180, 0)
                rot_angle = t * 15.0  # ~2.4 rotasi per detik
                radius = 0.12
                le = (0.30, 0.42)
                re = (0.70, 0.42)
                lw = (0.30 + math.cos(rot_angle) * radius, 0.42 + math.sin(rot_angle) * radius)
                rw = (0.70 + math.cos(rot_angle + math.pi) * radius, 0.42 + math.sin(rot_angle + math.pi) * radius)
                is_dash = 1.0
                dash_power = 0.95
                active_state_id = 3.0

            else:
                # 5. SWOOP CLIMB OUT OF DIVE & LEAN TO TURN
                lean_offset = 0.06 * math.sin(t * 2.0)
                ls[0] += lean_offset
                rs[0] += lean_offset
                mode_name = "SKY PECK: SWOOP CLIMB ↑ + LEAN TURN"
                mode_color = (0, 255, 220)
                le = (0.28 + lean_offset, 0.38 + tilt_wave * 0.5)
                re = (0.72 + lean_offset, 0.38 - tilt_wave * 0.5)
                lw = (0.16 + lean_offset, 0.39 + tilt_wave)
                rw = (0.84 + lean_offset, 0.39 - tilt_wave)
                steering_input = float(np.clip(lean_offset * 12.0, -1.0, 1.0))
                active_state_id = 0.0

            mouth = 1.0 if (math.sin(t * 0.8) > 0.75) else 0.0

            # 1. Kirim pose CSV ke Unity (32 float)
            sender.send_pose(
                (ls[0], ls[1]), (rs[0], rs[1]),
                lw, rw,
                (lh[0], lh[1]), (rh[0], rh[1]),
                mouth_open=mouth,
                le=le, re=re,
                is_dive=is_dive,
                is_flap=is_flap,
                flap_freq=flap_freq,
                flap_power=flap_power,
                body_pitch=(1.0 if (cycle >= 16.0 or (4.0 <= cycle < 8.0)) else (-1.0 if (8.0 <= cycle < 12.0) else 0.0)),
                nose=(0.50 + (ls[0] - 0.40), 0.24),
                wingspan_ratio=math.hypot(rw[0]-lw[0], rw[1]-lw[1]) / 0.20,
                flap_height=(ls[1]-lw[1]) / 0.32,
                lean_angle_deg=steering_input * 18.0,
                tracking_state=1.0,
                is_dash=is_dash,
                dash_power=dash_power,
                steering_input=steering_input,
                active_state_id=active_state_id,
                calib_state_id=5.0,
                calib_progress=1.0
            )

            # 2. Gambar frame sintetis untuk video PIP port 5053
            canvas = np.zeros((vh, vw, 3), dtype=np.uint8)
            for y_line in range(vh):
                canvas[y_line, :] = (int(15 + y_line * 0.1), int(20 + y_line * 0.08), int(35 + y_line * 0.15))

            def to_px(pt):
                return (int(pt[0] * vw), int(pt[1] * vh))

            p_ls, p_rs = to_px(ls), to_px(rs)
            p_le, p_re = to_px(le), to_px(re)
            p_lw, p_rw = to_px(lw), to_px(rw)
            p_lh, p_rh = to_px(lh), to_px(rh)

            # Gambar sendi & tulang
            bone_col = (0, 255, 200)
            cv2.line(canvas, p_ls, p_rs, bone_col, 2)
            cv2.line(canvas, p_ls, p_le, bone_col, 2)
            cv2.line(canvas, p_le, p_lw, bone_col, 2)
            cv2.line(canvas, p_rs, p_re, bone_col, 2)
            cv2.line(canvas, p_re, p_rw, bone_col, 2)
            cv2.line(canvas, p_ls, p_lh, bone_col, 2)
            cv2.line(canvas, p_rs, p_rh, bone_col, 2)
            cv2.line(canvas, p_lh, p_rh, bone_col, 2)

            hand_col = (255, 180, 0) if is_dash > 0.5 else ((0, 100, 255) if is_dive > 0.5 else ((0, 255, 0) if is_flap > 0.5 else (0, 255, 240)))
            cv2.circle(canvas, p_lw, 7, hand_col, -1)
            cv2.circle(canvas, p_rw, 7, hand_col, -1)

            cv2.putText(canvas, mode_name, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.40, mode_color, 1, cv2.LINE_AA)
            video_sender.send_frame(canvas)
            time.sleep(0.04)

    except KeyboardInterrupt:
        print("\n[*] Dummy Sender dihentikan.")
    finally:
        sender.close()
        video_sender.close()

if __name__ == "__main__":
    main()
