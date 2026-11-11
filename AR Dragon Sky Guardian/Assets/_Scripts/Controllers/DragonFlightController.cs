using UnityEngine;
using DragonWingAR.CV;

namespace DragonWingAR.Controllers
{
    /// <summary>
    /// Pengendali utama penerbangan naga (Dragon Flight Controller).
    /// Mengimplementasikan prinsip dinamika penerbangan Minecraft Elytra:
    /// 1. True 3D Flight: Naga bergerak bebas dalam 3D ke arah hadap badannya (transform.forward).
    /// 2. Konversi Energi Kinetik (Gravity Energy Exchange): Menukik (dive) berakselerasi kencang;
    ///    menanjak (climb) mengonversi kecepatan menjadi ketinggian (zoom climb).
    /// 3. Kepakan Sayap (Flapping): Fly Up + Speed Up (daya dorong maju kinetik + gaya angkat vertikal).
    /// 4. Pose T (Elytra Glide): Meluncur ke depan dengan sedikit dive (-5 deg) dan kecepatan jelajah stabil.
    /// 5. Pose Gambar (Tuck Dive): Terjun menukik tajam (-45 deg) dengan kecepatan tinggi 22-28 m/s.
    /// 6. Proteksi Daratan: Otomatis meratakan hidung naga saat mendekati lereng bukit pulau.
    /// 7. Auto-Hover: Mengambang di tempat saat berada di zona desa.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class DragonFlightController : MonoBehaviour
    {
        [Header("Referensi Pose Provider")]
        [Tooltip("Komponen penyedia pose (jika kosong, otomatis mencari IPoseProvider pada objek ini atau scene)")]
        [SerializeField] private MonoBehaviour poseProviderSource;
        private IPoseProvider _poseProvider;

        [Header("Parameter Kecepatan Udara (Minecraft Elytra Physics)")]
        [Tooltip("Kecepatan jelajah standar saat meluncur T-Pose (m/s)")]
        public float cruiseSpeed = 14f;

        [Tooltip("Batas kecepatan stall minimum (m/s)")]
        public float minSpeed = 7f;

        [Tooltip("Batas kecepatan maksimum saat dive terjun cepat (m/s)")]
        public float maxDiveSpeed = 28f;

        [Tooltip("Kekuatan akselerasi gravitasi saat menukik / deselerasi saat menanjak")]
        public float gravityAccel = 18f;

        [Tooltip("Koefisien hambatan udara jelajah normal")]
        public float cruiseDrag = 0.45f;

        [Tooltip("Koefisien hambatan udara saat tuck dive (aerodinamis terlipat)")]
        public float diveDrag = 0.12f;

        [Header("Dinamika Kepakan Sayap (Fly Up + Speed Up)")]
        [Tooltip("Akselerasi daya dorong maju saat tangan mengepak (m/s^2)")]
        public float flapThrustAccel = 14f;

        [Tooltip("Gaya angkat vertikal langsung saat tangan mengepak (m/s)")]
        public float flapLiftVelocity = 3.5f;

        [Tooltip("Kecepatan maksimum dorongan kepakan di bidang datar")]
        public float maxFlapSpeed = 22f;

        [Header("Kontrol Sudut Orientasi 3D (Pitch, Yaw, Roll)")]
        [Tooltip("Kecepatan putar kemudi belok horizontal (Yaw deg/s)")]
        public float yawTurnSpeed = 65f;

        [Tooltip("Sudut pitch saat T-Pose Elytra Glide (sedikit dive, derajat)")]
        public float tposeGlidePitch = -5f;

        [Tooltip("Sudut pitch saat Tuck Dive (Pose Foto Pengguna, derajat)")]
        public float tuckDivePitch = -45f;

        [Tooltip("Sudut pitch saat menanjak Pose Y (derajat)")]
        public float climbPitch = 32f;

        [Tooltip("Sudut kemiringan visual Roll maksimal saat belok tajam (derajat)")]
        public float maxRollAngle = 35f;

        [Tooltip("Kecepatan pelicinan rotasi Pitch")]
        public float pitchSmoothSpeed = 4.5f;

        [Tooltip("Kecepatan pelicinan kemiringan sayap Roll")]
        public float rollSmoothSpeed = 7.0f;

        [Header("Model Visual")]
        [Tooltip("Transform child model naga untuk penyesuaian rotasi mikro visual")]
        public Transform visualModel;

        [Header("Proteksi Ketinggian Daratan (Terrain Safety)")]
        [Tooltip("Jarak minimum aman di atas daratan pulau (meter)")]
        public float minGroundClearance = 3.5f;

        [Tooltip("Ketinggian maksimum jelajah di angkasa")]
        public float maxAltitude = 160f;

        [Header("Pengaturan Auto-Hover (Saat di Desa)")]
        [Tooltip("Kecepatan naga memutar badan menghadap pusat desa saat hovering")]
        public float hoverRotateSpeed = 3.5f;

        [Tooltip("Amplitudo gerak mengambang naik-turun halus saat hover")]
        public float hoverBobAmplitude = 0.4f;

        [Tooltip("Frekuensi gerak mengambang naik-turun saat hover")]
        public float hoverBobFrequency = 2.0f;

        [Header("Status Telemetri Penerbangan (Read Only)")]
        [SerializeField] private float _currentAirspeed = 14f;
        [SerializeField] private float _currentPitch = -5f;
        [SerializeField] private float _currentYaw = 0f;
        [SerializeField] private float _currentRoll = 0f;
        [SerializeField] private bool _isHovering = false;
        [SerializeField] private bool _isTuckDiving = false;
        [SerializeField] private bool _isFlapping = false;
        [SerializeField] private float _currentTurnInput = 0f;
        [SerializeField] private float _currentPitchInput = 0f;
        [SerializeField] private Vector3 _hoverLookTarget;

        private Rigidbody _rb;

        // Properti Kompatibilitas Publik
        public bool IsHovering => _isHovering;
        public float CurrentSpeed => _currentAirspeed;
        public float forwardSpeed { get => cruiseSpeed; set => cruiseSpeed = value; }
        public float CurrentTurnInput => _currentTurnInput;
        public float CurrentPitchInput => _currentPitchInput;
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

            // Inisialisasi yaw dari rotasi awal naga di scene
            _currentYaw = transform.eulerAngles.y;
            _currentPitch = tposeGlidePitch;
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
                _currentPitchInput = _poseProvider.PitchInput;
                _isTuckDiving = _poseProvider.IsTuckDive;
                _isFlapping = _poseProvider.IsFlapping;
            }
            else
            {
                ResolvePoseProvider();
                _currentTurnInput = 0f;
                _currentPitchInput = 0f;
                _isTuckDiving = false;
                _isFlapping = false;
            }

            if (_isHovering)
            {
                HandleHoverState();
            }
            else
            {
                HandleElytraFlightPhysics();
            }
        }

        /// <summary>
        /// Simulasi Fisika Penerbangan Minecraft Elytra 3D Sejati:
        /// - Orientasi badan 3D bebas (Pitch, Yaw, Roll).
        /// - Maju searah badan (transform.forward * airspeed).
        /// - Menukik menghasilkan percepatan gravitasi tinggi (hingga 28 m/s).
        /// - Menanjak mengonversi kecepatan menjadi ketinggian (climb soaring).
        /// - Flapping memberikan dorongan Speed Up + Fly Up.
        /// - Proteksi daratan meratakan hidung naga saat dekat tanah.
        /// </summary>
        private void HandleElytraFlightPhysics()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;

            // 1. Raycast Permukaan Daratan (Terrain Clearance Check)
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

            // 2. Kalkulasi Target Pitch (Sudut Hidung Naga):
            // Positif = mendongak ke atas langit (+), Negatif = menunduk menukik ke bawah (-)
            float targetPitch = tposeGlidePitch; // Default T-Pose (-5 deg)

            if (_isTuckDiving)
            {
                // Pose Foto Pengguna: Dive terjun cepat (-45 deg)
                targetPitch = tuckDivePitch;
            }
            else if (_isFlapping)
            {
                // SAAT MENGEPAK: Orientasi TIDAK BERUBAH kecuali badan diarahkan ke atas/bawah!
                // Gerakan tangan naik-turun TIDAK BOLEH membuat naga melihat ke atas lalu ke bawah.
                float bodyPitch = (_poseProvider != null) ? _poseProvider.BodyPitch : 0f;

                if (bodyPitch > 0.18f)
                {
                    // Badan diarahkan ke atas: naga mendongak menanjak ke langit!
                    targetPitch = Mathf.Lerp(8f, climbPitch, Mathf.Clamp01((bodyPitch - 0.18f) / 0.82f));
                }
                else if (bodyPitch < -0.18f)
                {
                    // Badan diarahkan ke bawah: naga menunduk ke bawah
                    targetPitch = Mathf.Lerp(-5f, -22f, Mathf.Clamp01((-bodyPitch - 0.18f) / 0.82f));
                }
                else
                {
                    // Badan netral: Pertahankan orientasi jelajah stabil mendatar (glide pitch -5 deg)
                    // Bebas dari goyangan atau angguk-angguk!
                    targetPitch = tposeGlidePitch;
                }
            }
            else if (_poseProvider != null && _poseProvider.IsYPose)
            {
                // Pose Y Sustained (Tangan ditahan di atas, tidak mengepak): Menanjak mendongak ke atas (+32 deg)
                float climbFactor = Mathf.Clamp01(_currentPitchInput);
                targetPitch = Mathf.Lerp(12f, climbPitch, climbFactor);
            }
            else if (_poseProvider != null && _poseProvider.IsAPose)
            {
                // Pose A Sustained (Tangan ditahan di samping paha): Menurun moderat (-25 deg)
                targetPitch = -25f;
            }
            else
            {
                // T-Pose Elytra Glide: Sedikit dive (-5 deg)
                targetPitch = tposeGlidePitch;
            }

            // Proteksi Daratan: Jika terlalu dekat tanah bukit, hidung naga tidak boleh menukik ke bawah!
            if (groundDistance < 8.0f)
            {
                float groundAvoidanceFactor = Mathf.Clamp01((8.0f - groundDistance) / 5.0f);
                targetPitch = Mathf.Max(targetPitch, Mathf.Lerp(0f, 15f, groundAvoidanceFactor));
            }

            // Pelicinan Pitch
            _currentPitch = Mathf.Lerp(_currentPitch, targetPitch, dt * pitchSmoothSpeed);

            // 3. Kemudi Belok (Yaw) & Kemiringan Sayap (Roll Banking):
            if (Mathf.Abs(_currentTurnInput) > 0.001f)
            {
                _currentYaw += _currentTurnInput * yawTurnSpeed * dt;
            }

            float targetRoll = -_currentTurnInput * maxRollAngle;
            _currentRoll = Mathf.Lerp(_currentRoll, targetRoll, dt * rollSmoothSpeed);

            // Terapkan Rotasi 3D ke Naga:
            // Sumbu X Euler: -currentPitch (karena rotasi X negatif di Unity memutar hidung ke atas)
            transform.rotation = Quaternion.Euler(-_currentPitch, _currentYaw, _currentRoll);

            // 4. Fisika Kecepatan Udara (Minecraft Elytra Physics Model):
            float pitchRad = _currentPitch * Mathf.Deg2Rad;

            // a. Gravitasi: Menukik menambah kecepatan (-sin(negative) > 0), menanjak mengurangi kecepatan
            float gravityForce = -Mathf.Sin(pitchRad) * gravityAccel;
            _currentAirspeed += gravityForce * dt;

            // b. Hambatan Udara (Aerodynamic Drag):
            float currentDragCoeff = _isTuckDiving ? diveDrag : cruiseDrag;
            float terminalTarget = _isTuckDiving ? maxDiveSpeed : cruiseSpeed;

            // Menstabilkan kecepatan menuju kecepatan terminal alami glide
            if (!_isFlapping && _currentPitch <= 5f && _currentPitch >= -10f)
            {
                _currentAirspeed = Mathf.Lerp(_currentAirspeed, cruiseSpeed, dt * currentDragCoeff);
            }
            else if (_currentAirspeed > terminalTarget)
            {
                _currentAirspeed = Mathf.Lerp(_currentAirspeed, terminalTarget, dt * currentDragCoeff);
            }

            // c. Dinamika Kepakan Sayap (Fly Up + Speed Up):
            if (_isFlapping)
            {
                float flapPower = (_poseProvider != null) ? Mathf.Max(0.7f, _poseProvider.FlapPower) : 1.0f;

                // Speed Up (Dorongan maju akselerasi):
                _currentAirspeed += flapThrustAccel * flapPower * dt;
                if (_currentAirspeed > maxFlapSpeed && !_isTuckDiving && _currentPitch > -15f)
                {
                    _currentAirspeed = maxFlapSpeed;
                }

                // Fly Up (Gaya angkat vertikal langsung):
                transform.position += Vector3.up * (flapLiftVelocity * flapPower * dt);
            }

            // Batas kecepatan minimum (stall prevention) dan maksimum
            _currentAirspeed = Mathf.Clamp(_currentAirspeed, minSpeed, maxDiveSpeed);

            // 5. Pergerakan Maju 3D Sejati (Searah Hidung Naga):
            Vector3 movement = transform.forward * (_currentAirspeed * dt);
            transform.position += movement;

            // 6. Koreksi Ketinggian Tanah Aman (Ground Clamp Safety):
            if (groundDistance < minGroundClearance)
            {
                Vector3 safePos = transform.position;
                safePos.y = groundSurfaceY + minGroundClearance;
                transform.position = safePos;

                // Jika menyentuh batas tanah aman, ratakan hidung dari menukik
                if (_currentPitch < 0f)
                {
                    _currentPitch = Mathf.Lerp(_currentPitch, 0f, dt * 10f);
                }
            }

            // Batas ketinggian maksimum jelajah
            if (transform.position.y > maxAltitude)
            {
                Vector3 clampedAlt = transform.position;
                clampedAlt.y = maxAltitude;
                transform.position = clampedAlt;
                if (_currentPitch > 0f) _currentPitch = 0f;
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
                _currentPitch = tposeGlidePitch;
            }
        }
    }
}
