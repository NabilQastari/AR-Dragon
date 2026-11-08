"""
test_send_dummy_udp.py
Skrip pengujian transmisi data sintetis (dummy) ke Unity via UDP port 5052 (Pose) & 5053 (Video PIP).
Berguna untuk memverifikasi penerimaan data di Unity tanpa perlu membuka webcam sungguhan.
"""

import time
import math
import cv2
import numpy as np
from udp_sender import PoseUDPSender, VideoUDPSender

def main():
    print("=" * 65)
    print("🚀 PENGIRIM PAKET UDP SINTETIS (TEST BENCH)")
    print("   - Target Pose UDP : 127.0.0.1:5052 (13 Float CSV)")
    print("   - Target Video PIP: 127.0.0.1:5053 (Synthetic Frame JPEG)")
    print("   - Pola Animasi    : Osilasi Belok, Kepakan Sayap, & Buka Mulut")
    print("   - Tekan Ctrl+C untuk berhenti")
    print("=" * 65)

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    video_sender = VideoUDPSender(ip="127.0.0.1", port=5053, width=320, height=180)
    t = 0.0

    # Canvas sintetis 320x180
    vw, vh = 320, 180

    try:
        while True:
            t += 0.05

            # Bahu statis
            ls = (0.40, 0.42)
            rs = (0.60, 0.42)
            lh = (0.44, 0.72)
            rh = (0.56, 0.72)

            # Osilasi pergelangan tangan (Simulasi belok & kepakan sayap)
            wing_wave = math.sin(t * 3.0) * 0.22  # Naik turun di atas & bawah bahu
            tilt_wave = math.cos(t * 1.5) * 0.14  # Miring kiri & kanan

            lw = (0.28, 0.42 + wing_wave + tilt_wave)
            rw = (0.72, 0.42 + wing_wave - tilt_wave)

            # Simulasi buka mulut secara periodik
            mouth = 1.0 if (math.sin(t * 1.0) > 0.6) else 0.0

            # 1. Kirim pose ke port 5052
            sender.send_pose(ls, rs, lw, rw, lh, rh, mouth_open=mouth)

            # 2. Gambar frame sintetis untuk port 5053
            canvas = np.zeros((vh, vw, 3), dtype=np.uint8)
            # Gradasi background biru gelap
            for y_line in range(vh):
                canvas[y_line, :] = (int(15 + y_line * 0.1), int(20 + y_line * 0.08), int(35 + y_line * 0.15))

            def to_px(pt):
                return (int(pt[0] * vw), int(pt[1] * vh))

            p_ls, p_rs = to_px(ls), to_px(rs)
            p_lw, p_rw = to_px(lw), to_px(rw)
            p_lh, p_rh = to_px(lh), to_px(rh)

            # Gambar kerangka sintetis
            cv2.line(canvas, p_ls, p_rs, (0, 255, 200), 2)
            cv2.line(canvas, p_ls, p_lw, (0, 255, 200), 2)
            cv2.line(canvas, p_rs, p_rw, (0, 255, 200), 2)
            cv2.line(canvas, p_ls, p_lh, (0, 255, 200), 2)
            cv2.line(canvas, p_rs, p_rh, (0, 255, 200), 2)
            cv2.line(canvas, p_lh, p_rh, (0, 255, 200), 2)

            is_above = (lw[1] < ls[1]) and (rw[1] < rs[1])
            hand_col = (0, 255, 0) if is_above else (255, 60, 180)
            cv2.circle(canvas, p_lw, 7, hand_col, -1)
            cv2.circle(canvas, p_rw, 7, hand_col, -1)

            # Kepala & mulut
            head_x, head_y = int(vw * 0.5), int(vh * 0.28)
            cv2.circle(canvas, (head_x, head_y), 14, (255, 230, 100), 2)
            if mouth > 0.5:
                cv2.circle(canvas, (head_x, head_y + 4), 6, (0, 200, 255), -1)

            # Label status
            cv2.putText(canvas, "TEST DUMMY VIDEO [UDP:5053]", (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 255), 1)
            tilt_lbl = "BELOK KANAN" if (lw[1] > rw[1]) else "BELOK KIRI"
            cv2.putText(canvas, f"STATUS: {tilt_lbl}", (10, 168), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 100), 1)

            # Kirim frame sintetis
            video_sender.send_frame(canvas)

            # Print status ke terminal setiap ~0.5 detik
            if int(t * 20) % 10 == 0:
                flap_dir = "DI ATAS BAHU" if is_above else "DI BAWAH BAHU"
                print(f"[*] Mengirim -> Kemudi: {tilt_lbl} | Sayap: {flap_dir} | Mulut: {'BUKA' if mouth > 0.5 else 'TUTUP'}")

            time.sleep(0.033) # ~30 FPS
    except KeyboardInterrupt:
        print("\n[*] Pengujian UDP dihentikan.")
    finally:
        sender.close()
        video_sender.close()

if __name__ == "__main__":
    main()
