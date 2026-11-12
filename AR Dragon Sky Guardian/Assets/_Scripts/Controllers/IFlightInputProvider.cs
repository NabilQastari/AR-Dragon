using UnityEngine;

namespace DragonWingAR.Controllers
{
    /// <summary>
    /// Struktur data perintah penerbangan standar (decoupled dari pose sensor).
    /// </summary>
    [System.Serializable]
    public struct FlightCommand
    {
        [Tooltip("Kemudi belok horizontal: -1.0 (Kiri) s/d +1.0 (Kanan)")]
        public float TurnInput;

        [Tooltip("Kendali pitch vertikal: -1.0 (Menukik) s/d +1.0 (Mendongak)")]
        public float PitchInput;

        [Tooltip("Orientasi condong badan: -1.0 s/d +1.0")]
        public float BodyPitch;

        [Tooltip("Status kepakan sayap ritmis (Fly Up + Speed Up)")]
        public bool IsFlapping;

        [Tooltip("Daya dorong kepakan (0.0 s/d 1.0)")]
        public float FlapPower;

        [Tooltip("Status menukik cepat aerodinamis (Tuck to Dive)")]
        public bool IsTuckDiving;

        [Tooltip("Intensitas menukik (0.0 s/d 1.0)")]
        public float DiveIntensity;

        [Tooltip("Status dorongan akselerasi rotasi lengan (Propeller Dash)")]
        public bool IsPropellerDash;

        [Tooltip("Kekuatan dorongan dash (0.0 s/d 1.0)")]
        public float DashPower;

        [Tooltip("Status meluncur jelajah santai (Glide)")]
        public bool IsGliding;

        [Tooltip("Status semburan air purba (Mouth Open / Hands Together)")]
        public bool IsWaterBreathing;

        [Tooltip("Status panggil hujan embun (Hands High Up)")]
        public bool IsHandsHighUp;

        [Tooltip("Status mode melayang di udara (Hover Mode - Upper arms tucked + forearm flap)")]
        public bool IsHover;

        [Tooltip("Daya pertahanan ketinggian hover lengan bawah (0.0 s/d 1.0)")]
        public float HoverPower;

        [Tooltip("Status luncuran maju lembut (Gentle Descent - Tucked T-Pose, no flapping)")]
        public bool IsGentleDescent;

        [Tooltip("Status terbang menanjak naik (Fly Up - Raised chest + full flapping)")]
        public bool IsFlyUp;

        [Tooltip("Elevasi dada relatif terhadap sumbu bahu")]
        public float ChestElevation;

        [Tooltip("ID State aktif dari gesture state machine (0=Glide, 1=Flap, 2=Dive, 3=Dash, 4=Hover, 5=GentleDescent, 6=FlyUp)")]
        public int ActiveStateId;
    }

    /// <summary>
    /// Antarmuka abstraksi penyedia perintah penerbangan.
    /// Memungkinkan Character Controller menerima input dari berbagai sumber (CV Pose, Input Mapper, Keyboard, Gamepad, atau AI).
    /// </summary>
    public interface IFlightInputProvider
    {
        FlightCommand GetFlightCommand();
    }
}
