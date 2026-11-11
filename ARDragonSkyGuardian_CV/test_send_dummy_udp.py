"""
test_send_dummy_udp.py
Skrip pengujian transmisi data sintetis (dummy) ke Unity via UDP port 5052 (Pose) & 5053 (Video PIP).
Mensimulasikan 4 mode Minecraft Elytra:
1. POSE T: Meluncur maju dengan sedikit dive (-5 deg)
2. FLAPPING: Mengepakkan tangan (Fly Up + Speed Up)
3. TUCK DIVE: Pose foto pengguna (tangan di dada, siku ke bawah -> Dive terjun kecepatan tinggi)
4. POSE Y / CLIMB: Badan mengarah ke atas (Zoom climb)
"""

import time
import math
import cv2
import numpy as np
from udp_sender import PoseUDPSender, VideoUDPSender

def main():
    print("=" * 65)
    print("🚀 PENGIRIM PAKET UDP SINTETIS (MINECRAFT ELYTRA DYNAMICS)")
    print("   - Target Pose UDP : 127.0.0.1:5052 (CSV 21 Float)")
    print("   - Target Video PIP: 127.0.0.1:5053 (JPEG Frame)")
    print("   - Siklus: T-Pose -> Flapping -> Tuck Dive -> Pose Y Climb")
    print("   - Tekan Ctrl+C untuk berhenti")
    print("=" * 65)

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    video_sender = VideoUDPSender(ip="127.0.0.1", port=5053, width=320, height=180)
    t = 0.0

    vw, vh = 320, 180

    try:
        while True:
            t += 0.05
            cycle = t % 16.0  # 4 fase per 4 detik

            # Bahu & Pinggul statis
            ls = (0.40, 0.38)
            rs = (0.60, 0.38)
            lh = (0.44, 0.72)
            rh = (0.56, 0.72)

            tilt_wave = math.cos(t * 1.5) * 0.08  # Kemiringan belok kiri-kanan
            is_dive = 0.0
            is_flap = 0.0
            flap_freq = 0.0
            flap_power = 0.0

            if cycle < 4.0:
                # 1. POSE T (Elytra Glide, tangan merentang mendatar)
                mode_name = "POSE T (ELYTRA GLIDE ~ -5°)"
                mode_color = (255, 220, 60)
                le = (0.28, 0.40 + tilt_wave * 0.5)
                re = (0.72, 0.40 - tilt_wave * 0.5)
                lw = (0.16, 0.41 + tilt_wave)
                rw = (0.84, 0.41 - tilt_wave)

            elif cycle < 8.0:
                # 2. FLAPPING (Mengepakkan tangan: Fly Up + Speed Up)
                mode_name = "KEPAK SAYAP (FLY UP + SPEED UP)"
                mode_color = (0, 255, 120)
                flap_osc = math.sin(t * 12.0) * 0.22  # Frekuensi cepat ~2 Hz
                le = (0.30, 0.42 + flap_osc * 0.5)
                re = (0.70, 0.42 + flap_osc * 0.5)
                lw = (0.20, 0.40 + flap_osc)
                rw = (0.80, 0.40 + flap_osc)
                is_flap = 1.0
                flap_freq = 2.0
                flap_power = 0.85

            elif cycle < 12.0:
                # 3. TUCK DIVE (Foto Pengguna: tangan mengepal di dada, siku ke bawah)
                mode_name = "TUCK DIVE (DIVE TERJUN CEPAT ↓↓)"
                mode_color = (0, 100, 255)
                # Siku di bawah bahu dan pergelangan tangan
                le = (0.32, 0.55)
                re = (0.68, 0.55)
                # Tangan mengepal di dada atas
                lw = (0.42, 0.42)
                rw = (0.58, 0.42)
                is_dive = 1.0

            else:
                # 4. POSE Y / CLIMB (Tangan diangkat ke atas -> Mengarahkan hidung ke atas)
                mode_name = "ARAH ATAS (CLIMB SOARING ↑)"
                mode_color = (0, 255, 220)
                le = (0.30, 0.28 + tilt_wave * 0.5)
                re = (0.70, 0.28 - tilt_wave * 0.5)
                lw = (0.22, 0.16 + tilt_wave)
                rw = (0.78, 0.16 - tilt_wave)

            mouth = 1.0 if (math.sin(t * 0.8) > 0.7) else 0.0

            # 1. Kirim pose CSV ke Unity (21 float)
            sender.send_pose(
                ls, rs, lw, rw, lh, rh,
                mouth_open=mouth,
                le=le, re=re,
                is_dive=is_dive,
                is_flap=is_flap,
                flap_freq=flap_freq,
                flap_power=flap_power
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

            hand_col = (0, 100, 255) if is_dive > 0.5 else ((0, 255, 0) if is_flap > 0.5 else (0, 255, 240))
            cv2.circle(canvas, p_lw, 7, hand_col, -1)
            cv2.circle(canvas, p_rw, 7, hand_col, -1)
            cv2.circle(canvas, p_le, 5, (255, 180, 0), -1)
            cv2.circle(canvas, p_re, 5, (255, 180, 0), -1)

            # Kepala
            head_x, head_y = int(vw * 0.5), int(vh * 0.24)
            cv2.circle(canvas, (head_x, head_y), 13, (255, 230, 100), 2)
            if mouth > 0.5:
                cv2.circle(canvas, (head_x, head_y + 4), 5, (255, 200, 0), -1)

            # Label overlay
            cv2.putText(canvas, mode_name, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, mode_color, 1)

            video_sender.send_frame(canvas)
            time.sleep(0.04)

    except KeyboardInterrupt:
        print("\n[*] Synthetic sender dihentikan.")
    finally:
        sender.close()
        video_sender.close()

if __name__ == "__main__":
    main()
