"""
test_send_dummy_udp.py
Skrip pengujian transmisi data sintetis (dummy) ke Unity via UDP port 5052.
Berguna untuk memverifikasi penerimaan data di Unity tanpa perlu membuka webcam.
"""

import time
import math
from udp_sender import PoseUDPSender

def main():
    print("=" * 60)
    print("🚀 PENGIRIM PAKET UDP SINTETIS (TEST BENCH)")
    print("   - Target : 127.0.0.1:5052")
    print("   - Pola   : Osilasi Belok Kiri/Kanan, Kepakan Sayap, & Buka Mulut")
    print("   - Tekan Ctrl+C untuk berhenti")
    print("=" * 60)

    sender = PoseUDPSender(ip="127.0.0.1", port=5052)
    t = 0.0

    try:
        while True:
            t += 0.05

            # Bahu statis
            ls = (0.40, 0.40)
            rs = (0.60, 0.40)
            lh = (0.42, 0.70)
            rh = (0.58, 0.70)

            # Osilasi pergelangan tangan (Simulasi belok & kepakan sayap)
            wing_wave = math.sin(t * 3.0) * 0.25  # Naik turun di atas & bawah bahu
            tilt_wave = math.cos(t * 1.5) * 0.15  # Miring kiri & kanan

            lw = (0.30, 0.40 + wing_wave + tilt_wave)
            rw = (0.70, 0.40 + wing_wave - tilt_wave)

            # Simulasi buka mulut secara periodik
            mouth = 1.0 if (math.sin(t * 1.0) > 0.6) else 0.0

            sender.send_pose(ls, rs, lw, rw, lh, rh, mouth_open=mouth)

            # Print status ke terminal setiap ~0.5 detik
            if int(t * 20) % 10 == 0:
                tilt_dir = "BELOK KANAN" if (lw[1] > rw[1]) else "BELOK KIRI"
                flap_dir = "DI ATAS BAHU" if (lw[1] < ls[1] and rw[1] < rs[1]) else "DI BAWAH BAHU"
                print(f"[*] Mengirim -> Kemudi: {tilt_dir} | Sayap: {flap_dir} | Mulut: {'BUKA' if mouth > 0.5 else 'TUTUP'}")

            time.sleep(0.033) # ~30 FPS
    except KeyboardInterrupt:
        print("\n[*] Pengujian UDP dihentikan.")
    finally:
        sender.close()

if __name__ == "__main__":
    main()
