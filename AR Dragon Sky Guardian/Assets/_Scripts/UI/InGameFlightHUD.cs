using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;
using DragonWingAR.CV;
using DragonWingAR.Controllers;

namespace DragonWingAR.UI
{
    /// <summary>
    /// GUI Awal / In-Game HUD Lengkap untuk AR Dragon Sky Guardian:
    /// 1. Kotak Preview Kamera (Picture-in-Picture) di bagian kanan atas layar (port 5053).
    /// 2. Panel Telemetri Penerbangan Naga (Kecepatan, Ketinggian, Kemudi Roll/Yaw).
    /// 3. Indikator Status Gestur (Kepakan Sayap, Semburan Air, Hujan Embun).
    /// 4. Fallback Wireframe Skeleton Avatar jika video webcam belum tersambung.
    /// </summary>
    public class InGameFlightHUD : MonoBehaviour
    {
        [Header("Pengaturan Preview Kamera PIP (Kanan Atas)")]
        [Tooltip("Port UDP untuk menerima streaming frame video JPEG dari Python (default: 5053)")]
        public int videoPort = 5053;

        [Tooltip("Lebar kotak preview di layar")]
        public float previewWidth = 260f;

        [Tooltip("Tinggi kotak preview di layar (rasio 16:9)")]
        public float previewHeight = 146f;

        [Tooltip("Jarak margin dari tepi kanan dan atas layar")]
        public Vector2 previewMargin = new Vector2(25f, 20f);

        [Header("Referensi Komponen")]
        [SerializeField] private UDPPoseReceiver poseReceiver;
        [SerializeField] private DragonFlightController flightController;

        // Video Streaming Internals
        private UdpClient _videoUdpClient;
        private Thread _videoThread;
        private volatile bool _isVideoRunning = false;
        private readonly object _videoLock = new object();
        private byte[] _pendingJpegBytes = null;
        private bool _hasNewFrame = false;
        private Texture2D _videoTexture;
        private Texture2D _boxBgTexture;
        private Texture2D _barTexture;
        private double _lastFrameTime = 0;
        private bool _isVideoConnected = false;

        private void Awake()
        {
            if (poseReceiver == null) poseReceiver = FindFirstObjectByType<UDPPoseReceiver>();
            if (flightController == null) flightController = FindFirstObjectByType<DragonFlightController>();

            _videoTexture = new Texture2D(256, 144, TextureFormat.RGB24, false);

            // Buat tekstur polos untuk background GUI
            _boxBgTexture = new Texture2D(1, 1);
            _boxBgTexture.SetPixel(0, 0, new Color(0.08f, 0.08f, 0.10f, 0.85f));
            _boxBgTexture.Apply();

            _barTexture = new Texture2D(1, 1);
            _barTexture.SetPixel(0, 0, Color.white);
            _barTexture.Apply();

            StartVideoReceiver();
        }

        private void OnEnable()
        {
            if (!_isVideoRunning) StartVideoReceiver();
        }

        private void OnDisable()
        {
            StopVideoReceiver();
        }

        private void OnDestroy()
        {
            StopVideoReceiver();
            if (_videoTexture != null) Destroy(_videoTexture);
            if (_boxBgTexture != null) Destroy(_boxBgTexture);
            if (_barTexture != null) Destroy(_barTexture);
        }

        private void StartVideoReceiver()
        {
            if (_isVideoRunning) return;

            try
            {
                _videoUdpClient = new UdpClient(videoPort);
                _isVideoRunning = true;
                _videoThread = new Thread(VideoReceiveLoop)
                {
                    IsBackground = true,
                    Name = "UDP_Video_PIP_Thread"
                };
                _videoThread.Start();
                Debug.Log($"<color=#00FF88>[InGameFlightHUD]</color> Mendengarkan stream video PIP di port {videoPort}.");
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[InGameFlightHUD] Port video {videoPort} tidak dapat dibuka: {ex.Message}. Mode wireframe aktif.");
                _isVideoRunning = false;
            }
        }

        private void StopVideoReceiver()
        {
            _isVideoRunning = false;
            if (_videoUdpClient != null)
            {
                try { _videoUdpClient.Close(); } catch { }
                _videoUdpClient = null;
            }
            if (_videoThread != null && _videoThread.IsAlive)
            {
                _videoThread.Join(100);
                _videoThread = null;
            }
        }

        private void VideoReceiveLoop()
        {
            IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, videoPort);
            while (_isVideoRunning)
            {
                try
                {
                    if (_videoUdpClient == null) break;
                    byte[] data = _videoUdpClient.Receive(ref remoteEndPoint);
                    if (data == null || data.Length == 0) continue;

                    lock (_videoLock)
                    {
                        _pendingJpegBytes = data;
                        _hasNewFrame = true;
                    }
                }
                catch (SocketException) { break; }
                catch (Exception) { }
            }
        }

        private void Update()
        {
            byte[] bytesToLoad = null;
            lock (_videoLock)
            {
                if (_hasNewFrame && _pendingJpegBytes != null)
                {
                    bytesToLoad = _pendingJpegBytes;
                    _hasNewFrame = false;
                    _lastFrameTime = Time.realtimeSinceStartupAsDouble;
                }
            }

            if (bytesToLoad != null && _videoTexture != null)
            {
                _videoTexture.LoadImage(bytesToLoad);
            }

            _isVideoConnected = (Time.realtimeSinceStartupAsDouble - _lastFrameTime) < 1.5;
        }

        private void OnGUI()
        {
            if (!Application.isPlaying) return;

            DrawCameraPreviewBox();
            DrawFlightHUD();
            DrawControlsQuickGuide();
        }

        /// <summary>
        /// Menggambar kotak preview kamera (PIP) di pojok kanan atas layar.
        /// </summary>
        private void DrawCameraPreviewBox()
        {
            float boxX = Screen.width - previewWidth - previewMargin.x;
            float boxY = previewMargin.y;
            Rect containerRect = new Rect(boxX, boxY, previewWidth, previewHeight + 28f);

            // 1. Background Frame Panel
            GUI.DrawTexture(containerRect, _boxBgTexture);

            // Garis bingkai neon
            Color borderColor = _isVideoConnected ? new Color(0f, 1f, 0.7f, 0.9f) : new Color(1f, 0.6f, 0f, 0.8f);
            DrawOutline(containerRect, 2, borderColor);

            // 2. Header Status Bar
            Rect headerRect = new Rect(boxX + 8, boxY + 5, previewWidth - 16, 20);
            string statusBadge = _isVideoConnected ? "● LIVE WEBCAM" : "● WIREFRAME STANDBY";
            GUI.color = _isVideoConnected ? Color.green : Color.yellow;
            GUI.Label(headerRect, statusBadge);

            GUI.color = new Color(0.8f, 0.8f, 0.8f, 0.9f);
            GUIStyle rightStyle = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleRight };
            GUI.Label(headerRect, "PORT: " + videoPort, rightStyle);

            // 3. Area Konten Preview (Video Feed atau Skeleton Wireframe)
            Rect videoRect = new Rect(boxX + 4, boxY + 24, previewWidth - 8, previewHeight);

            if (_isVideoConnected && _videoTexture != null)
            {
                GUI.color = Color.white;
                GUI.DrawTexture(videoRect, _videoTexture, ScaleMode.ScaleToFit);
            }
            else
            {
                // Fallback: Wireframe Pose Avatar jika video stream belum aktif
                DrawSkeletonWireframe(videoRect);
            }
        }

        /// <summary>
        /// Menggambar avatar kerangka visual interaktif saat stream video belum terhubung.
        /// Mendukung sendi siku (elbow) dan visualisasi gestur dinamis Minecraft Elytra.
        /// </summary>
        private void DrawSkeletonWireframe(Rect area)
        {
            // Background area hitam
            GUI.color = new Color(0.04f, 0.04f, 0.06f, 1f);
            GUI.DrawTexture(area, _barTexture);

            // Garis grid radar
            GUI.color = new Color(0.2f, 0.25f, 0.3f, 0.5f);
            float midX = area.x + area.width * 0.5f;
            float midY = area.y + area.height * 0.5f;
            DrawLine(new Vector2(area.x, midY), new Vector2(area.xMax, midY), 1, GUI.color);
            DrawLine(new Vector2(midX, area.y), new Vector2(midX, area.yMax), 1, GUI.color);

            if (poseReceiver != null)
            {
                Vector2 toAreaPx(Vector2 normPt)
                {
                    return new Vector2(area.x + normPt.x * area.width, area.y + normPt.y * area.height);
                }

                Vector2 ls = toAreaPx(poseReceiver.LeftShoulder);
                Vector2 rs = toAreaPx(poseReceiver.RightShoulder);
                Vector2 le = toAreaPx(poseReceiver.LeftElbow);
                Vector2 re = toAreaPx(poseReceiver.RightElbow);
                Vector2 lw = toAreaPx(poseReceiver.LeftWrist);
                Vector2 rw = toAreaPx(poseReceiver.RightWrist);
                Vector2 lh = toAreaPx(poseReceiver.LeftHip);
                Vector2 rh = toAreaPx(poseReceiver.RightHip);

                // Garis tulang kerangka (termasuk lengan bersiku)
                Color boneCol = new Color(0f, 1f, 0.8f, 0.9f);
                DrawLine(ls, rs, 2, boneCol);
                DrawLine(ls, le, 2, boneCol);
                DrawLine(le, lw, 2, boneCol);
                DrawLine(rs, re, 2, boneCol);
                DrawLine(re, rw, 2, boneCol);
                DrawLine(ls, lh, 2, boneCol);
                DrawLine(rs, rh, 2, boneCol);
                DrawLine(lh, rh, 2, boneCol);

                // Sendi siku
                DrawCircle(le, 4, new Color(1f, 0.7f, 0.1f, 0.9f));
                DrawCircle(re, 4, new Color(1f, 0.7f, 0.1f, 0.9f));

                // Sendi tangan & warna status
                Color handCol;
                string poseLabel;
                if (poseReceiver.IsTuckDive)
                {
                    handCol = new Color(1f, 0.3f, 0f);
                    poseLabel = "● DIVE TERJUN (TUCK DIVE ↓↓)";
                }
                else if (poseReceiver.IsFlapping)
                {
                    handCol = new Color(0.1f, 1f, 0.4f);
                    poseLabel = "● KEPAK SAYAP (FLY UP + SPEED UP)";
                }
                else if (poseReceiver.IsYPose)
                {
                    handCol = new Color(0f, 1f, 0.9f);
                    poseLabel = "● ARAH ATAS (CLIMB SOARING ↑)";
                }
                else
                {
                    handCol = new Color(1f, 0.9f, 0.2f);
                    poseLabel = "● POSE T (ELYTRA GLIDE ~ -5°)";
                }

                DrawCircle(lw, 6, handCol);
                DrawCircle(rw, 6, handCol);

                GUI.color = handCol;
                GUIStyle pStyle = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.UpperCenter, fontStyle = FontStyle.Bold, fontSize = 11 };
                GUI.Label(new Rect(area.x, area.y + 4, area.width, 20), poseLabel, pStyle);

                // Indikator semburan air
                if (poseReceiver.IsWaterBreathing)
                {
                    Vector2 headCenter = Vector2.Lerp(ls, rs, 0.5f) + Vector2.up * (-15f);
                    DrawCircle(headCenter, 8, Color.cyan);
                }
            }

            GUI.color = new Color(0.7f, 0.7f, 0.7f, 0.8f);
            GUIStyle centerStyle = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter, fontSize = 10 };
            GUI.Label(new Rect(area.x, area.yMax - 20, area.width, 20), "Kepak: FlyUp | T-Pose: Glide | Dive: Terjun", centerStyle);
        }

        /// <summary>
        /// Menggambar Panel Telemetri Penerbangan Naga di pojok kiri atas layar.
        /// </summary>
        private void DrawFlightHUD()
        {
            Rect hudRect = new Rect(20, 20, 330, 185);
            GUI.color = Color.white;
            GUI.DrawTexture(hudRect, _boxBgTexture);
            DrawOutline(hudRect, 1, new Color(0.2f, 0.8f, 1f, 0.6f));

            float speed = (flightController != null) ? flightController.CurrentSpeed : 14f;
            float altitude = (flightController != null) ? flightController.transform.position.y : 22f;
            float pitch = (flightController != null) ? flightController.CurrentPitch : -5f;
            bool isHovering = (flightController != null) && flightController.IsHovering;
            float turnInput = (poseReceiver != null) ? poseReceiver.TurnInput : 0f;

            GUIStyle titleStyle = new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold, fontSize = 13 };
            GUI.color = new Color(0f, 1f, 0.9f);
            GUI.Label(new Rect(32, 26, 300, 22), "AR DRAGON SKY GUARDIAN", titleStyle);

            GUI.color = isHovering ? Color.yellow : Color.white;
            string flightMode = isHovering ? "AUTO-HOVER (Area Desa)" : "MINECRAFT ELYTRA 3D FLIGHT";
            GUI.Label(new Rect(32, 48, 300, 20), $"Status Mode : {flightMode}");

            // Kecepatan & Ketinggian
            string speedTag = (speed > 20f) ? " [HIGH SPEED DIVE]" : ((speed > 16f) ? " [THRUST BOOST]" : "");
            GUI.color = (speed > 20f) ? new Color(1f, 0.4f, 0f) : Color.white;
            GUI.Label(new Rect(32, 68, 300, 20), $"Kecepatan  : {speed:F1} m/s{speedTag} | Alt: {altitude:F1} m");

            // Status Manuver Dinamis (Elytra Physics)
            string vertStatus;
            Color vertCol;
            if (poseReceiver != null && poseReceiver.IsTuckDive)
            {
                vertStatus = $"TUCK DIVE: TERJUN CEPAT (Pitch: {pitch:F0}°)";
                vertCol = new Color(1f, 0.35f, 0.05f);
            }
            else if (poseReceiver != null && poseReceiver.IsFlapping)
            {
                vertStatus = $"KEPAK SAYAP: SPEED UP + FLY UP (Pitch: {pitch:F0}°)";
                vertCol = new Color(0.1f, 1f, 0.4f);
            }
            else if (poseReceiver != null && poseReceiver.IsYPose)
            {
                vertStatus = $"ARAH ATAS: CLIMB SOARING ↑ (Pitch: {pitch:F0}°)";
                vertCol = new Color(0f, 1f, 0.9f);
            }
            else
            {
                vertStatus = $"POSE T: ELYTRA GLIDE (Pitch: {pitch:F0}°)";
                vertCol = new Color(1f, 0.9f, 0.2f);
            }
            GUI.color = vertCol;
            GUI.Label(new Rect(32, 88, 300, 20), $"Orientasi  : {vertStatus}");

            // Bar Kemudi Belok (-100% s/d +100%)
            string steerTxt = (Mathf.Abs(turnInput) < 0.08f) ? "Lurus (Deadzone)" : (turnInput < 0 ? $"Kiri ({Mathf.Abs(turnInput) * 100:F0}%)" : $"Kanan ({turnInput * 100:F0}%)");
            GUI.color = Color.white;
            GUI.Label(new Rect(32, 108, 300, 20), $"Kemudi     : {steerTxt}");

            Rect barBg = new Rect(32, 130, 290, 10);
            GUI.color = new Color(0.2f, 0.2f, 0.2f, 0.9f);
            GUI.DrawTexture(barBg, _barTexture);

            // Titik tengah kemudi
            GUI.color = Color.gray;
            GUI.DrawTexture(new Rect(barBg.x + barBg.width * 0.5f - 1, barBg.y - 2, 2, 14), _barTexture);

            // Pointer Kemudi
            float ptrX = barBg.x + (turnInput + 1f) * 0.5f * barBg.width;
            GUI.color = Color.cyan;
            GUI.DrawTexture(new Rect(ptrX - 4, barBg.y - 3, 8, 16), _barTexture);

            // Aksi Gestur Status
            bool flap = poseReceiver != null && poseReceiver.IsFlapping;
            bool water = poseReceiver != null && poseReceiver.IsWaterBreathing;
            bool high = poseReceiver != null && poseReceiver.IsHandsHighUp;
            bool dive = poseReceiver != null && poseReceiver.IsTuckDive;

            string gestStr = $"Aksi: {(flap ? "[KEPAK]" : "")} {(dive ? "[DIVE]" : "")} {(water ? "[SEMBUR AIR]" : "")} {(high ? "[HUJAN EMBUN]" : "")}";
            if (!flap && !dive && !water && !high) gestStr = "Aksi: Menjelajah Meluncur (Elytra)";

            GUI.color = water ? Color.cyan : (dive ? new Color(1f, 0.4f, 0f) : (flap ? Color.green : Color.yellow));
            GUI.Label(new Rect(32, 148, 300, 20), gestStr);
        }

        /// <summary>
        /// Menggambar panduan kontrol singkat di bagian bawah layar.
        /// </summary>
        private void DrawControlsQuickGuide()
        {
            float width = 740f;
            float height = 26f;
            float x = (Screen.width - width) * 0.5f;
            float y = Screen.height - height - 12f;

            Rect bgRect = new Rect(x, y, width, height);
            GUI.color = new Color(0.06f, 0.06f, 0.08f, 0.85f);
            GUI.DrawTexture(bgRect, _barTexture);
            DrawOutline(bgRect, 1, new Color(0.3f, 0.3f, 0.3f, 0.7f));

            GUI.color = new Color(0.9f, 0.9f, 0.9f, 0.95f);
            GUIStyle guideStyle = new GUIStyle(GUI.skin.label)
            {
                alignment = TextAnchor.MiddleCenter,
                fontSize = 11
            };
            GUI.Label(bgRect, "Elytra CV: Kepak Tangan=Fly Up+Speed Up | Pose T=Glide (-5°) | Pose Gambar=Tuck Dive (-45°) | Tilt=Belok || KB: Space=Flap | S=Dive | W/Y=Climb | A/D=Kemudi", guideStyle);
        }

        private void DrawOutline(Rect rect, int width, Color color)
        {
            GUI.color = color;
            GUI.DrawTexture(new Rect(rect.x, rect.y, rect.width, width), _barTexture);
            GUI.DrawTexture(new Rect(rect.x, rect.yMax - width, rect.width, width), _barTexture);
            GUI.DrawTexture(new Rect(rect.x, rect.y, width, rect.height), _barTexture);
            GUI.DrawTexture(new Rect(rect.xMax - width, rect.y, width, rect.height), _barTexture);
        }

        private void DrawLine(Vector2 p1, Vector2 p2, float width, Color color)
        {
            GUI.color = color;
            Vector2 d = p2 - p1;
            float angle = Mathf.Rad2Deg * Mathf.Atan2(d.y, d.x);
            GUIUtility.RotateAroundPivot(angle, p1);
            GUI.DrawTexture(new Rect(p1.x, p1.y - width * 0.5f, d.magnitude, width), _barTexture);
            GUIUtility.RotateAroundPivot(-angle, p1);
        }

        private void DrawCircle(Vector2 center, float radius, Color color)
        {
            GUI.color = color;
            GUI.DrawTexture(new Rect(center.x - radius, center.y - radius, radius * 2, radius * 2), _barTexture);
        }
    }
}
