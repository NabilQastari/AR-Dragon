using UnityEditor;
using UnityEngine;
using DragonWingAR.CV;

namespace DragonWingAR.EditorTools
{
    /// <summary>
    /// Pembantu Editor untuk memasang objek pengujian UDPPoseReceiver secara instan di scene aktif.
    /// Diakses melalui Menu Unity: DragonWingAR -> Setup Scene Uji UDP Receiver.
    /// </summary>
    public static class QuickUDPTestBuilder
    {
        [MenuItem("DragonWingAR/Setup Scene Uji UDP Receiver")]
        public static void SetupUDPTestInScene()
        {
            UDPPoseReceiver existing = Object.FindObjectOfType<UDPPoseReceiver>();
            if (existing != null)
            {
                Selection.activeGameObject = existing.gameObject;
                Debug.Log("<color=#00FF88>[DragonWingAR]</color> UDPPoseReceiver sudah ada di scene pada objek: " + existing.gameObject.name);
                EditorUtility.DisplayDialog("Setup UDP Receiver", 
                    $"Komponen UDPPoseReceiver sudah terpasang pada objek '{existing.gameObject.name}'.\n\nSilakan langsung tekan tombol PLAY di Unity untuk mulai menguji!", "OK");
                return;
            }

            GameObject go = new GameObject("[UDP_Pose_Test_Manager]");
            UDPPoseReceiver receiver = go.AddComponent<UDPPoseReceiver>();
            Undo.RegisterCreatedObjectUndo(go, "Create UDP Pose Receiver");
            Selection.activeGameObject = go;

            Debug.Log("<color=#00FF88>[DragonWingAR]</color> Berhasil membuat objek [UDP_Pose_Test_Manager] dengan komponen UDPPoseReceiver.");
            EditorUtility.DisplayDialog("Setup UDP Receiver Berhasil!", 
                "Objek [UDP_Pose_Test_Manager] telah otomatis dipasang ke Scene!\n\n" +
                "Langkah Pengujian:\n" +
                "1. Tekan tombol PLAY di Unity.\n" +
                "2. Coba kontrol Keyboard Fallback: Panah Kiri/Kanan (Belok), Tombol 1 (Kepak), 2 (Sembur Air), 3 (Hujan Embun).\n" +
                "3. Jalankan 'active_cv_sender.py' di terminal untuk menguji langsung dengan webcam!", "Siap Uji!");
        }
    }
}
