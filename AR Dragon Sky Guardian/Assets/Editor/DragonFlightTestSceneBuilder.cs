using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using DragonWingAR.CV;
using DragonWingAR.Controllers;
using DragonWingAR.UI;

namespace DragonWingAR.EditorTools
{
    /// <summary>
    /// Alat Editor 1-Klik untuk membangun Scene Uji Terbang Naga 3D (Nagcu) secara otomatis.
    /// Menu: DragonWingAR -> Setup Scene Uji Terbang Naga 3D (Nagcu).
    /// </summary>
    public static class DragonFlightTestSceneBuilder
    {
        [MenuItem("DragonWingAR/Setup Scene Uji Terbang Naga 3D (Nagcu)")]
        public static void BuildDragonFlightTestScene()
        {
            // 1. Buat scene baru atau bersihkan scene aktif
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // 2. Buat Pencahayaan Dasar (Directional Light)
            GameObject lightGo = new GameObject("Directional Light");
            Light light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = new Color(1.0f, 0.96f, 0.90f);
            light.intensity = 1.2f;
            lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            // 3. Buat Ground Plane / Daratan Referensi (Ukuran 400x400 m di Y = 0)
            GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground_Reference";
            ground.transform.position = Vector3.zero;
            ground.transform.localScale = new Vector3(40f, 1f, 40f); // 400m x 400m

            // Material Daratan Hijau / Tanah
            Renderer groundRend = ground.GetComponent<Renderer>();
            if (groundRend != null)
            {
                Material groundMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                groundMat.name = "Mat_Ground_Grid";
                groundMat.color = new Color(0.22f, 0.45f, 0.25f); // Hijau alam
                groundRend.sharedMaterial = groundMat;
            }

            // 4. Buat Pilar / Grid Landmark untuk referensi visual terbang
            GameObject landmarksParent = new GameObject("Landmarks");
            Color[] pilarColors = new Color[] { Color.yellow, Color.cyan, Color.magenta, Color.red, Color.blue };
            Vector3[] pilarPositions = new Vector3[]
            {
                new Vector3(0, 7.5f, 50),
                new Vector3(60, 7.5f, 100),
                new Vector3(-60, 7.5f, 100),
                new Vector3(100, 7.5f, 0),
                new Vector3(-100, 7.5f, 0)
            };

            for (int i = 0; i < pilarPositions.Length; i++)
            {
                GameObject pilar = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                pilar.name = $"Pilar_Landmark_{i + 1}";
                pilar.transform.parent = landmarksParent.transform;
                pilar.transform.position = pilarPositions[i];
                pilar.transform.localScale = new Vector3(6f, 7.5f, 6f); // Tinggi 15m

                Renderer pRend = pilar.GetComponent<Renderer>();
                if (pRend != null)
                {
                    Material pMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                    pMat.color = pilarColors[i % pilarColors.Length];
                    pRend.sharedMaterial = pMat;
                }
            }

            // 5. Muat Model Naga (Nagcu)
            GameObject dragonPrefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Assets 3D/Nagcu.fbx");
            if (dragonPrefab == null)
            {
                dragonPrefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Assets 3D/Nagcu.blend");
            }

            // 6. Buat Root Naga Pemain (Dragon_Player)
            GameObject dragonRoot = new GameObject("Dragon_Player");
            dragonRoot.transform.position = new Vector3(0f, 15f, -80f);
            dragonRoot.transform.rotation = Quaternion.identity;

            // Rigidbody
            Rigidbody rb = dragonRoot.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;

            // Collider
            BoxCollider col = dragonRoot.AddComponent<BoxCollider>();
            col.center = new Vector3(0, 0, 0);
            col.size = new Vector3(4f, 2f, 5f);

            // Kontroler UDP Pose Receiver
            UDPPoseReceiver udpReceiver = dragonRoot.AddComponent<UDPPoseReceiver>();
            udpReceiver.port = 5052;
            udpReceiver.smoothingSpeed = 12f;
            udpReceiver.enableKeyboardFallback = true;

            // Kontroler Penerbangan (Flight Controller)
            DragonFlightController flightCtrl = dragonRoot.AddComponent<DragonFlightController>();
            flightCtrl.forwardSpeed = 12f;
            flightCtrl.fixedAltitudeY = 15f;
            flightCtrl.yawTurnSpeed = 65f;
            flightCtrl.maxRollAngle = 35f;

            // 7. Instansiasi Model Visual Naga di dalam Child (Visual_Dragon)
            GameObject visualChild;
            if (dragonPrefab != null)
            {
                visualChild = (GameObject)PrefabUtility.InstantiatePrefab(dragonPrefab, dragonRoot.transform);
                visualChild.name = "Visual_Dragon";
                visualChild.transform.localPosition = Vector3.zero;
                visualChild.transform.localRotation = Quaternion.identity;
                visualChild.transform.localScale = Vector3.one * 1.5f; // Skala naga proporsional
            }
            else
            {
                // Fallback Greybox jika aset belum terload
                visualChild = GameObject.CreatePrimitive(PrimitiveType.Cube);
                visualChild.name = "Visual_Dragon_Placeholder";
                visualChild.transform.SetParent(dragonRoot.transform, false);
                visualChild.transform.localScale = new Vector3(2f, 1f, 4f);
            }

            flightCtrl.visualModel = visualChild.transform;

            // 8. Pasang GUI & Preview Kamera PIP (Pojok Kanan Atas)
            dragonRoot.AddComponent<InGameFlightHUD>();

            // 9. Buat Main Camera (Third Person Follow)
            GameObject camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            Camera cam = camGo.AddComponent<Camera>();
            camGo.AddComponent<AudioListener>();

            // Letakkan kamera sebagai child Dragon_Player (Third-Person View)
            camGo.transform.SetParent(dragonRoot.transform, false);
            camGo.transform.localPosition = new Vector3(0f, 4f, -14f);
            camGo.transform.localRotation = Quaternion.Euler(12f, 0f, 0f);

            // 9. Simpan Scene ke Assets/_Scenes/Test_Dragon_Flight.unity
            string scenePath = "Assets/_Scenes/Test_Dragon_Flight.unity";
            EditorSceneManager.SaveScene(scene, scenePath);

            Selection.activeGameObject = dragonRoot;

            Debug.Log($"<color=#00FF88>[DragonWingAR]</color> Berhasil membuat Scene Uji Terbang Naga: {scenePath}");
            EditorUtility.DisplayDialog("Setup Scene Terbang Naga 3D Berhasil!",
                "Scene Uji Terbang Naga 3D (Nagcu) telah berhasil dibangun!\n\n" +
                "Lokasi Scene: Assets/_Scenes/Test_Dragon_Flight.unity\n\n" +
                "Cara Menguji Langsung:\n" +
                "1. Klik tombol PLAY (▶️) di Unity.\n" +
                "2. Naga akan otomatis terbang maju di ketinggian 15 meter.\n" +
                "3. Belok menggunakan Panah Kiri/Kanan (Keyboard) ATAU Webcam (active_cv_sender.py)!\n" +
                "4. Perhatikan model naga akan condong miring (roll) saat berbelok!",
                "Mulai Uji Terbang!");
        }
    }
}
