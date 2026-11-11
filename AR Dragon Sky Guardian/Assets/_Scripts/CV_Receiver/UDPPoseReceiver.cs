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
    /// mendukung gestur dinamis Minecraft Elytra (Flapping, Tuck Dive, T-Pose Glide, Pose Y Climb),
    /// serta menyediakan Keyboard Fallback otomatis saat offline atau saat tombol ditekan.
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
        public Vector2 LeftElbow => _smoothedLE;
        public Vector2 RightElbow => _smoothedRE;
        public Vector2 LeftHip => _smoothedLH;
        public Vector2 RightHip => _smoothedRH;

        public float MouthOpen => _smoothedMouth;
        public bool IsWaterBreathing => _isWaterBreathing;
        public float TurnInput => _turnInput;
        public float PitchInput => _pitchInput;
        public float BodyPitch => _bodyPitch;

        public bool IsYPose => _isYPose;
        public bool IsTPose => _isTPose;
        public bool IsAPose => _isAPose;
        public bool IsTuckDive => _isTuckDive;
        public bool IsDiving => _isTuckDive || _isAPose;

        public bool IsFlapping => _isFlapping;
        public float FlapPower => _flapPower;
        public bool IsHandsTogether => _isHandsTogether;
        public bool IsHandsHighUp => _isHandsHighUp;

        // ==========================================
        // Variabel Internal Smoothing & Status
        // ==========================================
        [Header("Status Telemetri (Read Only)")]
        [SerializeField] private bool _isConnected = false;
        [SerializeField] private bool _isPoseDetected = false;
        [SerializeField] private float _turnInput = 0f;
        [SerializeField] private float _pitchInput = 0f;
        [SerializeField] private float _bodyPitch = 0f;
        [SerializeField] private bool _isYPose = false;
        [SerializeField] private bool _isTPose = true;
        [SerializeField] private bool _isAPose = false;
        [SerializeField] private bool _isTuckDive = false;
        [SerializeField] private bool _isFlapping = false;
        [SerializeField] private float _flapPower = 0f;
        [SerializeField] private float _smoothedMouth = 0f;
        [SerializeField] private bool _isWaterBreathing = false;
        [SerializeField] private bool _isHandsTogether = false;
        [SerializeField] private bool _isHandsHighUp = false;

        private Vector2 _smoothedLS = new Vector2(0.40f, 0.40f);
        private Vector2 _smoothedRS = new Vector2(0.60f, 0.40f);
        private Vector2 _smoothedLW = new Vector2(0.35f, 0.60f);
        private Vector2 _smoothedRW = new Vector2(0.65f, 0.60f);
        private Vector2 _smoothedLE = new Vector2(0.32f, 0.50f);
        private Vector2 _smoothedRE = new Vector2(0.68f, 0.50f);
        private Vector2 _smoothedLH = new Vector2(0.42f, 0.70f);
        private Vector2 _smoothedRH = new Vector2(0.58f, 0.70f);
        private Vector2 _smoothedNose = new Vector2(0.50f, 0.25f);

        // Thread-safe raw data buffer
        private readonly object _dataLock = new object();
        private readonly System.Diagnostics.Stopwatch _stopwatch = System.Diagnostics.Stopwatch.StartNew();
        private long _lastPacketMs = -999999;
        private bool _hasNewPacket = false;
        private Vector2 _rawLS, _rawRS, _rawLW, _rawRW, _rawLH, _rawRH;
        private Vector2 _rawLE = new Vector2(0.32f, 0.50f);
        private Vector2 _rawRE = new Vector2(0.68f, 0.50f);
        private Vector2 _rawNose = new Vector2(0.50f, 0.25f);
        private bool _hasElbows = false;
        private bool _hasExtendedFlags = false;
        private bool _hasBodyPitch = false;
        private bool _rawIsDiveFlag = false;
        private bool _rawIsFlapFlag = false;
        private float _rawFlapFreq = 0f;
        private float _rawFlapPower = 0f;
        private float _rawBodyPitch = 0f;
        private float _rawMouth = 0f;

        // Gestur State Timers & Tracking
        private float _flapTimer = 0f;
        private float _prevWristY = 0.5f;

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
        /// Parsing string CSV:
        /// Format 13 float: LS_X,LS_Y,RS_X,RS_Y,LW_X,LW_Y,RW_X,RW_Y,LH_X,LH_Y,RH_X,RH_Y,MOUTH_OPEN
        /// Format 21 float: ... + LE_X,LE_Y,RE_X,RE_Y,IS_DIVE,IS_FLAP,FLAP_FREQ,FLAP_POWER
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
                    return;
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

                _rawMouth = (tokens.Length >= 13) ? v[12] : 0f;

                if (tokens.Length >= 17)
                {
                    _rawLE = new Vector2(v[13], v[14]);
                    _rawRE = new Vector2(v[15], v[16]);
                    _hasElbows = true;
                }
                else
                {
                    _hasElbows = false;
                }

                if (tokens.Length >= 21)
                {
                    _rawIsDiveFlag = v[17] > 0.5f;
                    _rawIsFlapFlag = v[18] > 0.5f;
                    _rawFlapFreq = v[19];
                    _rawFlapPower = v[20];
                    _hasExtendedFlags = true;
                }
                else
                {
                    _hasExtendedFlags = false;
                }

                if (tokens.Length >= 22)
                {
                    _rawBodyPitch = v[21];
                    _hasBodyPitch = true;
                }
                else
                {
                    _hasBodyPitch = false;
                }

                if (tokens.Length >= 24)
                {
                    _rawNose = new Vector2(v[22], v[23]);
                }

                _lastPacketMs = _stopwatch.ElapsedMilliseconds;
                _hasNewPacket = true;
            }
        }

        private void Update()
        {
            long nowMs = _stopwatch.ElapsedMilliseconds;
            bool hadRecentPacket = (nowMs - _lastPacketMs) <= (long)(timeoutSeconds * 1000f);

            Vector2 targetLS, targetRS, targetLW, targetRW, targetLH, targetRH, targetLE, targetRE, targetNose;
            float targetMouth, targetBodyPitch;
            bool pyDiveFlag, pyFlapFlag;
            float pyFlapPower;
            bool hasElbowsData, hasFlagsData, hasBodyPitchData;

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
                targetLE = _rawLE;
                targetRE = _rawRE;
                targetNose = _rawNose;
                targetMouth = _rawMouth;
                targetBodyPitch = _rawBodyPitch;
                pyDiveFlag = _rawIsDiveFlag;
                pyFlapFlag = _rawIsFlapFlag;
                pyFlapPower = _rawFlapPower;
                hasElbowsData = _hasElbows;
                hasFlagsData = _hasExtendedFlags;
                hasBodyPitchData = _hasBodyPitch;
            }

            // 1. Pelicinan Koordinat Vector2.Lerp (smoothingSpeed = 12f)
            float lerpFactor = Mathf.Clamp01(Time.deltaTime * smoothingSpeed);

            if (_isConnected)
            {
                _smoothedLS = Vector2.Lerp(_smoothedLS, targetLS, lerpFactor);
                _smoothedRS = Vector2.Lerp(_smoothedRS, targetRS, lerpFactor);
                _smoothedLW = Vector2.Lerp(_smoothedLW, targetLW, lerpFactor);
                _smoothedRW = Vector2.Lerp(_smoothedRW, targetRW, lerpFactor);
                _smoothedLH = Vector2.Lerp(_smoothedLH, targetLH, lerpFactor);
                _smoothedRH = Vector2.Lerp(_smoothedRH, targetRH, lerpFactor);
                _smoothedNose = Vector2.Lerp(_smoothedNose, targetNose, lerpFactor);
                _smoothedMouth = Mathf.Lerp(_smoothedMouth, targetMouth, lerpFactor);

                if (hasElbowsData)
                {
                    _smoothedLE = Vector2.Lerp(_smoothedLE, targetLE, lerpFactor);
                    _smoothedRE = Vector2.Lerp(_smoothedRE, targetRE, lerpFactor);
                }
                else
                {
                    Vector2 midL = (_smoothedLS + _smoothedLW) * 0.5f;
                    Vector2 midR = (_smoothedRS + _smoothedRW) * 0.5f;
                    _smoothedLE = Vector2.Lerp(_smoothedLE, midL + new Vector2(-0.03f, 0.04f), lerpFactor);
                    _smoothedRE = Vector2.Lerp(_smoothedRE, midR + new Vector2(0.03f, 0.04f), lerpFactor);
                }
            }

            // 2. Kemudi Belok Horizontal (Berdasarkan perbedaan tinggi pergelangan tangan)
            float tiltDelta = _smoothedLW.y - _smoothedRW.y;
            if (Mathf.Abs(tiltDelta) < turnDeadzone)
            {
                _turnInput = 0f;
            }
            else
            {
                _turnInput = Mathf.Clamp(tiltDelta * turnMultiplier, -1f, 1f);
            }

            // 3. Deteksi Gestur Dinamis Minecraft Elytra:
            // a. TUCK DIVE (Foto Pengguna: Tangan mengepal di dada, siku mengarah ke bawah):
            float wristDist = Vector2.Distance(_smoothedLW, _smoothedRW);
            float shoulderDist = Vector2.Distance(_smoothedLS, _smoothedRS);
            if (shoulderDist < 0.05f) shoulderDist = 0.20f;

            bool elbowsBelowWrists = (_smoothedLE.y > _smoothedLW.y + 0.03f) && (_smoothedRE.y > _smoothedRW.y + 0.03f);
            bool elbowsBelowShoulders = (_smoothedLE.y > _smoothedLS.y + 0.05f) && (_smoothedRE.y > _smoothedRS.y + 0.05f);
            bool wristsAtChest = (_smoothedLW.y > _smoothedLS.y - 0.12f) && (_smoothedRW.y > _smoothedRS.y - 0.12f) &&
                                 (_smoothedLW.y < _smoothedLH.y - 0.06f) && (_smoothedRW.y < _smoothedRH.y - 0.06f);
            bool handsCompact = wristDist < (shoulderDist * 1.65f);
            bool geomTuckDive = elbowsBelowWrists && elbowsBelowShoulders && wristsAtChest && handsCompact;

            _isTuckDive = _isConnected && (hasFlagsData ? pyDiveFlag : geomTuckDive);

            // b. KEPAKAN SAYAP (Flapping: Fly Up + Speed Up):
            float curWristY = (_smoothedLW.y + _smoothedRW.y) * 0.5f;
            float wristSpeed = Mathf.Abs(curWristY - _prevWristY) / Mathf.Max(0.001f, Time.deltaTime);
            _prevWristY = curWristY;

            if (_isConnected && hasFlagsData && pyFlapFlag)
            {
                _flapTimer = 0.5f;
                _flapPower = Mathf.Clamp01(Mathf.Max(0.7f, pyFlapPower));
            }
            else if (wristSpeed > 0.8f && !_isTuckDive)
            {
                _flapTimer = 0.45f;
                _flapPower = Mathf.Clamp01(wristSpeed / 2.0f);
            }
            else if (_flapTimer > 0f)
            {
                _flapTimer -= Time.deltaTime;
            }

            _isFlapping = (_flapTimer > 0f);
            if (!_isFlapping) _flapPower = 0f;

            // c. ORIENTASI BADAN (Body Pitch: -1.0 s/d +1.0):
            // Fallback kalkulasi internal jika data Python UDP tidak menyertakan token ke-22
            Vector2 midShoulder = (_smoothedLS + _smoothedRS) * 0.5f;
            float headDist = midShoulder.y - _smoothedNose.y;
            float headRatio = headDist / shoulderDist;
            float internalBodyPitch = 0f;

            if (_isFlapping)
            {
                // Saat mengepak: Periksa apakah busur kepakan tangan diarahkan tinggi ke atas kepala
                float armAimOffset = midShoulder.y - curWristY;
                if (armAimOffset > 0.07f)
                {
                    internalBodyPitch = Mathf.Clamp01((armAimOffset - 0.07f) / 0.12f);
                }
                else if (armAimOffset < -0.10f)
                {
                    internalBodyPitch = -Mathf.Clamp01((Mathf.Abs(armAimOffset) - 0.10f) / 0.12f);
                }
                else
                {
                    internalBodyPitch = 0f;
                }
            }
            else
            {
                float headSignal = (headRatio - 0.48f) / 0.14f;
                if (Mathf.Abs(headSignal) > 0.22f)
                {
                    internalBodyPitch = Mathf.Clamp(Mathf.Sign(headSignal) * (Mathf.Abs(headSignal) - 0.22f) / 0.78f, -1f, 1f);
                }
            }

            float rawBP = hasBodyPitchData ? targetBodyPitch : internalBodyPitch;
            _bodyPitch = Mathf.Lerp(_bodyPitch, rawBP, lerpFactor);

            // d. POSE Y & A vs KEPAKAN SAYAP (DECOUPLING LENGKAP):
            // Saat tangan dikepakkan naik-turun, gerakan ayunan tangan TIDAK BOLEH memicu Pose Y atau Pose A!
            // Flapping itu sendiri adalah daya dorong (Speed Up + Fly Up), BUKAN kontrol kemudi pitch angguk-angguk!
            float dyL = _smoothedLW.y - _smoothedLS.y;
            float dyR = _smoothedRW.y - _smoothedRS.y;
            float avgDeltaY = (dyL + dyR) * 0.5f;

            bool isYDetected = ((dyL < -0.04f && dyR < -0.04f) || (avgDeltaY < -0.05f)) && !_isTuckDive && !_isFlapping;
            bool isADetected = ((dyL > 0.05f && dyR > 0.05f) || (avgDeltaY > 0.06f)) && !_isTuckDive && !_isFlapping;

            if (_isTuckDive)
            {
                _isAPose = true;
                _isYPose = false;
                _isTPose = false;
                _pitchInput = -1.0f; // Dive tajam
            }
            else if (_isFlapping)
            {
                // SAAT MENGEPAK: Reset isYPose & isAPose agar naga TIDAK melihat ke atas lalu ke bawah!
                _isYPose = false;
                _isAPose = false;
                _isTPose = false;
                _pitchInput = _bodyPitch; // Pitch input mengikuti orientasi badan jika ada
            }
            else if (isYDetected)
            {
                _isYPose = true;
                _isTPose = false;
                _isAPose = false;
                float climbStrength = Mathf.Clamp01((-avgDeltaY) / 0.12f);
                _pitchInput = Mathf.Max(0.65f, climbStrength);
            }
            else if (isADetected)
            {
                _isAPose = true;
                _isYPose = false;
                _isTPose = false;
                float diveStrength = Mathf.Clamp01(avgDeltaY / 0.12f);
                _pitchInput = -Mathf.Max(0.50f, diveStrength);
            }
            else
            {
                // e. POSE T (Elytra Glide: Tangan mendatar, sedikit dive -5 deg)
                _isTPose = true;
                _isYPose = false;
                _isAPose = false;
                _pitchInput = -0.10f; // Sedikit menunduk untuk glide slope alami
            }

            // f. Semburan Air (Mouth open > 0.45 atau kedua tangan rapat di dada saat bukan dive)
            _isHandsTogether = (wristDist < 0.12f) && (_smoothedLW.y > _smoothedLS.y) && (_smoothedLW.y < _smoothedLH.y);
            _isWaterBreathing = (_smoothedMouth > 0.45f) || (_isHandsTogether && !_isTuckDive);

            // g. Panggil Hujan Embun (Tangan diangkat tinggi di atas kepala)
            _isHandsHighUp = (_smoothedLW.y < _smoothedLS.y - 0.14f) && (_smoothedRW.y < _smoothedRS.y - 0.14f);

            // 4. Keyboard Fallback
            if (enableKeyboardFallback)
            {
                HandleKeyboardFallback();
            }
        }

        /// <summary>
        /// Kontrol keyboard fallback:
        /// - Spasi / W : Kepak Sayap (Fly Up + Speed Up)
        /// - S         : Tuck Dive (Terjun Menukik Tajam -45 deg)
        /// - T         : T-Pose Elytra Glide (-5 deg)
        /// - Up / Y    : Pitch Up (Arahkan badan ke atas / Climb)
        /// - Down      : Pitch Down
        /// - A / Left  : Belok Kiri
        /// - D / Right : Belok Kanan
        /// </summary>
        private void HandleKeyboardFallback()
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null)
            {
                bool keyFlap = kb.spaceKey.isPressed || kb.wKey.isPressed;
                bool keyDive = kb.sKey.isPressed;
                bool keyPitchUp = kb.upArrowKey.isPressed || kb.yKey.isPressed;
                bool keyPitchDown = kb.downArrowKey.isPressed;
                bool keyGlide = kb.tKey.isPressed;
                bool keyLeft = kb.leftArrowKey.isPressed || kb.qKey.isPressed;
                bool keyRight = kb.rightArrowKey.isPressed || kb.dKey.isPressed;

                bool isAnyAction = keyFlap || keyDive || keyPitchUp || keyPitchDown || keyGlide || keyLeft || keyRight;

                // Jika terhubung UDP dan tidak menyentuh keyboard, biarkan data kamera bekerja
                if (_isConnected && !isAnyAction)
                {
                    return;
                }

                // Kemudi Belok
                if (keyLeft || keyRight || !_isConnected)
                {
                    float h = 0f;
                    if (keyLeft) h -= 1f;
                    if (keyRight) h += 1f;
                    _turnInput = Mathf.Clamp(h, -1f, 1f);
                }

                // Aksi Vertikal / Gestur
                if (keyDive)
                {
                    _isTuckDive = true;
                    _isAPose = true;
                    _isYPose = false;
                    _isTPose = false;
                    _pitchInput = -1.0f;
                    _isFlapping = false;
                }
                else if (keyPitchUp)
                {
                    _isYPose = true;
                    _isTPose = false;
                    _isAPose = false;
                    _isTuckDive = false;
                    _pitchInput = 1.0f;
                }
                else if (keyPitchDown)
                {
                    _isAPose = true;
                    _isYPose = false;
                    _isTPose = false;
                    _isTuckDive = false;
                    _pitchInput = -0.6f;
                }
                else if (keyGlide || !_isConnected)
                {
                    _isTPose = true;
                    _isYPose = false;
                    _isAPose = false;
                    _isTuckDive = false;
                    _pitchInput = -0.10f;
                }

                if (keyFlap)
                {
                    _isFlapping = true;
                    _flapTimer = 0.5f;
                    _flapPower = 1.0f;
                    _isYPose = false;
                    _isAPose = false;
                    _isTPose = false;

                    if (keyPitchUp)
                    {
                        _bodyPitch = 1.0f;
                        _pitchInput = 1.0f;
                    }
                    else if (keyPitchDown)
                    {
                        _bodyPitch = -1.0f;
                        _pitchInput = -0.6f;
                    }
                    else
                    {
                        _bodyPitch = 0.0f;
                        _pitchInput = -0.05f;
                    }
                }

                // Aksi Khusus Desa
                if (kb.digit1Key.isPressed || kb.numpad1Key.isPressed)
                {
                    _isFlapping = true;
                    _flapTimer = 0.5f;
                    _flapPower = 1.0f;
                }

                if (kb.digit2Key.isPressed || kb.numpad2Key.isPressed || kb.fKey.isPressed)
                {
                    _isWaterBreathing = true;
                    _smoothedMouth = 1.0f;
                }

                if (kb.digit3Key.isPressed || kb.numpad3Key.isPressed || kb.rKey.isPressed)
                {
                    _isHandsHighUp = true;
                }

                return;
            }
#else
            try
            {
                bool keyFlap = Input.GetKey(KeyCode.Space) || Input.GetKey(KeyCode.W);
                bool keyDive = Input.GetKey(KeyCode.S);
                bool keyPitchUp = Input.GetKey(KeyCode.UpArrow) || Input.GetKey(KeyCode.Y);
                bool keyPitchDown = Input.GetKey(KeyCode.DownArrow);
                bool keyGlide = Input.GetKey(KeyCode.T);
                bool keyLeft = Input.GetKey(KeyCode.LeftArrow) || Input.GetKey(KeyCode.Q);
                bool keyRight = Input.GetKey(KeyCode.RightArrow) || Input.GetKey(KeyCode.D);

                bool isAnyAction = keyFlap || keyDive || keyPitchUp || keyPitchDown || keyGlide || keyLeft || keyRight;

                if (_isConnected && !isAnyAction) return;

                if (keyLeft || keyRight || !_isConnected)
                {
                    float h = 0f;
                    if (keyLeft) h -= 1f;
                    if (keyRight) h += 1f;
                    _turnInput = Mathf.Clamp(h, -1f, 1f);
                }

                if (keyDive)
                {
                    _isTuckDive = true;
                    _isAPose = true;
                    _isYPose = false;
                    _isTPose = false;
                    _pitchInput = -1.0f;
                }
                else if (keyPitchUp)
                {
                    _isYPose = true;
                    _isTPose = false;
                    _isAPose = false;
                    _isTuckDive = false;
                    _pitchInput = 1.0f;
                }
                else if (keyPitchDown)
                {
                    _isAPose = true;
                    _isYPose = false;
                    _isTPose = false;
                    _isTuckDive = false;
                    _pitchInput = -0.6f;
                }
                else if (keyGlide || !_isConnected)
                {
                    _isTPose = true;
                    _isYPose = false;
                    _isAPose = false;
                    _isTuckDive = false;
                    _pitchInput = -0.10f;
                }

                if (keyFlap)
                {
                    _isFlapping = true;
                    _flapTimer = 0.5f;
                    _flapPower = 1.0f;
                    _isYPose = false;
                    _isAPose = false;
                    _isTPose = false;

                    if (keyPitchUp)
                    {
                        _bodyPitch = 1.0f;
                        _pitchInput = 1.0f;
                    }
                    else if (keyPitchDown)
                    {
                        _bodyPitch = -1.0f;
                        _pitchInput = -0.6f;
                    }
                    else
                    {
                        _bodyPitch = 0.0f;
                        _pitchInput = -0.05f;
                    }
                }
            }
            catch (Exception) { }
#endif
        }

        [Tooltip("Tampilkan teks debug status di pojok kiri atas")]
        public bool showDebugGUI = false;

        private void OnGUI()
        {
            if (!Application.isPlaying || !showDebugGUI) return;

            GUI.color = _isConnected ? Color.green : (enableKeyboardFallback ? Color.yellow : Color.red);
            string status = _isConnected ? "TERHUBUNG (Python UDP)" : (enableKeyboardFallback ? "KEYBOARD FALLBACK AKTIF" : "TERPUTUS");
            string info = $"[PoseReceiver] {status}\nTurn: {_turnInput:F2} | Pitch: {_pitchInput:F2} | Flap: {_isFlapping} | Dive: {_isTuckDive}";
            GUI.Label(new Rect(10, 10, 400, 45), info);
        }
    }
}
