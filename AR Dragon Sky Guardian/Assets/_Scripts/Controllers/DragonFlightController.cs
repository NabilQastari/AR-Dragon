using UnityEngine;
using DragonWingAR.CV;

namespace DragonWingAR.Controllers
{
    /// <summary>
    /// Pengendali penerbangan naga Sky Peck (Phase 3 Upgrade):
    /// 1. Flap to Climb: Mengepakkan tangan secara fisik mengangkat naga naik (climb) dan menambah dorongan maju.
    /// 2. Lean to Bank/Turn: Condongkan tubuh untuk berbelok (yaw) dan memiringkan sayap (roll banking) secara kontinu.
    /// 3. Tuck to Dive: Merapatkan tangan ke dada membuat naga menukik tajam (pitch -40 deg) berkecepatan tinggi hingga 28 m/s.
    /// 4. Propeller Dash: Rotasi lengan kontinu menghasilkan dorongan kecepatan impulsif (dash) hingga 26 m/s.
    /// 5. Swoop Climb Out of Dive: Membuka sayap setelah dive mengonversi kelebihan kecepatan kinetik menjadi luncuran melambung naik (swoop soaring).
    /// 6. Glide: Meluncur anggun dengan sink rate alami (-1.0 m/s) pada kecepatan jelajah stabil saat tangan direntangkan.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class DragonFlightController : MonoBehaviour
    {
        [Header("Referensi Input Mapper & Pose Provider")]
        [Tooltip("Komponen pemeta input modular (IFlightInputProvider). Kosongkan untuk deteksi otomatis.")]
        [SerializeField] private MonoBehaviour flightInputSource;
        private IFlightInputProvider _flightInputProvider;
        private IPoseProvider _directPoseProvider;

        [Header("Kecepatan & Fisika Terbang (Sky Peck Dynamics)")]
        [Tooltip("Kecepatan jelajah meluncur normal (m/s)")]
        public float cruiseSpeed = 14f;

        [Tooltip("Kecepatan stall minimum (m/s)")]
        public float minSpeed = 7f;

        [Tooltip("Kecepatan maksimum saat dive menukik (m/s)")]
        public float maxDiveSpeed = 28f;

        [Tooltip("Kecepatan dorongan maksimum saat Propeller Dash (m/s)")]
        public float maxDashSpeed = 26f;

        [Tooltip("Laju turun alami saat meluncur santai / Glide Sink Rate (m/s)")]
        public float glideSinkRate = 1.0f;

        [Header("Mekanik Kepakan (Flap to Climb)")]
        [Tooltip("Kekuatan daya angkat vertikal saat mengepak (m/s)")]
        public float flapLiftPower = 6.0f;

        [Tooltip("Daya dorong maju tambahan saat mengepak (m/s^2)")]
        public float flapThrustAccel = 12f;

        [Tooltip("Kecepatan maksimum dorongan kepakan di bidang datar")]
        public float maxFlapSpeed = 21f;

        [Header("Mekanik Menukik & Dash (Dive, Dash & Swoop)")]
        [Tooltip("Akselerasi gravitasi saat sayap dilipat / dive (m/s^2)")]
        public float diveAcceleration = 18f;

        [Tooltip("Sudut pitch menukik saat tangan ditekuk ke dada (derajat)")]
        public float tuckDivePitch = -40f;

        [Tooltip("Akselerasi dorongan maju saat Propeller Dash (m/s^2)")]
        public float dashThrustAccel = 22f;

        [Tooltip("Efisiensi konversi kecepatan dive menjadi kenaikan ketinggian (Swoop Climb)")]
        [Range(0.4f, 1.0f)]
        public float swoopEfficiency = 0.85f;

        [Header("Mekanik Kemudi & Kemiringan Tubuh (Continuous Lean)")]
        [Tooltip("Kecepatan belok kompas (Yaw deg/s) saat condong maksimal")]
        public float yawTurnSpeed = 72f;

        [Tooltip("Sudut kemiringan sayap (Roll Banking) saat belok tajam (derajat)")]
        public float maxRollAngle = 38f;

        [Tooltip("Kecepatan pelicinan kemudi yaw")]
        public float yawSmoothSpeed = 8f;

        [Tooltip("Kecepatan pelicinan kemiringan sayap roll")]
        public float rollSmoothSpeed = 7.5f;

        [Tooltip("Kecepatan pelicinan sudut pitch")]
        public float pitchSmoothSpeed = 5.5f;

        [Header("Model Visual & Kamera")]
        public Transform visualModel;

        [Header("Kamera & Efek Visual Penerbangan (Camera Polish)")]
        [Tooltip("Kamera penerbangan utama (opsional, jika kosong akan mencari Camera.main)")]
        public Camera flightCamera;

        [Tooltip("Field of View dasar saat meluncur jelajah santai (derajat)")]
        public float baseCameraFOV = 60f;

        [Tooltip("Field of View tambahan saat kecepatan tinggi (Dive / Dash)")]
        public float maxSpeedFOVBoost = 12f;

        [Tooltip("Kecepatan pelicinan transisi FOV kamera")]
        public float fovSmoothSpeed = 4.0f;

        [Header("Proteksi Ketinggian Daratan (Terrain Clearance)")]
        public float minGroundClearance = 3.5f;
        public float maxAltitude = 160f;

        [Header("Fitur Tambahan: Fly Up, In-Flight Hover & Gentle Descent")]
        [Tooltip("Kekuatan daya angkat vertikal saat Fly Up (m/s)")]
        public float flyUpLiftPower = 11.0f;

        [Tooltip("Daya dorong maju akselerasi saat Fly Up (m/s^2)")]
        public float flyUpThrustAccel = 14.0f;

        [Tooltip("Sudut pitch menanjak saat Fly Up (derajat)")]
        public float flyUpPitch = 24.0f;

        [Tooltip("Kecepatan deselerasi maju saat memasuki Hover Mode")]
        public float hoverDecelRate = 4.0f;

        [Tooltip("Amplitudo bobbing saat In-Flight Hover")]
        public float inFlightHoverBobAmp = 0.35f;

        [Tooltip("Frekuensi bobbing saat In-Flight Hover")]
        public float inFlightHoverBobFreq = 2.2f;

        [Tooltip("Kecepatan jelajah saat Gentle Descent / Tucked T-Pose (m/s)")]
        public float gentleDescentSpeed = 16.0f;

        [Tooltip("Laju turun lembut saat Gentle Descent (m/s, jauh lebih lambat dari dive)")]
        public float gentleDescentSinkRate = 1.8f;

        [Tooltip("Sudut pitch saat Gentle Descent (derajat)")]
        public float gentleDescentPitch = -8.0f;

        [Header("Pengaturan Auto-Hover (Saat di Desa)")]
        public float hoverRotateSpeed = 3.5f;
        public float hoverBobAmplitude = 0.4f;
        public float hoverBobFrequency = 2.0f;

        [Header("Status Telemetri Penerbangan (Read Only)")]
        [SerializeField] private float _currentAirspeed = 14f;
        [SerializeField] private float _currentVerticalVelocity = 0f;
        [SerializeField] private float _currentPitch = -4f;
        [SerializeField] private float _currentYaw = 0f;
        [SerializeField] private float _currentRoll = 0f;
        [SerializeField] private bool _isHovering = false;
        [SerializeField] private bool _isInFlightHover = false;
        [SerializeField] private bool _isGentleDescent = false;
        [SerializeField] private bool _isFlyUp = false;
        [SerializeField] private bool _isTuckDiving = false;
        [SerializeField] private bool _isFlapping = false;
        [SerializeField] private bool _isPropellerDash = false;
        [SerializeField] private bool _isSwoopClimbing = false;
        [SerializeField] private float _currentTurnInput = 0f;
        [SerializeField] private Vector3 _hoverLookTarget;

        private Rigidbody _rb;
        private FlightCommand _activeCommand;

        // Properti Kompatibilitas Publik (InGameFlightHUD & VillageZoneController)
        public bool IsHovering => _isHovering;
        public bool IsInFlightHover => _isInFlightHover;
        public bool IsGentleDescent => _isGentleDescent;
        public bool IsFlyUp => _isFlyUp;
        public bool IsTuckDiving => _isTuckDiving;
        public bool IsFlapping => _isFlapping;
        public bool IsPropellerDash => _isPropellerDash;
        public bool IsSwoopClimbing => _isSwoopClimbing;
        public float CurrentSpeed => _currentAirspeed;
        public float CurrentVerticalVelocity => _currentVerticalVelocity;
        public float forwardSpeed { get => cruiseSpeed; set => cruiseSpeed = value; }
        public float CurrentTurnInput => _currentTurnInput;
        public float CurrentPitch => _currentPitch;
        public float CurrentAltitude => transform.position.y;
        public float currentAltitude { get => transform.position.y; set { } }
        public float fixedAltitudeY { get => transform.position.y; set { } }
        public FlightCommand ActiveCommand => _activeCommand;

        private void Awake()
        {
            _rb = GetComponent<Rigidbody>();
            if (_rb != null)
            {
                _rb.isKinematic = true;
                _rb.useGravity = false;
            }

            ResolveInputProvider();
            SetupVisualModel();

            _currentYaw = transform.eulerAngles.y;
            _currentPitch = -4f;
            _currentAirspeed = cruiseSpeed;

            SetupCamera();
        }

        private void SetupCamera()
        {
            if (flightCamera == null)
            {
                flightCamera = GetComponentInChildren<Camera>() ?? Camera.main;
            }
            if (flightCamera != null)
            {
                baseCameraFOV = flightCamera.fieldOfView;
            }
        }

        private void ResolveInputProvider()
        {
            if (flightInputSource is IFlightInputProvider mapper)
            {
                _flightInputProvider = mapper;
            }
            else
            {
                _flightInputProvider = GetComponent<IFlightInputProvider>() ?? FindFirstObjectByType<DefaultFlightInputMapper>();
            }

            // Direct fallback to IPoseProvider if mapper is not attached
            if (_flightInputProvider == null)
            {
                _directPoseProvider = GetComponent<IPoseProvider>() ?? FindFirstObjectByType<UDPPoseReceiver>();
            }
        }

        private void SetupVisualModel()
        {
            if (visualModel != null) return;

            Transform childVisual = transform.Find("Visual") ?? transform.Find("Model") ?? transform.Find("Visual_Dragon");
            if (childVisual != null)
            {
                visualModel = childVisual;
            }
            else if (transform.childCount > 0)
            {
                for (int i = 0; i < transform.childCount; i++)
                {
                    Transform c = transform.GetChild(i);
                    if (!c.GetComponent<Camera>())
                    {
                        visualModel = c;
                        break;
                    }
                }
            }
        }

        private void Update()
        {
            FetchFlightCommand();

            if (_isHovering)
            {
                HandleHoverState();
            }
            else
            {
                HandleSkyPeckFlightPhysics();
            }
        }

        private void LateUpdate()
        {
            UpdateCameraPolish();
        }

        /// <summary>
        /// 6.2 Camera Polish: Dynamic Field of View scaling proportional to airspeed.
        /// Memberikan efek sensasi desau angin dan kecepatan tinggi saat Tuck Dive atau Propeller Dash,
        /// dan mereda secara halus saat kembali ke kecepatan jelajah.
        /// </summary>
        private void UpdateCameraPolish()
        {
            if (flightCamera == null)
            {
                flightCamera = GetComponentInChildren<Camera>() ?? Camera.main;
                if (flightCamera == null) return;
            }

            float dt = Time.deltaTime;
            if (dt <= 0f) return;

            float speedRatio = Mathf.InverseLerp(cruiseSpeed, maxDiveSpeed, _currentAirspeed);
            float targetFOV = baseCameraFOV + speedRatio * maxSpeedFOVBoost;

            flightCamera.fieldOfView = Mathf.Lerp(flightCamera.fieldOfView, targetFOV, dt * fovSmoothSpeed);
        }

        /// <summary>
        /// Mengambil perintah terbang dari IFlightInputProvider atau fallback langsung ke IPoseProvider.
        /// </summary>
        private void FetchFlightCommand()
        {
            if (_flightInputProvider != null)
            {
                _activeCommand = _flightInputProvider.GetFlightCommand();
            }
            else if (_directPoseProvider != null)
            {
                _activeCommand = new FlightCommand
                {
                    TurnInput = _directPoseProvider.TurnInput,
                    PitchInput = _directPoseProvider.PitchInput,
                    BodyPitch = _directPoseProvider.BodyPitch,
                    IsFlapping = _directPoseProvider.IsFlapping,
                    FlapPower = _directPoseProvider.FlapPower,
                    IsTuckDiving = _directPoseProvider.IsTuckDive,
                    IsPropellerDash = _directPoseProvider.IsPropellerDash,
                    DashPower = _directPoseProvider.DashPower,
                    IsHover = _directPoseProvider.IsHover,
                    HoverPower = _directPoseProvider.ForearmFlapPower,
                    IsGentleDescent = _directPoseProvider.IsGentleDescent,
                    IsFlyUp = _directPoseProvider.IsFlyUp,
                    ChestElevation = _directPoseProvider.ChestElevation,
                    ActiveStateId = _directPoseProvider.ActiveStateId,
                    IsGliding = !_directPoseProvider.IsTuckDive && !_directPoseProvider.IsPropellerDash && !_directPoseProvider.IsFlapping && !_directPoseProvider.IsHover && !_directPoseProvider.IsGentleDescent && !_directPoseProvider.IsFlyUp
                };
            }
            else
            {
                ResolveInputProvider();
                _activeCommand = new FlightCommand { IsGliding = true };
            }

            _currentTurnInput = _activeCommand.TurnInput;
            _isTuckDiving = _activeCommand.IsTuckDiving;
            _isFlapping = _activeCommand.IsFlapping;
            _isPropellerDash = _activeCommand.IsPropellerDash;
            _isInFlightHover = _activeCommand.IsHover;
            _isGentleDescent = _activeCommand.IsGentleDescent;
            _isFlyUp = _activeCommand.IsFlyUp;
        }

        /// <summary>
        /// 3.1 & 3.2 Sky Peck Flight Movement & Continuous Physics:
        /// - Flap to Climb (Dynamic Lift & Thrust proportional to Flap Power)
        /// - Continuous Lean to Turn & Banking Roll
        /// - Tuck to Dive (Steep pitch, reduced drag, gravitational momentum acceleration)
        /// - Propeller Dash (Impulse forward thrust boost from arm rotation)
        /// - Swoop Climb Out of Dive (Kinetic speed excess smoothly converts into soaring altitude)
        /// - Glide (Gentle natural sink rate, airspeed relaxes to cruise speed)
        /// </summary>
        private void HandleSkyPeckFlightPhysics()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;
            dt = Mathf.Min(0.066f, dt); // Cap delta waktu maks 66ms untuk mencegah lonjakan fisika saat frame hiccup

            // 1. Raycast Jarak Permukaan Daratan
            float groundDistance = 999f;
            float groundSurfaceY = 0f;
            Ray groundRay = new Ray(transform.position + Vector3.up * 1f, Vector3.down);
            int mask = ~LayerMask.GetMask("Ignore Raycast");

            if (Physics.Raycast(groundRay, out RaycastHit gHit, 500f, mask))
            {
                if (gHit.collider.gameObject != gameObject && !gHit.collider.transform.IsChildOf(transform))
                {
                    groundSurfaceY = gHit.point.y;
                    groundDistance = transform.position.y - groundSurfaceY;
                }
            }

            // 2. Kemudi Belok & Banking Roll (Continuous Lean Mechanism)
            if (Mathf.Abs(_currentTurnInput) > 0.001f)
            {
                _currentYaw += _currentTurnInput * yawTurnSpeed * dt;
            }

            float targetRoll = -_currentTurnInput * maxRollAngle;
            _currentRoll = Mathf.Lerp(_currentRoll, targetRoll, dt * rollSmoothSpeed);

            // 3. Logika Keadaan Fisika Terbang Sky Peck
            float targetPitch = -4.0f; // Glide default (sedikit dive slope alami)
            _isSwoopClimbing = false;

            // Priority 1: Propeller Dash (Forward Impulse Boost)
            if (_isPropellerDash)
            {
                targetPitch = 0.0f; // Piercing level flight during dash
                float dashPwr = Mathf.Max(0.6f, _activeCommand.DashPower);

                // Akselerasi dorongan maju kencang
                _currentAirspeed += dashThrustAccel * dashPwr * dt;
                if (_currentAirspeed > maxDashSpeed) _currentAirspeed = maxDashSpeed;

                // Mempertahankan ketinggian horizontal stabil saat dash
                _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, 0.5f, dt * 6f);
            }
            // Priority 2: Tuck to Dive (High-Speed Steep Dive)
            else if (_isTuckDiving)
            {
                targetPitch = tuckDivePitch;

                // Akselerasi gravitasi saat sayap dilipat
                _currentAirspeed += diveAcceleration * dt;
                if (_currentAirspeed > maxDiveSpeed) _currentAirspeed = maxDiveSpeed;

                // Kecepatan vertikal turun cepat searah dive
                float diveSink = -_currentAirspeed * Mathf.Sin(Mathf.Abs(tuckDivePitch) * Mathf.Deg2Rad);
                _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, diveSink, dt * 5.5f);
            }
            // Priority 3: Stay on Air / Hover Mode (Upper Arms Tucked + Forearm Flapping)
            else if (_isInFlightHover)
            {
                targetPitch = 0.0f; // Menjaga naga tetap horizontal di udara

                // Perlahan menghentikan laju maju hingga mendekati 0 m/s
                _currentAirspeed = Mathf.Lerp(_currentAirspeed, 0f, dt * hoverDecelRate);

                // Flapping lengan bawah mempertahankan ketinggian
                float hoverPwr = _activeCommand.HoverPower;
                if (hoverPwr > 0.05f)
                {
                    // Vertical velocity dijaga mendekati nol dengan sedikit gerak alami (hover bobbing)
                    float bobTarget = Mathf.Sin(Time.time * inFlightHoverBobFreq) * inFlightHoverBobAmp;
                    _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, bobTarget, dt * 5.0f);
                }
                else
                {
                    // Jika kepakan berhenti, daya angkat berkurang dan naga mulai kehilangan ketinggian secara bertahap
                    _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, -1.6f, dt * 2.5f);
                }
            }
            // Priority 4: Forward Glide / Gentle Descent (Tucked T-Pose: Upper Arms Tucked + Forearms Extended, No Flapping)
            else if (_isGentleDescent)
            {
                targetPitch = gentleDescentPitch; // Sudut menunduk ringan (-8 deg), bukan menukik tajam

                // Mempertahankan atau sedikit meluncur maju (forward glide)
                _currentAirspeed = Mathf.Lerp(_currentAirspeed, gentleDescentSpeed, dt * 2.5f);

                // Penurunan ketinggian perlahan (jauh lebih lambat dari dive normal)
                _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, -gentleDescentSinkRate, dt * 3.5f);
            }
            // Priority 5: Fly Up (Chest Raised + Rhythmic Flapping)
            else if (_isFlyUp)
            {
                float flapPwr = Mathf.Max(0.5f, _activeCommand.FlapPower);

                // Naga mendongak ke atas mengikuti intensitas flapping
                targetPitch = Mathf.Lerp(16f, flyUpPitch, flapPwr);

                // Upward acceleration & momentum
                float targetClimb = flyUpLiftPower * flapPwr;
                _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, targetClimb, dt * 8.0f);

                // Tenaga dorong maju mendaki
                _currentAirspeed += flyUpThrustAccel * flapPwr * dt;
                if (_currentAirspeed > maxFlapSpeed) _currentAirspeed = maxFlapSpeed;
            }
            // Priority 6: Flap to Climb (Dynamic Lift + Thrust)
            else if (_isFlapping)
            {
                float flapPwr = Mathf.Max(0.5f, _activeCommand.FlapPower);

                // Hidung mendongak lembut saat mendaki tanpa pitch nodding
                targetPitch = Mathf.Lerp(7f, 15f, flapPwr);

                // Daya dorong maju kepakan
                _currentAirspeed += flapThrustAccel * flapPwr * dt;
                if (_currentAirspeed > maxFlapSpeed) _currentAirspeed = maxFlapSpeed;

                // Daya angkat vertikal kepakan (Climb!)
                float targetClimb = flapLiftPower * flapPwr;
                _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, targetClimb, dt * 7.5f);
            }
            // Priority 4: Glide & Swoop Climb (Aerodynamic Soaring)
            else
            {
                // Jika memiliki sisa kecepatan tinggi paska-dive atau paska-dash -> SWOOP CLIMB!
                if (_currentAirspeed > cruiseSpeed + 2.0f)
                {
                    _isSwoopClimbing = true;
                    float excessSpeed = _currentAirspeed - cruiseSpeed;

                    // Kepala mendongak anggun mengikuti luncuran swoop
                    targetPitch = Mathf.Clamp(excessSpeed * 1.5f, 7f, 24f);

                    // Kelebihan energi kinetik dikonversi menjadi kenaikan ketinggian
                    float swoopLift = excessSpeed * swoopEfficiency;
                    _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, swoopLift, dt * 6.0f);

                    // Kecepatan terkuras secara bertahap saat menanjak melawan gravitasi
                    _currentAirspeed -= excessSpeed * 0.60f * dt;
                }
                else
                {
                    // Glide jelajah stabil (sink rate santai)
                    targetPitch = -4.0f;
                    _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, -glideSinkRate, dt * 3.5f);
                    _currentAirspeed = Mathf.Lerp(_currentAirspeed, cruiseSpeed, dt * 2.2f);
                }
            }

            // Proteksi Daratan: Cegah menukik jika dekat daratan pulau
            if (groundDistance < 8.0f)
            {
                float groundAvoidance = Mathf.Clamp01((8.0f - groundDistance) / 5.0f);
                targetPitch = Mathf.Max(targetPitch, Mathf.Lerp(0f, 15f, groundAvoidance));
                if (_currentVerticalVelocity < 0f)
                {
                    _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, 1.5f, groundAvoidance * dt * 8f);
                }
            }

            // Pelicinan Pitch & Terapkan Rotasi 3D
            _currentPitch = Mathf.Lerp(_currentPitch, targetPitch, dt * pitchSmoothSpeed);
            transform.rotation = Quaternion.Euler(-_currentPitch, _currentYaw, _currentRoll);

            // 4. Pergerakan Posisi Naga 3D
            Vector3 forwardDir = Quaternion.Euler(0f, _currentYaw, 0f) * Vector3.forward;
            Vector3 forwardMove = forwardDir * (_currentAirspeed * dt);
            Vector3 verticalMove = Vector3.up * (_currentVerticalVelocity * dt);

            transform.position += (forwardMove + verticalMove);

            // 5. Koreksi Ground Clearance Aman
            float currentGroundDist = transform.position.y - groundSurfaceY;
            if (currentGroundDist < minGroundClearance)
            {
                Vector3 safePos = transform.position;
                safePos.y = groundSurfaceY + minGroundClearance;
                transform.position = safePos;
                if (_currentVerticalVelocity < 0f) _currentVerticalVelocity = 0f;
                if (_currentPitch < 0f) _currentPitch = Mathf.Lerp(_currentPitch, 0f, dt * 10f);
            }

            if (transform.position.y > maxAltitude)
            {
                Vector3 clampedAlt = transform.position;
                clampedAlt.y = maxAltitude;
                transform.position = clampedAlt;
                if (_currentVerticalVelocity > 0f) _currentVerticalVelocity = 0f;
            }
        }

        /// <summary>
        /// Mode melayang di tempat (Auto-Hover) saat berada di dalam area desa:
        /// Perlahan menghentikan laju maju, meratakan orientasi, dan menghadap ke pusat desa.
        /// </summary>
        private void HandleHoverState()
        {
            float dt = Time.deltaTime;
            _currentAirspeed = Mathf.Lerp(_currentAirspeed, 0f, dt * 4f);
            _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, 0f, dt * 4f);
            _currentPitch = Mathf.Lerp(_currentPitch, 0f, dt * 5f);
            _currentRoll = Mathf.Lerp(_currentRoll, 0f, dt * 5f);

            // Gerakan mengambang naik-turun halus (hover bobbing)
            float bobOffsetY = Mathf.Sin(Time.time * hoverBobFrequency) * hoverBobAmplitude * dt;
            transform.position += Vector3.up * bobOffsetY;

            // Hadapkan badan naga ke pusat desa secara halus
            Vector3 dirToTarget = _hoverLookTarget - transform.position;
            dirToTarget.y = 0f;

            if (dirToTarget.sqrMagnitude > 0.1f)
            {
                Quaternion targetRot = Quaternion.LookRotation(dirToTarget);
                transform.rotation = Quaternion.Slerp(transform.rotation, targetRot, dt * hoverRotateSpeed);
                _currentYaw = transform.eulerAngles.y;
            }
        }

        /// <summary>
        /// Diaktifkan oleh VillageZoneController saat naga memasuki atau meninggalkan area desa.
        /// </summary>
        public void SetHoverState(bool hover, Vector3 targetLookAt)
        {
            _isHovering = hover;
            _hoverLookTarget = targetLookAt;

            if (!hover)
            {
                _currentAirspeed = cruiseSpeed;
                _currentPitch = -4f;
                _currentVerticalVelocity = 0f;
            }
        }
    }
}
