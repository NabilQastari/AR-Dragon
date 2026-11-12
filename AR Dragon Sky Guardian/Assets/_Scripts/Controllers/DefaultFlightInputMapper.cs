using UnityEngine;
using DragonWingAR.CV;

namespace DragonWingAR.Controllers
{
    /// <summary>
    /// Sistem pemetaan input modular (Section 3.3).
    /// Menerjemahkan data pose dan gestur dari IPoseProvider menjadi FlightCommand yang bersih dan terstandar,
    /// memisahkan data sensor Computer Vision dari mekanisme pergerakan karakter.
    /// </summary>
    [DisallowMultipleComponent]
    public class DefaultFlightInputMapper : MonoBehaviour, IFlightInputProvider
    {
        [Header("Sumber Pose Provider")]
        [Tooltip("Komponen penyedia data pose (UDPPoseReceiver atau mock provider)")]
        [SerializeField] private MonoBehaviour poseProviderSource;
        private IPoseProvider _poseProvider;

        [Header("Sensitivitas & Deadzone")]
        [Tooltip("Pengali sensitivitas belok kemudi")]
        [Range(0.5f, 2.5f)]
        public float turnSensitivity = 1.0f;

        [Tooltip("Zona mati belok tambahan jika diperlukan")]
        public float turnDeadzone = 0.02f;

        [Header("Adaptasi Kenyamanan & Kelelahan (Phase 4: Comfort & Fatigue)")]
        [Tooltip("Kurva kemudi non-linear (1.0 = linear, 1.35 = smooth micro-steer)")]
        [Range(1.0f, 2.0f)]
        public float steeringEasePower = 1.35f;

        [Tooltip("Pengali kenyamanan kepakan (mencegah kelelahan tangan berlebih)")]
        [Range(0.8f, 1.5f)]
        public float flapComfortMultiplier = 1.15f;

        [Header("Status Perintah Terakhir (Read Only)")]
        [SerializeField] private FlightCommand _lastCommand;

        public FlightCommand CurrentCommand => _lastCommand;

        private void Awake()
        {
            ResolvePoseProvider();
        }

        private void ResolvePoseProvider()
        {
            if (poseProviderSource is IPoseProvider provider)
            {
                _poseProvider = provider;
            }
            else
            {
                _poseProvider = GetComponent<IPoseProvider>() ?? FindFirstObjectByType<UDPPoseReceiver>();
            }
        }

        public FlightCommand GetFlightCommand()
        {
            if (_poseProvider == null)
            {
                ResolvePoseProvider();
                if (_poseProvider == null)
                {
                    _lastCommand = new FlightCommand
                    {
                        IsGliding = true
                    };
                    return _lastCommand;
                }
            }

            // 1. Pemetaan Kemudi Belok Adaptif
            float rawTurn = _poseProvider.TurnInput;
            float mappedTurn = 0f;
            if (Mathf.Abs(rawTurn) > turnDeadzone)
            {
                float sign = Mathf.Sign(rawTurn);
                float effective = (Mathf.Abs(rawTurn) - turnDeadzone) / (1.0f - turnDeadzone);
                float curved = Mathf.Pow(Mathf.Clamp01(effective), steeringEasePower);
                mappedTurn = Mathf.Clamp(sign * curved * turnSensitivity, -1f, 1f);
            }

            // 2. Pemetaan Status Gestur
            bool isHover = _poseProvider.IsHover;
            bool isGentle = _poseProvider.IsGentleDescent;
            bool isFlyUp = _poseProvider.IsFlyUp;
            bool isDive = _poseProvider.IsTuckDive && !isHover && !isGentle;
            bool isDash = _poseProvider.IsPropellerDash && !isHover && !isGentle;
            bool isFlap = _poseProvider.IsFlapping && !isDive && !isDash && !isHover && !isGentle;
            bool isGlide = !isDive && !isDash && !isFlap && !isHover && !isGentle && !isFlyUp;

            _lastCommand = new FlightCommand
            {
                TurnInput = mappedTurn,
                PitchInput = _poseProvider.PitchInput,
                BodyPitch = _poseProvider.BodyPitch,
                IsFlapping = isFlap,
                FlapPower = isFlap ? Mathf.Clamp01(_poseProvider.FlapPower * flapComfortMultiplier) : 0f,
                IsTuckDiving = isDive,
                DiveIntensity = isDive ? 1.0f : 0f,
                IsPropellerDash = isDash,
                DashPower = isDash ? Mathf.Clamp01(_poseProvider.DashPower) : 0f,
                IsGliding = isGlide,
                IsHover = isHover,
                HoverPower = isHover ? Mathf.Clamp01(_poseProvider.ForearmFlapPower) : 0f,
                IsGentleDescent = isGentle,
                IsFlyUp = isFlyUp,
                ChestElevation = _poseProvider.ChestElevation,
                ActiveStateId = _poseProvider.ActiveStateId,
                IsWaterBreathing = _poseProvider.IsWaterBreathing,
                IsHandsHighUp = _poseProvider.IsHandsHighUp
            };

            return _lastCommand;
        }
    }
}
