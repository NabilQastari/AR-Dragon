using UnityEngine;
using DragonWingAR.CV;

namespace DragonWingAR.Controllers
{
    /// <summary>
    /// Pengendali utama penerbangan naga (Dragon Flight Controller).
    /// Mengimplementasikan prinsip desain PRD & Konteks:
    /// 1. Auto-Forward: Naga bergerak maju otomatis dengan kecepatan 12 m/s.
    /// 2. Fixed Altitude: Ketinggian naga dijaga stabil pada Y = 15 m.
    /// 3. Kemudi Belok & Roll: Putaran Yaw (65 deg/s) dan kemiringan visual Roll (-turnInput * 35 deg).
    /// 4. Auto-Hover: Mengambang di tempat saat memasuki zona desa dan menghadap ke pusat desa.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class DragonFlightController : MonoBehaviour
    {
        [Header("Referensi Pose Provider")]
        [Tooltip("Komponen penyedia pose (jika kosong, otomatis mencari IPoseProvider pada objek ini atau scene)")]
        [SerializeField] private MonoBehaviour poseProviderSource;
        private IPoseProvider _poseProvider;

        [Header("Parameter Terbang Maju")]
        [Tooltip("Kecepatan terbang maju otomatis (sesuai konteks.md = 12f)")]
        public float forwardSpeed = 12f;

        [Tooltip("Kecepatan putar arah naga / Yaw (sesuai konteks.md = 65f)")]
        public float yawTurnSpeed = 65f;

        [Header("Parameter Terbang Vertikal (Naik & Turun)")]
        [Tooltip("Ketinggian naga saat ini")]
        public float currentAltitude = 22f;

        /// <summary>
        /// Properti kompatibilitas untuk fixed altitude lama
        /// </summary>
        public float fixedAltitudeY { get => currentAltitude; set => currentAltitude = value; }

        [Tooltip("Ketinggian minimum di atas daratan")]
        public float minAltitude = 5f;

        [Tooltip("Ketinggian maksimum jelajah (mampu melewati puncak gunung 120m)")]
        public float maxAltitude = 140f;

        [Tooltip("Kecepatan menanjak naik saat Pose Y (m/s)")]
        public float climbSpeed = 10f;

        [Tooltip("Kecepatan menukik turun saat Pose A (m/s)")]
        public float diveSpeed = 12f;

        [Tooltip("Kecepatan transisi smoothing ketinggian")]
        public float altitudeSmoothSpeed = 8f;

        [Header("Model Visual & Kemiringan Dinamis")]
        [Tooltip("Transform child model naga untuk efek kemiringan visual (Banking Roll & Pitch)")]
        public Transform visualModel;

        [Tooltip("Sudut kemiringan visual Roll maksimal saat belok tajam (sesuai konteks.md = 35f)")]
        public float maxRollAngle = 35f;

        [Tooltip("Sudut kemiringan visual Pitch maksimal saat menanjak/menukik (derajat)")]
        public float maxPitchAngle = 22f;

        [Tooltip("Kecepatan transisi kemiringan model visual")]
        public float attitudeSmoothSpeed = 10f;

        [Header("Pengaturan Auto-Hover (Saat di Desa)")]
        [Tooltip("Kecepatan naga memutar badan menghadap pusat desa saat hovering")]
        public float hoverRotateSpeed = 3.5f;

        [Tooltip("Amplitudo gerak mengambang naik-turun halus saat hover")]
        public float hoverBobAmplitude = 0.4f;

        [Tooltip("Frekuensi gerak mengambang naik-turun saat hover")]
        public float hoverBobFrequency = 2.0f;

        [Header("Status Telemetri (Read Only)")]
        [SerializeField] private bool _isHovering = false;
        [SerializeField] private float _currentTurnInput = 0f;
        [SerializeField] private float _currentPitchInput = 0f;
        [SerializeField] private float _currentSpeed = 0f;
        [SerializeField] private Vector3 _hoverLookTarget;

        private Rigidbody _rb;

        public bool IsHovering => _isHovering;
        public float CurrentSpeed => _currentSpeed;
        public float CurrentTurnInput => _currentTurnInput;
        public float CurrentPitchInput => _currentPitchInput;
        public float CurrentAltitude => currentAltitude;

        private void Awake()
        {
            _rb = GetComponent<Rigidbody>();
            if (_rb != null)
            {
                _rb.isKinematic = true;
                _rb.useGravity = false;
            }

            // Inisialisasi Pose Provider
            ResolvePoseProvider();

            // Pastikan model visual terpisah agar roll & pitch visual tidak mengganggu arah maju
            SetupVisualModel();

            // Set ketinggian awal naga sesuai posisi awal
            if (currentAltitude <= 1f)
            {
                currentAltitude = transform.position.y > 1f ? transform.position.y : 22f;
            }
            Vector3 initPos = transform.position;
            initPos.y = currentAltitude;
            transform.position = initPos;
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

            // Cari child bernama "Visual" atau "Model"
            Transform childVisual = transform.Find("Visual") ?? transform.Find("Model") ?? transform.Find("Visual_Dragon");
            if (childVisual != null)
            {
                visualModel = childVisual;
            }
            else if (transform.childCount > 0)
            {
                // Gunakan child pertama selain Camera
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

            // Jika tidak ada child, buat empty container sebagai referensi visual
            if (visualModel == null)
            {
                GameObject dummyVisual = new GameObject("Visual_Root");
                dummyVisual.transform.SetParent(transform, false);
                visualModel = dummyVisual.transform;
            }
        }

        private void Update()
        {
            // Ambil input kemudi dari Pose Provider / Keyboard Fallback
            if (_poseProvider != null)
            {
                _currentTurnInput = _poseProvider.TurnInput;
                _currentPitchInput = _poseProvider.PitchInput;
            }
            else
            {
                ResolvePoseProvider();
                _currentTurnInput = 0f;
                _currentPitchInput = 0f;
            }

            if (_isHovering)
            {
                HandleHoverState();
            }
            else
            {
                HandleFlightMovement();
            }

            // Update kemiringan roll & pitch model visual (visual banking & attitude)
            UpdateVisualAttitude();
        }

        /// <summary>
        /// Pergerakan terbang naga dengan navigasi 3D lengkap:
        /// 1. Auto-Forward: Maju otomatis (kecepatan bertambah saat menukik / dive boost).
        /// 2. Ketinggian Dinamis: Naik saat kepak sayap, turun saat dive pose, stabil saat T-pose.
        /// 3. Kemudi Belok: Putaran Yaw (65 deg/s) berdasarkan kemiringan tangan.
        /// </summary>
        private void HandleFlightMovement()
        {
            // 1. Maju Otomatis dengan Dinamika Kecepatan (Dive Boost)
            float speedModifier = 1.0f;
            if (_currentPitchInput < -0.1f)
            {
                // Menukik: gravitasi menambah kecepatan hingga +35% (misal 12 -> 16.2 m/s)
                speedModifier += Mathf.Abs(_currentPitchInput) * 0.35f;
            }
            else if (_currentPitchInput > 0.1f)
            {
                // Menanjak: hambatan gravitasi sedikit melambatkan maju (misal 12 -> 10.5 m/s)
                speedModifier -= _currentPitchInput * 0.12f;
            }

            _currentSpeed = forwardSpeed * speedModifier;
            Vector3 moveDelta = transform.forward * (_currentSpeed * Time.deltaTime);
            transform.position += moveDelta;

            // 2. Kontrol Ketinggian Vertikal Dinamis (Sistem Alfabet: Y = NAIK, T = LURUS, A = TURUN)
            bool isClimbing = (_poseProvider != null && _poseProvider.IsYPose) || _currentPitchInput > 0.05f;
            bool isDiving = (_poseProvider != null && _poseProvider.IsAPose) || _currentPitchInput < -0.05f;

            if (isClimbing)
            {
                float factor = Mathf.Max(0.7f, Mathf.Abs(_currentPitchInput));
                currentAltitude += factor * climbSpeed * Time.deltaTime;
            }
            else if (isDiving)
            {
                float factor = Mathf.Max(0.7f, Mathf.Abs(_currentPitchInput));
                currentAltitude -= factor * diveSpeed * Time.deltaTime;
            }
            // Catatan: Jika T-Pose, currentAltitude dipertahankan stabil di ketinggian jelajah saat ini!

            // Raycast proteksi ketinggian daratan: naga tidak akan pernah menembus ke dalam tanah pulau
            float terrainSurfaceY = 0f;
            Ray groundRay = new Ray(new Vector3(transform.position.x, 300f, transform.position.z), Vector3.down);
            int mask = ~LayerMask.GetMask("Ignore Raycast");
            if (Physics.Raycast(groundRay, out RaycastHit gHit, 500f, mask))
            {
                if (gHit.collider.gameObject != gameObject && !gHit.collider.transform.IsChildOf(transform))
                {
                    terrainSurfaceY = gHit.point.y;
                }
            }

            float safeMin = Mathf.Max(minAltitude, terrainSurfaceY + 2.5f);
            currentAltitude = Mathf.Clamp(currentAltitude, safeMin, maxAltitude);

            Vector3 currentPos = transform.position;
            currentPos.y = Mathf.Lerp(currentPos.y, currentAltitude, Time.deltaTime * altitudeSmoothSpeed);
            transform.position = currentPos;

            // 3. Putaran Arah Kemudi (Yaw Turn)
            if (Mathf.Abs(_currentTurnInput) > 0.001f)
            {
                float yawDelta = _currentTurnInput * yawTurnSpeed * Time.deltaTime;
                transform.Rotate(Vector3.up, yawDelta, Space.World);
            }
        }

        /// <summary>
        /// Mode melayang di tempat (Auto-Hover) saat berada di dalam area desa:
        /// Berhenti bergerak maju dan secara perlahan menghadapkan naga ke pusat desa.
        /// </summary>
        private void HandleHoverState()
        {
            _currentSpeed = Mathf.Lerp(_currentSpeed, 0f, Time.deltaTime * 5f);

            // Gerakan mengambang naik-turun halus (hover bobbing)
            float bobOffsetY = Mathf.Sin(Time.time * hoverBobFrequency) * hoverBobAmplitude;
            Vector3 pos = transform.position;
            pos.y = currentAltitude + bobOffsetY;
            transform.position = pos;

            // Memutar badan secara halus menghadap pusat desa
            Vector3 dirToTarget = _hoverLookTarget - transform.position;
            dirToTarget.y = 0f; // Tetap di bidang horizontal (tidak menukik)

            if (dirToTarget.sqrMagnitude > 0.1f)
            {
                Quaternion targetRot = Quaternion.LookRotation(dirToTarget);
                transform.rotation = Quaternion.Slerp(transform.rotation, targetRot, Time.deltaTime * hoverRotateSpeed);
            }
        }

        /// <summary>
        /// Memperbarui kemiringan visual (Banking Roll & Pitch) pada visualModel naga.
        /// - Roll: Miring saat belok kiri/kanan (-turnInput * maxRollAngle).
        /// - Pitch: Menengadah saat naik (climb) dan menunduk tajam saat menukik (dive).
        /// - T-Pose: Kembali rata mendatar (0 deg).
        /// </summary>
        private void UpdateVisualAttitude()
        {
            if (visualModel == null) return;

            float targetRoll = _isHovering ? 0f : (-_currentTurnInput * maxRollAngle);

            // Pitch: Saat Pose Y (Naik), kepala naga mendongak ke atas (-Euler X)
            // Saat Pose A (Menukik), kepala naga menunduk tajam (+Euler X)
            float targetPitch = 0f;
            if (!_isHovering)
            {
                if (_poseProvider != null && _poseProvider.IsYPose)
                {
                    targetPitch = -maxPitchAngle;
                }
                else if (_poseProvider != null && _poseProvider.IsAPose)
                {
                    targetPitch = maxPitchAngle;
                }
                else
                {
                    targetPitch = -_currentPitchInput * maxPitchAngle;
                }
            }

            Quaternion targetLocalRot = Quaternion.Euler(targetPitch, 0f, targetRoll);

            visualModel.localRotation = Quaternion.Slerp(
                visualModel.localRotation,
                targetLocalRot,
                Time.deltaTime * attitudeSmoothSpeed
            );
        }

        /// <summary>
        /// Diaktifkan oleh VillageZoneController saat naga memasuki atau meninggalkan area desa.
        /// </summary>
        /// <param name="hover">True jika naga harus berhenti dan mengambang di desa</param>
        /// <param name="targetLookAt">Posisi pusat desa yang harus dihadapi oleh naga</param>
        public void SetHoverState(bool hover, Vector3 targetLookAt)
        {
            _isHovering = hover;
            _hoverLookTarget = targetLookAt;

            if (!hover)
            {
                _currentSpeed = forwardSpeed;
            }
        }
    }
}
