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

        [Header("Parameter Terbang Otomatis")]
        [Tooltip("Kecepatan terbang maju otomatis (sesuai konteks.md = 12f)")]
        public float forwardSpeed = 12f;

        [Tooltip("Ketinggian naga tetap stabil di udara (sesuai konteks.md = 15f)")]
        public float fixedAltitudeY = 15f;

        [Tooltip("Kecepatan putar arah naga / Yaw (sesuai konteks.md = 65f)")]
        public float yawTurnSpeed = 65f;

        [Header("Model Visual & Kemiringan Roll")]
        [Tooltip("Transform child model naga untuk efek kemiringan visual (Z-axis banking)")]
        public Transform visualModel;

        [Tooltip("Sudut kemiringan visual maksimal saat belok tajam (sesuai konteks.md = 35f)")]
        public float maxRollAngle = 35f;

        [Tooltip("Kecepatan transisi kemiringan model visual")]
        public float rollSmoothSpeed = 8f;

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
        [SerializeField] private float _currentSpeed = 0f;
        [SerializeField] private Vector3 _hoverLookTarget;

        private Rigidbody _rb;

        public bool IsHovering => _isHovering;
        public float CurrentSpeed => _currentSpeed;

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

            // Pastikan model visual terpisah agar roll visual tidak mengganggu arah maju
            SetupVisualModel();

            // Kunci posisi awal naga di ketinggian standar
            Vector3 initPos = transform.position;
            initPos.y = fixedAltitudeY;
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
                _poseProvider = GetComponent<IPoseProvider>() ?? FindObjectOfType<UDPPoseReceiver>();
            }
        }

        private void SetupVisualModel()
        {
            if (visualModel != null) return;

            // Cari child bernama "Visual" atau "Model"
            Transform childVisual = transform.Find("Visual") ?? transform.Find("Model");
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
            }
            else
            {
                ResolvePoseProvider();
                _currentTurnInput = 0f;
            }

            if (_isHovering)
            {
                HandleHoverState();
            }
            else
            {
                HandleFlightMovement();
            }

            // Update kemiringan roll model visual (visual banking)
            UpdateVisualRoll();
        }

        /// <summary>
        /// Pergerakan terbang reguler di luar zona desa:
        /// Maju otomatis 12 m/s, ketinggian tetap Y = 15 m, dan belok Yaw berdasarkan TurnInput.
        /// </summary>
        private void HandleFlightMovement()
        {
            _currentSpeed = forwardSpeed;

            // 1. Maju Otomatis (Auto-Forward)
            Vector3 moveDelta = transform.forward * (_currentSpeed * Time.deltaTime);
            transform.position += moveDelta;

            // 2. Kunci Ketinggian Tetap (Fixed Altitude Y = 15m)
            Vector3 currentPos = transform.position;
            currentPos.y = fixedAltitudeY;
            transform.position = currentPos;

            // 3. Putaran Arah Kemudi (Yaw Turn)
            // Sesuai konteks.md Bagian 4.1: transform.Rotate(Vector3.up * turnInput * 65f * Time.deltaTime)
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
            pos.y = fixedAltitudeY + bobOffsetY;
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
        /// Memperbarui kemiringan roll visual pada child visualModel.
        /// Sesuai konteks.md: visualModel.localRotation dicondongkan pada paksi Z sebanyak -turnInput * 35f.
        /// </summary>
        private void UpdateVisualRoll()
        {
            if (visualModel == null) return;

            float targetRoll = _isHovering ? 0f : (-_currentTurnInput * maxRollAngle);
            Quaternion targetLocalRot = Quaternion.Euler(0f, 0f, targetRoll);

            visualModel.localRotation = Quaternion.Slerp(
                visualModel.localRotation,
                targetLocalRot,
                Time.deltaTime * rollSmoothSpeed
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
