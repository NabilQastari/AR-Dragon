using System;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace DragonWingAR.CV
{
    /// <summary>
    /// Penerima data socket UDP dari modul Computer Vision Python (port 5052).
    /// Mengimplementasikan IPoseProvider, melakukan smoothing koordinat via Vector2.Lerp,
    /// dan menyediakan Keyboard Fallback untuk kemudahan pengujian kapan pun tanpa kamera.
    /// </summary>
    public class UDPPoseReceiver : MonoBehaviour, IPoseProvider
    {
        [Header("Pengaturan Socket UDP")]
        [Tooltip("Port UDP yang mendengarkan data dari Python (default: 5052)")]
        public int port = 5052;

        [Tooltip("Kecepatan pelicinan koordinat (Vector2.Lerp rate, sesuai konteks.md = 12f)")]
        public float smoothingSpeed = 12f;

        [Tooltip("Batas waktu dalam detik sebelum koneksi dianggap terputus")]
        public float timeoutSeconds = 1.0f;

        [Header("Pengaturan Kemudi Terbang")]
        [Tooltip("Batas mati kemiringan tangan sebelum naga mulai belok (default: 0.08f)")]
        public float turnDeadzone = 0.08f;

        [Tooltip("Pengali sensitivitas belok naga (default: 2.5f)")]
        public float turnMultiplier = 2.5f;

        [Header("Keyboard Fallback (Kontrol Alternatif)")]
        [Tooltip("Aktifkan kontrol keyboard otomatis saat UDP tidak menerima data")]
        public bool enableKeyboardFallback = true;

        // ==========================================
        // Implementasi Properti IPoseProvider
        // ==========================================
        public bool IsConnected => _isConnected;
        public bool IsPoseDetected => _isPoseDetected;

        public Vector2 LeftShoulder => _smoothedLS;
        public Vector2 RightShoulder => _smoothedRS;
        public Vector2 LeftWrist => _smoothedLW;
        public Vector2 RightWrist => _smoothedRW;
        public Vector2 LeftHip => _smoothedLH;
        public Vector2 RightHip => _smoothedRH;

        public float MouthOpen => _smoothedMouth;
        public bool IsWaterBreathing => _isWaterBreathing;
        public float TurnInput => _turnInput;

        public bool IsFlapping => _isFlapping;
        public bool IsHandsTogether => _isHandsTogether;
        public bool IsHandsHighUp => _isHandsHighUp;

        // ==========================================
        // Variabel Internal Smoothing & Status
        // ==========================================
        [Header("Status Telemetri (Read Only)")]
        [SerializeField] private bool _isConnected = false;
        [SerializeField] private bool _isPoseDetected = false;
        [SerializeField] private float _turnInput = 0f;
        [SerializeField] private float _smoothedMouth = 0f;
        [SerializeField] private bool _isWaterBreathing = false;
        [SerializeField] private bool _isFlapping = false;
        [SerializeField] private bool _isHandsTogether = false;
        [SerializeField] private bool _isHandsHighUp = false;

        private Vector2 _smoothedLS = new Vector2(0.40f, 0.40f);
        private Vector2 _smoothedRS = new Vector2(0.60f, 0.40f);
        private Vector2 _smoothedLW = new Vector2(0.35f, 0.60f);
        private Vector2 _smoothedRW = new Vector2(0.65f, 0.60f);
        private Vector2 _smoothedLH = new Vector2(0.42f, 0.70f);
        private Vector2 _smoothedRH = new Vector2(0.58f, 0.70f);

        // Thread-safe raw data buffer
        private readonly object _dataLock = new object();
        private readonly System.Diagnostics.Stopwatch _stopwatch = System.Diagnostics.Stopwatch.StartNew();
        private long _lastPacketMs = -999999;
        private bool _hasNewPacket = false;
        private Vector2 _rawLS, _rawRS, _rawLW, _rawRW, _rawLH, _rawRH;
        private float _rawMouth = 0f;

        // Gestur State Timers
        private bool _prevIsAbove = false;
        private float _flapTimer = 0f;

        // Thread UDP
        private UdpClient _udpClient;
        private Thread _receiveThread;
        private volatile bool _isRunning = false;

        private void Awake()
        {
            StartUDPListener();
        }

        private void OnEnable()
        {
            if (!_isRunning)
            {
                StartUDPListener();
            }
        }

        private void OnDisable()
        {
            StopUDPListener();
        }

        private void OnDestroy()
        {
            StopUDPListener();
        }

        private void OnApplicationQuit()
        {
            StopUDPListener();
        }

        private void StartUDPListener()
        {
            if (_isRunning) return;

            try
            {
                _udpClient = new UdpClient(port);
                _isRunning = true;
                _receiveThread = new Thread(ReceiveDataLoop)
                {
                    IsBackground = true,
                    Name = "UDP_Pose_Receiver_Thread"
                };
                _receiveThread.Start();
                Debug.Log($"<color=#00FF88>[UDPPoseReceiver]</color> Berhasil mendengarkan port UDP {port}.");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[UDPPoseReceiver] Gagal mengikat port {port}: {ex.Message}. Keyboard fallback akan aktif.");
                _isRunning = false;
            }
        }

        private void StopUDPListener()
        {
            _isRunning = false;

            if (_udpClient != null)
            {
                try
                {
                    _udpClient.Close();
                }
                catch (Exception) { }
                _udpClient = null;
            }

            if (_receiveThread != null && _receiveThread.IsAlive)
            {
                _receiveThread.Join(100);
                _receiveThread = null;
            }
        }

        /// <summary>
        /// Loop eksekusi penerimaan data UDP di background thread.
        /// </summary>
        private void ReceiveDataLoop()
        {
            IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, port);

            while (_isRunning)
            {
                try
                {
                    if (_udpClient == null) break;

                    byte[] data = _udpClient.Receive(ref remoteEndPoint);
                    if (data == null || data.Length == 0) continue;

                    string text = Encoding.UTF8.GetString(data).Trim();
                    ParsePoseCSV(text);
                }
                catch (SocketException)
                {
                    // Wajar terjadi saat socket ditutup oleh Unity
                    break;
                }
                catch (Exception ex)
                {
                    if (_isRunning)
                    {
                        Debug.LogWarning($"[UDPPoseReceiver] Galat saat menerima paket UDP: {ex.Message}");
                    }
                }
            }
        }

        /// <summary>
        /// Parsing string CSV 12-float atau 13-float dari modul Python.
        /// Format: LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y[,MOUTH_OPEN]
        /// </summary>
        private void ParsePoseCSV(string csv)
        {
            string[] tokens = csv.Split(new char[] { ',', ';' }, StringSplitOptions.RemoveEmptyEntries);
            if (tokens.Length < 12) return;

            float[] v = new float[tokens.Length];
            for (int i = 0; i < tokens.Length; i++)
            {
                if (!float.TryParse(tokens[i], NumberStyles.Float, CultureInfo.InvariantCulture, out v[i]))
                {
                    return; // Gagal parsing float
                }
            }

            lock (_dataLock)
            {
                _rawLS = new Vector2(v[0], v[1]);
                _rawRS = new Vector2(v[2], v[3]);
                _rawLW = new Vector2(v[4], v[5]);
                _rawRW = new Vector2(v[6], v[7]);
                _rawLH = new Vector2(v[8], v[9]);
                _rawRH = new Vector2(v[10], v[11]);

                // Elemen ke-13 adalah skor bukaan mulut
                _rawMouth = (tokens.Length >= 13) ? v[12] : 0f;

                _lastPacketMs = _stopwatch.ElapsedMilliseconds;
                _hasNewPacket = true;
            }
        }

        private void Update()
        {
            long nowMs = _stopwatch.ElapsedMilliseconds;
            bool hadRecentPacket = (nowMs - _lastPacketMs) <= (long)(timeoutSeconds * 1000f);

            Vector2 targetLS, targetRS, targetLW, targetRW, targetLH, targetRH;
            float targetMouth;

            lock (_dataLock)
            {
                _isConnected = hadRecentPacket;
                _isPoseDetected = hadRecentPacket && _hasNewPacket;

                targetLS = _rawLS;
                targetRS = _rawRS;
                targetLW = _rawLW;
                targetRW = _rawRW;
                targetLH = _rawLH;
                targetRH = _rawRH;
                targetMouth = _rawMouth;
            }

            // 1. Terapkan Smoothing Vector2.Lerp (sesuai konteks.md = Time.deltaTime * 12f)
            float lerpFactor = Mathf.Clamp01(Time.deltaTime * smoothingSpeed);

            if (_isConnected)
            {
                _smoothedLS = Vector2.Lerp(_smoothedLS, targetLS, lerpFactor);
                _smoothedRS = Vector2.Lerp(_smoothedRS, targetRS, lerpFactor);
                _smoothedLW = Vector2.Lerp(_smoothedLW, targetLW, lerpFactor);
                _smoothedRW = Vector2.Lerp(_smoothedRW, targetRW, lerpFactor);
                _smoothedLH = Vector2.Lerp(_smoothedLH, targetLH, lerpFactor);
                _smoothedRH = Vector2.Lerp(_smoothedRH, targetRH, lerpFactor);
                _smoothedMouth = Mathf.Lerp(_smoothedMouth, targetMouth, lerpFactor);
            }

            // 2. Kalkulasi Kemudi Terbang (Berdasarkan perbedaan tinggi pergelangan tangan)
            // Sesuai konteks.md Bagian 4.1: tiltDelta = LeftWrist.y - RightWrist.y
            float tiltDelta = _smoothedLW.y - _smoothedRW.y;
            if (Mathf.Abs(tiltDelta) < turnDeadzone)
            {
                _turnInput = 0f;
            }
            else
            {
                _turnInput = Mathf.Clamp(tiltDelta * turnMultiplier, -1f, 1f);
            }

            // 3. Kalkulasi Gestur Sesuai Aturan konteks.md Bagian 4.2
            // a. Desa 1 (Pollution): Kepakan Sayap (LW.y < LS.y && RW.y < RS.y)
            bool isAbove = (_smoothedLW.y < _smoothedLS.y) && (_smoothedRW.y < _smoothedRS.y);
            if (isAbove != _prevIsAbove)
            {
                _flapTimer = 0.6f;
                _prevIsAbove = isAbove;
            }

            if (_flapTimer > 0f)
            {
                _flapTimer -= Time.deltaTime;
                _isFlapping = true;
            }
            else
            {
                _isFlapping = false;
            }

            // b. Desa 2 (Wildfire): Sembur Air (Buka Mulut > 0.45f ATAU Tangan Rapat di Dada)
            // Jarak tangan di depan dada < 0.14f dan di antara bahu & pinggul
            _isHandsTogether = (Vector2.Distance(_smoothedLW, _smoothedRW) < 0.14f) &&
                               (_smoothedLW.y > _smoothedLS.y - 0.05f && _smoothedLW.y < _smoothedLH.y);

            _isWaterBreathing = (_smoothedMouth > 0.45f) || _isHandsTogether;

            // c. Desa 3 (Drought): Panggil Hujan Embun (Tangan diangkat tinggi di atas kepala)
            _isHandsHighUp = (_smoothedLW.y < _smoothedLS.y - 0.12f) && (_smoothedRW.y < _smoothedRS.y - 0.12f);

            // 4. Keyboard Fallback (Jika diaktifkan & ditekan oleh pengguna)
            if (enableKeyboardFallback)
            {
                HandleKeyboardFallback();
            }
        }

        /// <summary>
        /// Menyediakan kontrol alternatif melalui keyboard sehingga developer/penguji
        /// dapat mengendalikan naga dan menguji 3 desa kapan saja tanpa webcam.
        /// Mendukung Input System baru (Keyboard.current) maupun Legacy Input Manager.
        /// </summary>
        private void HandleKeyboardFallback()
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null)
            {
                float h = 0f;
                if (kb.leftArrowKey.isPressed || kb.aKey.isPressed) h -= 1f;
                if (kb.rightArrowKey.isPressed || kb.dKey.isPressed) h += 1f;
                if (Mathf.Abs(h) > 0.01f)
                {
                    _turnInput = Mathf.Clamp(h, -1f, 1f);
                }

                // Tombol 1 atau Space: Simulasi Kepakan Sayap (Desa 1)
                if (kb.digit1Key.isPressed || kb.numpad1Key.isPressed || kb.spaceKey.isPressed)
                {
                    _isFlapping = true;
                    _flapTimer = 0.4f;
                }

                // Tombol 2 atau F: Simulasi Semburan Air Naga (Desa 2)
                if (kb.digit2Key.isPressed || kb.numpad2Key.isPressed || kb.fKey.isPressed)
                {
                    _isWaterBreathing = true;
                    _smoothedMouth = 1.0f;
                }

                // Tombol 3 atau R: Simulasi Panggil Hujan Embun (Desa 3)
                if (kb.digit3Key.isPressed || kb.numpad3Key.isPressed || kb.rKey.isPressed)
                {
                    _isHandsHighUp = true;
                }

                return; // Selesai diproses oleh Input System baru, jangan jalankan legacy input
            }
#else
            // Fallback Legacy Input Manager HANYA jika paket Input System tidak terpasang
            try
            {
                // Belok Kiri / Kanan menggunakan Panah atau A / D
                float horizontalAxis = Input.GetAxisRaw("Horizontal");
                if (Mathf.Abs(horizontalAxis) > 0.01f)
                {
                    _turnInput = Mathf.Clamp(horizontalAxis, -1f, 1f);
                }

                // Tombol 1 atau Space: Simulasi Kepakan Sayap (Desa 1)
                if (Input.GetKey(KeyCode.Alpha1) || Input.GetKey(KeyCode.Keypad1) || Input.GetKey(KeyCode.Space))
                {
                    _isFlapping = true;
                    _flapTimer = 0.4f;
                }

                // Tombol 2 atau F: Simulasi Semburan Air Naga (Desa 2)
                if (Input.GetKey(KeyCode.Alpha2) || Input.GetKey(KeyCode.Keypad2) || Input.GetKey(KeyCode.F))
                {
                    _isWaterBreathing = true;
                    _smoothedMouth = 1.0f;
                }

                // Tombol 3 atau R: Simulasi Panggil Hujan Embun (Desa 3)
                if (Input.GetKey(KeyCode.Alpha3) || Input.GetKey(KeyCode.Keypad3) || Input.GetKey(KeyCode.R))
                {
                    _isHandsHighUp = true;
                }
            }
            catch (Exception)
            {
                // Mencegah crash jika legacy input dinonaktifkan di Player Settings
            }
#endif
        }

        private void OnGUI()
        {
            // Panel info kecil di pojok kiri atas game view saat Play Mode
            if (!Application.isPlaying) return;

            GUI.color = _isConnected ? Color.green : (enableKeyboardFallback ? Color.yellow : Color.red);
            string status = _isConnected ? "TERHUBUNG (Python UDP)" : (enableKeyboardFallback ? "KEYBOARD FALLBACK AKTIF" : "TERPUTUS");
            string info = $"[PoseReceiver] {status}\nTurn: {_turnInput:F2} | Flap: {_isFlapping} | Water: {_isWaterBreathing} | High: {_isHandsHighUp}";
            GUI.Label(new Rect(10, 10, 400, 45), info);
        }
    }
}
