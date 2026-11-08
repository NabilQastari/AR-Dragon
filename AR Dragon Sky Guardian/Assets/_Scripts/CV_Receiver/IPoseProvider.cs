using UnityEngine;

namespace DragonWingAR.CV
{
    /// <summary>
    /// Kontrak antarmuka penyedia data pose dan telemetri gestur pemain.
    /// Memungkinkan komponen game (seperti DragonFlightController dan VillageZoneController)
    /// mengakses koordinat smoothed maupun status gestur tanpa bergantung langsung pada UDP socket.
    /// </summary>
    public interface IPoseProvider
    {
        // ==========================================
        // Status Koneksi & Deteksi
        // ==========================================
        bool IsConnected { get; }
        bool IsPoseDetected { get; }

        // ==========================================
        // Koordinat Sendi Ternormalisasi (0.0 - 1.0)
        // (0,0) di kiri atas layar, (1,1) di kanan bawah layar
        // ==========================================
        Vector2 LeftShoulder { get; }
        Vector2 RightShoulder { get; }
        Vector2 LeftWrist { get; }
        Vector2 RightWrist { get; }
        Vector2 LeftHip { get; }
        Vector2 RightHip { get; }

        // ==========================================
        // Semburan Air & Mulut
        // ==========================================
        float MouthOpen { get; }            // 0.0f (tertutup) s/d 1.0f (terbuka penuh)
        bool IsWaterBreathing { get; }      // True jika mulut terbuka lebar atau gestur rapat tangan aktif

        // ==========================================
        // Kemudi Terbang & Ketinggian Vertikal (Pose Alfabet: Y - T - A)
        // ==========================================
        float TurnInput { get; }            // -1.0f (belok kiri tajam) s/d +1.0f (belok kanan tajam)
        float PitchInput { get; }           // -1.0f (Pose A: Turun) s/d +1.0f (Pose Y: Naik)
        bool IsYPose { get; }               // Pose "Y": Kedua tangan diangkat ke atas diagonal -> NAIK
        bool IsTPose { get; }               // Pose "T": Kedua tangan mendatar sejajar bahu -> LURUS MENDATAR
        bool IsAPose { get; }               // Pose "A": Kedua tangan menyerong ke bawah paha -> TURUN
        bool IsDiving { get; }              // Kompatibilitas alias untuk IsAPose

        // ==========================================
        // Status Gestur Pemulihan Desa
        // ==========================================
        bool IsFlapping { get; }            // Desa 1: Kepakan sayap aktif
        bool IsHandsTogether { get; }       // Desa 2 (Alternatif): Tangan rapat di depan dada
        bool IsHandsHighUp { get; }         // Desa 3: Kedua tangan diangkat tinggi di atas kepala
    }
}
