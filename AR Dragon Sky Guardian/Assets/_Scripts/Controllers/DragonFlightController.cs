using UnityEngine;
using DragonWingAR.CV;

namespace DragonWingAR.Controllers
{
    /// <summary>
    /// Pengendali penerbangan naga dengan mekanik terinspirasi dari Sky Peck:
    /// 1. Flap to Climb: Mengepakkan tangan secara fisik mengangkat naga naik (climb) secara mulus.
    /// 2. Lean to Bank/Turn: Condongkan tubuh kiri/kanan untuk belok dan miringkan sayap (roll banking).
    /// 3. Tuck to Dive: Menekuk/merapatkan tangan ke dada membuat naga menukik tajam berkecepatan tinggi.
    /// 4. Swoop Out of Dive: Membuka sayap setelah dive mengonversi kecepatan menjadi luncuran menanjak (swoop climb).
    /// 5. Glide: Meluncur anggun dengan sink rate alami yang santai saat tangan direntangkan.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class DragonFlightController : MonoBehaviour
    {
        [Header("Referensi Pose Provider")]
        [SerializeField] private MonoBehaviour poseProviderSource;
        private IPoseProvider _poseProvider;

        [Header("Kecepatan & Fisika Terbang (Sky Peck Model)")]
        [Tooltip("Kecepatan jelajah meluncur normal (m/s)")]
        public float cruiseSpeed = 14f;

        [Tooltip("Kecepatan stall minimum (m/s)")]
        public float minSpeed = 7f;

        [Tooltip("Kecepatan maksimum saat dive menukik (m/s)")]
        public float maxDiveSpeed = 28f;

        [Tooltip("Laju turun alami saat meluncur santai / Glide Sink Rate (m/s)")]
        public float glideSinkRate = 1.0f;

        [Header("Mekanik Kepakan (Flap to Climb)")]
        [Tooltip("Kekuatan daya angkat vertikal saat mengepak (m/s)")]
        public float flapLiftPower = 5.5f;

        [Tooltip("Daya dorong maju tambahan saat mengepak (m/s^2)")]
        public float flapThrustAccel = 10f;

        [Tooltip("Kecepatan maksimum dorongan kepakan di bidang datar")]
        public float maxFlapSpeed = 22f;

        [Header("Mekanik Menukik (Tuck to Dive & Swoop)")]
        [Tooltip("Akselerasi gravitasi saat sayap dilipat / dive (m/s^2)")]
        public float diveAcceleration = 18f;

        [Tooltip("Sudut pitch menukik saat tangan ditekuk ke dada (derajat)")]
        public float tuckDivePitch = -38f;

        [Tooltip("Efisiensi konversi kecepatan dive menjadi kenaikan ketinggian (Swoop Climb)")]
        [Range(0.4f, 1.0f)]
        public float swoopEfficiency = 0.85f;

        [Header("Mekanik Kemudi & Kemiringan Tubuh (Lean to Turn)")]
        [Tooltip("Kecepatan belok kompas (Yaw deg/s) saat condong maksimal")]
        public float yawTurnSpeed = 70f;

        [Tooltip("Sudut kemiringan sayap (Roll Banking) saat belok tajam (derajat)")]
        public float maxRollAngle = 38f;

        [Tooltip("Kecepatan pelicinan kemudi yaw")]
        public float yawSmoothSpeed = 8f;

        [Tooltip("Kecepatan pelicinan kemiringan sayap roll")]
        public float rollSmoothSpeed = 7f;

        [Tooltip("Kecepatan pelicinan sudut pitch")]
        public float pitchSmoothSpeed = 5f;

        [Header("Model Visual & Kamera")]
        public Transform visualModel;

        [Header("Proteksi Ketinggian Daratan (Terrain Clearance)")]
        public float minGroundClearance = 3.5f;
        public float maxAltitude = 160f;

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
        [SerializeField] private bool _isTuckDiving = false;
        [SerializeField] private bool _isFlapping = false;
        [SerializeField] private bool _isSwoopClimbing = false;
        [SerializeField] private float _currentTurnInput = 0f;
        [SerializeField] private Vector3 _hoverLookTarget;

        private Rigidbody _rb;

        // Properti Kompatibilitas Publik
        public bool IsHovering => _isHovering;
        public bool IsTuckDiving => _isTuckDiving;
        public bool IsFlapping => _isFlapping;
        public bool IsSwoopClimbing => _isSwoopClimbing;
        public float CurrentSpeed => _currentAirspeed;
        public float CurrentVerticalVelocity => _currentVerticalVelocity;
        public float forwardSpeed { get => cruiseSpeed; set => cruiseSpeed = value; }
        public float CurrentTurnInput => _currentTurnInput;
        public float CurrentPitch => _currentPitch;
        public float CurrentAltitude => transform.position.y;
        public float currentAltitude { get => transform.position.y; set { } }
        public float fixedAltitudeY { get => transform.position.y; set { } }

        private void Awake()
        {
            _rb = GetComponent<Rigidbody>();
            if (_rb != null)
            {
                _rb.isKinematic = true;
                _rb.useGravity = false;
            }

            ResolvePoseProvider();
            SetupVisualModel();

            _currentYaw = transform.eulerAngles.y;
            _currentPitch = -4f;
            _currentAirspeed = cruiseSpeed;
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
            if (_poseProvider != null)
            {
                _currentTurnInput = _poseProvider.TurnInput;
                _isTuckDiving = _poseProvider.IsTuckDive;
                _isFlapping = _poseProvider.IsFlapping;
            }
            else
            {
                ResolvePoseProvider();
                _currentTurnInput = 0f;
                _isTuckDiving = false;
                _isFlapping = false;
            }

            if (_isHovering)
            {
                HandleHoverState();
            }
            else
            {
                HandleSkyPeckFlightPhysics();
            }
        }

        /// <summary>
        /// Mekanik Penerbangan Sky Peck:
        /// 1. Flap to Climb: Mengepakkan tangan memberi lift vertikal halus & akselerasi maju.
        /// 2. Lean to Turn: Condongkan tubuh untuk berbelok dan banking sayap.
        /// 3. Tuck to Dive: Merapatkan tangan ke dada membuat naga menukik tajam berkecepatan tinggi.
        /// 4. Swoop Climb: Membuka sayap setelah dive mengonversi kecepatan menjadi luncuran menanjak.
        /// 5. Glide: Meluncur anggun dengan sink rate alami yang santai saat tangan direntangkan.
        /// </summary>
        private void HandleSkyPeckFlightPhysics()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;

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

            // 2. Kemudi Belok & Banking Roll (Sky Peck Lean Mechanism)
            if (Mathf.Abs(_currentTurnInput) > 0.001f)
            {
                _currentYaw += _currentTurnInput * yawTurnSpeed * dt;
            }

            float targetRoll = -_currentTurnInput * maxRollAngle;
            _currentRoll = Mathf.Lerp(_currentRoll, targetRoll, dt * rollSmoothSpeed);

            // 3. Logika Keadaan Terbang Sky Peck (Dive, Flap Climb, Swoop, Glide):
            float targetPitch = -4.0f; // Glide default (sedikit dive slope alami)
            _isSwoopClimbing = false;

            if (_isTuckDiving)
            {
                // A. TUCK TO DIVE:
                // Tangan dilipat di dada -> sayap melipat, hidung menukik tajam, meluncur kencang!
                targetPitch = tuckDivePitch;
                _currentAirspeed += diveAcceleration * dt;
                if (_currentAirspeed > maxDiveSpeed) _currentAirspeed = maxDiveSpeed;

                // Kecepatan vertikal turun cepat searah dive
                float diveSink = -_currentAirspeed * Mathf.Sin(Mathf.Abs(tuckDivePitch) * Mathf.Deg2Rad);
                _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, diveSink, dt * 5f);
            }
            else if (_isFlapping)
            {
                // B. FLAP TO CLIMB:
                // Setiap kepakan mengangkat naga naik dan menambah daya dorong maju!
                float flapPower = (_poseProvider != null) ? Mathf.Max(0.7f, _poseProvider.FlapPower) : 1.0f;

                // Hidung mendongak lembut saat mendaki (tanpa goyangan)
                targetPitch = Mathf.Lerp(6f, 15f, flapPower);

                // Daya dorong maju kepakan
                _currentAirspeed += flapThrustAccel * flapPower * dt;
                if (_currentAirspeed > maxFlapSpeed) _currentAirspeed = maxFlapSpeed;

                // Daya angkat vertikal kepakan (Climb!)
                float targetClimb = flapLiftPower * flapPower;
                _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, targetClimb, dt * 7f);
            }
            else
            {
                // C. GLIDE & SWOOP:
                // Sayap terbentang meluncur santai
                // Jika memiliki sisa kecepatan tinggi dari dive sebelumnya -> Otomatis SWOOP CLIMB!
                if (_currentAirspeed > cruiseSpeed + 2.5f)
                {
                    _isSwoopClimbing = true;
                    float excessSpeed = _currentAirspeed - cruiseSpeed;

                    // Kepala mendongak anggun mengikuti luncuran swoop
                    targetPitch = Mathf.Clamp(excessSpeed * 1.6f, 6f, 26f);

                    // Kecepatan dikonversi menjadi kenaikan ketinggian
                    float swoopLift = excessSpeed * swoopEfficiency;
                    _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, swoopLift, dt * 6f);

                    // Kecepatan terkuras secara bertahap saat menanjak
                    _currentAirspeed -= excessSpeed * 0.65f * dt;
                }
                else
                {
                    // Glide jelajah stabil (sink rate santai)
                    targetPitch = -4.0f;
                    _currentVerticalVelocity = Mathf.Lerp(_currentVerticalVelocity, -glideSinkRate, dt * 3f);
                    _currentAirspeed = Mathf.Lerp(_currentAirspeed, cruiseSpeed, dt * 2f);
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
            // Maju horizontal searah hadap yaw
            Vector3 forwardDir = Quaternion.Euler(0f, _currentYaw, 0f) * Vector3.forward;
            Vector3 forwardMove = forwardDir * (_currentAirspeed * dt);

            // Gerak vertikal hasil kalkulasi lift / sink
            Vector3 verticalMove = Vector3.up * (_currentVerticalVelocity * dt);

            transform.position += (forwardMove + verticalMove);

            // 5. Koreksi Ground Clearance Aman
            if (groundDistance < minGroundClearance)
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
