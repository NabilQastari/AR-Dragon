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
        Vector2 LeftElbow { get; }
        Vector2 RightElbow { get; }
        Vector2 LeftHip { get; }
        Vector2 RightHip { get; }

        // ==========================================
        // Semburan Air & Mulut
        // ==========================================
        float MouthOpen { get; }            // 0.0f (tertutup) s/d 1.0f (terbuka penuh)
        bool IsWaterBreathing { get; }      // True jika mulut terbuka lebar atau gestur rapat tangan aktif

        // ==========================================
        // Kemudi Terbang & Minecraft Elytra Dynamics
        // ==========================================
        float TurnInput { get; }            // -1.0f (belok kiri tajam) s/d +1.0f (belok kanan tajam)
        float PitchInput { get; }           // -1.0f (Turun/Dive) s/d +1.0f (Naik/Climb)
        float BodyPitch { get; }            // -1.0f (Badan condong/arah bawah) s/d +1.0f (Badan condong/arah atas), 0.0f = netral mendatar
        bool IsYPose { get; }               // Pose "Y": Kedua tangan diangkat ke atas diagonal -> Arahkan badan ke atas (Climb)
        bool IsTPose { get; }               // Pose "T": Kedua tangan mendatar sejajar bahu -> Meluncur maju sedikit dive (-5 deg)
        bool IsAPose { get; }               // Pose "A": Kedua tangan menyerong ke paha -> Turun meluncur
        bool IsTuckDive { get; }            // Pose Gambar: Tangan mengepal di dada, siku ke bawah -> Dive terjun kecepatan tinggi (-45 deg)
        bool IsDiving { get; }              // Kompatibilitas alias untuk IsTuckDive || IsAPose

        // ==========================================
        // Dinamika Kepakan Sayap (Fly Up + Speed Up) & Gestur Desa
        // ==========================================
        bool IsFlapping { get; }            // Mengepakkan tangan -> Fly Up + Speed Up
        float FlapPower { get; }            // Kekuatan daya dorong kepakan (0.0 - 1.0)
        bool IsHandsTogether { get; }       // Desa 2 (Alternatif): Tangan rapat di depan dada
        bool IsHandsHighUp { get; }         // Desa 3: Kedua tangan diangkat tinggi di atas kepala

        // ==========================================
        // Biometrik Ternormalisasi Phase 1 (Scale & Distance Invariant)
        // ==========================================
        float WingspanRatio { get; }        // Rasio bentang tangan terhadap lebar bahu (~1.2 rest, >2.4 T-Pose)
        float FlapHeightRatio { get; }      // Rasio tinggi tangan relatif terhadap bahu dinormalisasi torso length
        float LeanAngleDeg { get; }         // Sudut kemiringan torso tulang belakang dalam derajat (-30 s/d +30)
        float TrackingStateValue { get; }   // 1.0 = TRACKED, 0.5 = DEGRADED, 0.0 = LOST

        // ==========================================
        // Gesture Recognition Phase 2 (Propeller Dash & Continuous Motion)
        // ==========================================
        bool IsPropellerDash { get; }       // Rotasi lengan kontinu / Propeller Dash
        float DashPower { get; }            // Kekuatan dorongan dash (0.0 - 1.0)

        // ==========================================
        // Kalibrasi Pemain & Adaptive Control Phase 4
        // ==========================================
        int CalibrationStateId { get; }      // 0=Idle, 1=Neutral, 2=TPose, 3=LeanL, 4=LeanR, 5=Complete
        float CalibrationProgress { get; }   // 0.0f - 1.0f
        bool IsCalibrated { get; }           // True jika kalibrasi personal telah selesai

        // ==========================================
        // Fitur Tambahan Kontrol Terbang: Fly Up, Hover & Gentle Descent
        // ==========================================
        bool IsHover { get; }                // True: Upper arms tucked + forearm flapping (Hover di udara)
        bool IsGentleDescent { get; }        // True: Upper arms tucked + forearms extended (Tucked T-Pose, no flapping)
        bool IsFlyUp { get; }                // True: Chest elevated + active flapping (Menanjak ke atas)
        float ChestElevation { get; }        // Rasio elevasi dada (dy_spine / shoulder_width)
        float ForearmFlapPower { get; }      // Kekuatan kepakan lengan bawah (0.0 - 1.0)
        int ActiveStateId { get; }           // 0=Glide, 1=Flap, 2=Dive, 3=Dash, 4=Hover, 5=GentleDescent, 6=FlyUp
    }
}
