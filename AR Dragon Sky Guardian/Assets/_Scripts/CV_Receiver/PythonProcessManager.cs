using System;
using System.Diagnostics;
using System.IO;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace DragonWingAR.CV
{
    /// <summary>
    /// Pengelola Otomatis Proses Python Computer Vision (YOLOv8n-pose).
    /// Memastikan active_cv_sender.py berjalan otomatis saat Unity dimainkan (Play Mode / Standalone),
    /// dan dihentikan secara bersih saat Unity berhenti atau keluar.
    /// </summary>
    [DisallowMultipleComponent]
    public class PythonProcessManager : MonoBehaviour
    {
        [Header("Pengaturan Peluncuran Otomatis")]
        [Tooltip("Jalankan modul Python CV otomatis saat game mulai")]
        public bool autoLaunchPython = true;

        [Tooltip("Jalankan Python tanpa jendela GUI OpenCV eksternal (stream video tetap tampil di HUD Unity PIP)")]
        public bool runHeadless = false;

        [Tooltip("Sembunyikan jendela console prompt CMD hitam saat meluncurkan Python")]
        public bool hideConsoleWindow = true;

        [Header("Koneksi Socket")]
        public string targetIp = "127.0.0.1";
        public int posePort = 5052;
        public int videoPort = 5053;

        [Header("Override Path Kustom (Opsional)")]
        [Tooltip("Kosongkan untuk deteksi otomatis (venv/Scripts/python.exe)")]
        public string customPythonExecutable = "";

        [Tooltip("Kosongkan untuk deteksi otomatis (ARDragonSkyGuardian_CV/active_cv_sender.py)")]
        public string customScriptPath = "";

        [Header("Status Proses (Read Only)")]
        [SerializeField] private bool _isProcessRunning = false;
        [SerializeField] private int _processId = 0;
        [SerializeField] private string _resolvedPythonPath = "";
        [SerializeField] private string _resolvedScriptPath = "";

        private Process _pythonProcess = null;
        private static PythonProcessManager _instance;

        public static PythonProcessManager Instance => _instance;
        public bool IsProcessRunning => _isProcessRunning && _pythonProcess != null && !_pythonProcess.HasExited;
        public int ProcessId => _processId;

        private void Awake()
        {
            if (_instance != null && _instance != this)
            {
                Destroy(this);
                return;
            }
            _instance = this;

#if UNITY_EDITOR
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
#endif

            if (autoLaunchPython)
            {
                LaunchPython();
            }
        }

#if UNITY_EDITOR
        private void OnPlayModeStateChanged(PlayModeStateChange state)
        {
            if (state == PlayModeStateChange.ExitingPlayMode)
            {
                StopPython();
            }
        }
#endif

        private void OnEnable()
        {
            if (autoLaunchPython && !IsProcessRunning)
            {
                LaunchPython();
            }
        }

        private void OnDisable()
        {
            StopPython();
        }

        private void OnDestroy()
        {
#if UNITY_EDITOR
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
#endif
            StopPython();
        }

        private void OnApplicationQuit()
        {
            StopPython();
        }

        /// <summary>
        /// Meluncurkan proses Python active_cv_sender.py secara otomatis.
        /// </summary>
        public void LaunchPython()
        {
            if (IsProcessRunning)
            {
                UnityEngine.Debug.Log($"<color=#00FF88>[PythonProcessManager]</color> Python CV sudah berjalan (PID: {_processId}).");
                return;
            }

            ResolvePaths();

            if (string.IsNullOrEmpty(_resolvedPythonPath) || !File.Exists(_resolvedPythonPath))
            {
                UnityEngine.Debug.LogWarning($"<color=#FF8800>[PythonProcessManager]</color> Python executable tidak ditemukan di: {_resolvedPythonPath}. Menggunakan fallback keyboard.");
                return;
            }

            if (string.IsNullOrEmpty(_resolvedScriptPath) || !File.Exists(_resolvedScriptPath))
            {
                UnityEngine.Debug.LogWarning($"<color=#FF8800>[PythonProcessManager]</color> Script Python tidak ditemukan di: {_resolvedScriptPath}. Menggunakan fallback keyboard.");
                return;
            }

            try
            {
                string args = $"\"{_resolvedScriptPath}\" --ip {targetIp} --port {posePort} --video-port {videoPort}";
                if (runHeadless)
                {
                    args += " --headless";
                }

                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = _resolvedPythonPath,
                    Arguments = args,
                    WorkingDirectory = Path.GetDirectoryName(_resolvedScriptPath),
                    UseShellExecute = false,
                    CreateNoWindow = hideConsoleWindow
                };

                _pythonProcess = new Process { StartInfo = psi };
                _pythonProcess.EnableRaisingEvents = true;
                _pythonProcess.Exited += (s, e) =>
                {
                    _isProcessRunning = false;
                    _processId = 0;
                    UnityEngine.Debug.Log("<color=#FF8800>[PythonProcessManager]</color> Proses Python telah berhenti.");
                };

                bool started = _pythonProcess.Start();
                if (started)
                {
                    _processId = _pythonProcess.Id;
                    _isProcessRunning = true;
                    UnityEngine.Debug.Log($"<color=#00FF88>[PythonProcessManager]</color> Sukses meluncurkan Python active_cv_sender (PID: {_processId}) | Pose Port: {posePort}, Video: {videoPort}");
                }
                else
                {
                    _isProcessRunning = false;
                    _processId = 0;
                    UnityEngine.Debug.LogError("<color=#FF0000>[PythonProcessManager]</color> Gagal memulai proses Python.");
                }
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogError($"<color=#FF0000>[PythonProcessManager]</color> Galat saat meluncurkan Python: {ex.Message}");
                _isProcessRunning = false;
                _processId = 0;
            }
        }

        /// <summary>
        /// Menghentikan proses Python beserta seluruh child process tree-nya secara bersih.
        /// </summary>
        public void StopPython()
        {
            if (_pythonProcess != null)
            {
                try
                {
                    if (!_pythonProcess.HasExited)
                    {
                        int pid = _pythonProcess.Id;
                        UnityEngine.Debug.Log($"<color=#00FFFF>[PythonProcessManager]</color> Menghentikan proses Python (PID: {pid})...");

                        try
                        {
                            _pythonProcess.Kill();
                        }
                        catch { }

                        if (Application.platform == RuntimePlatform.WindowsEditor || Application.platform == RuntimePlatform.WindowsPlayer)
                        {
                            try
                            {
                                Process.Start(new ProcessStartInfo
                                {
                                    FileName = "taskkill",
                                    Arguments = $"/PID {pid} /F /T",
                                    CreateNoWindow = true,
                                    UseShellExecute = false
                                })?.WaitForExit(1000);
                            }
                            catch { }
                        }
                    }
                }
                catch (Exception ex)
                {
                    UnityEngine.Debug.LogWarning($"[PythonProcessManager] Info saat menutup proses: {ex.Message}");
                }
                finally
                {
                    _pythonProcess.Dispose();
                    _pythonProcess = null;
                    _isProcessRunning = false;
                    _processId = 0;
                }
            }
        }

        /// <summary>
        /// Mencari lokasi file Python executable dan script active_cv_sender.py secara dinamis.
        /// </summary>
        private void ResolvePaths()
        {
            if (!string.IsNullOrEmpty(customPythonExecutable) && File.Exists(customPythonExecutable))
            {
                _resolvedPythonPath = customPythonExecutable;
            }
            else
            {
                _resolvedPythonPath = FindPythonExecutable();
            }

            if (!string.IsNullOrEmpty(customScriptPath) && File.Exists(customScriptPath))
            {
                _resolvedScriptPath = customScriptPath;
            }
            else
            {
                _resolvedScriptPath = FindScriptPath();
            }
        }

        private string FindPythonExecutable()
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string workspaceRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));

            string[] candidates = new string[]
            {
                Path.Combine(workspaceRoot, "ARDragonSkyGuardian_CV", "venv", "Scripts", "python.exe"),
                Path.Combine(projectRoot, "ARDragonSkyGuardian_CV", "venv", "Scripts", "python.exe"),
                Path.Combine(workspaceRoot, "venv", "Scripts", "python.exe"),
                Path.Combine(projectRoot, "venv", "Scripts", "python.exe")
            };

            foreach (string candidate in candidates)
            {
                if (File.Exists(candidate))
                {
                    return Path.GetFullPath(candidate);
                }
            }

            return "python.exe";
        }

        private string FindScriptPath()
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string workspaceRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "../.."));

            string[] candidates = new string[]
            {
                Path.Combine(workspaceRoot, "ARDragonSkyGuardian_CV", "active_cv_sender.py"),
                Path.Combine(projectRoot, "ARDragonSkyGuardian_CV", "active_cv_sender.py"),
                Path.Combine(workspaceRoot, "active_cv_sender.py")
            };

            foreach (string candidate in candidates)
            {
                if (File.Exists(candidate))
                {
                    return Path.GetFullPath(candidate);
                }
            }

            return "";
        }
    }
}
