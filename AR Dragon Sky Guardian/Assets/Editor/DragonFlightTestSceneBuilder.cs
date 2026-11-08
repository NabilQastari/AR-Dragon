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

            // 3. Muat Model Pulau 3D Utama (pulau.fbx / pulau.blend)
            GameObject islandPrefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Assets 3D/pulau.fbx");
            if (islandPrefab == null)
            {
                islandPrefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Assets 3D/pulau.blend");
            }

            if (islandPrefab != null)
            {
                GameObject islandGo = (GameObject)PrefabUtility.InstantiatePrefab(islandPrefab);
                islandGo.name = "World_Island";
                islandGo.transform.position = Vector3.zero;
                islandGo.transform.rotation = Quaternion.identity;
                islandGo.transform.localScale = Vector3.one;

                // Pasang MeshCollider pada Terrain & Bebatuan Pulau
                Transform terrainT = islandGo.transform.Find("Island_Terrain");
                if (terrainT != null && !terrainT.GetComponent<Collider>())
                {
                    terrainT.gameObject.AddComponent<MeshCollider>();
                }
                Transform rocksT = islandGo.transform.Find("Island_Rocks");
                if (rocksT != null && !rocksT.GetComponent<Collider>())
                {
                    rocksT.gameObject.AddComponent<MeshCollider>();
                }

                Debug.Log("<color=#00FF88>[DragonWingAR]</color> Model Pulau 3D (pulau.fbx) berhasil dipasang ke dalam Scene!");
            }
            else
            {
                // Fallback jika file pulau belum ada
                GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
                ground.name = "Ground_Reference";
                ground.transform.position = Vector3.zero;
                ground.transform.localScale = new Vector3(80f, 1f, 80f);
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

                // Nonaktifkan bidang referensi 2D sketch dari Blender (Plane, Plane.001, Plane.002, dll)
                foreach (Transform t in visualChild.GetComponentsInChildren<Transform>(true))
                {
                    if (t.name.StartsWith("Plane"))
                    {
                        t.gameObject.SetActive(false);
                    }
                }

                // Hitung titik pusat bound naga agar tepat berada di tengah Dragon_Player
                Renderer[] renderers = visualChild.GetComponentsInChildren<Renderer>(true);
                if (renderers.Length > 0)
                {
                    Bounds b = new Bounds(visualChild.transform.position, Vector3.zero);
                    bool first = true;
                    foreach (var r in renderers)
                    {
                        if (r.gameObject.activeInHierarchy)
                        {
                            if (first) { b = r.bounds; first = false; }
                            else b.Encapsulate(r.bounds);
                        }
                    }
                    Vector3 diff = b.center - dragonRoot.transform.position;
                    visualChild.transform.position -= diff;
                }
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

            // 9. Buat Main Camera (Third Person Follow yang lapang)
            GameObject camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            Camera cam = camGo.AddComponent<Camera>();
            camGo.AddComponent<AudioListener>();

            // Letakkan kamera sebagai child Dragon_Player (Third-Person View)
            camGo.transform.SetParent(dragonRoot.transform, false);
            camGo.transform.localPosition = new Vector3(0f, 10f, -28f);
            camGo.transform.localRotation = Quaternion.Euler(15f, 0f, 0f);

            // 9. Simpan Scene ke Assets/_Scenes/Test_Dragon_Flight.unity
            string scenePath = "Assets/_Scenes/Test_Dragon_Flight.unity";
            EditorSceneManager.SaveScene(scene, scenePath);

            Selection.activeGameObject = dragonRoot;

            Debug.Log($"<color=#00FF88>[DragonWingAR]</color> Berhasil membuat dan menyimpan Scene Uji Terbang Naga: {scenePath}");
        }

        [MenuItem("DragonWingAR/Inject Naga & HUD ke Scene Aktif Ini")]
        public static void InjectDragonToActiveScene()
        {
            // Pasang Pulau 3D jika belum ada
            if (GameObject.Find("World_Island") == null)
            {
                GameObject islandPrefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Assets 3D/pulau.fbx") ??
                                          AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Assets 3D/pulau.blend");
                if (islandPrefab != null)
                {
                    GameObject islandGo = (GameObject)PrefabUtility.InstantiatePrefab(islandPrefab);
                    islandGo.name = "World_Island";
                    islandGo.transform.position = Vector3.zero;
                    islandGo.transform.rotation = Quaternion.identity;

                    Transform terrainT = islandGo.transform.Find("Island_Terrain");
                    if (terrainT != null && !terrainT.GetComponent<Collider>()) terrainT.gameObject.AddComponent<MeshCollider>();
                    Transform rocksT = islandGo.transform.Find("Island_Rocks");
                    if (rocksT != null && !rocksT.GetComponent<Collider>()) rocksT.gameObject.AddComponent<MeshCollider>();
                }
            }

            GameObject existing = GameObject.Find("Dragon_Player");
            if (existing != null)
            {
                Selection.activeGameObject = existing;
                Debug.Log("<color=#00FF88>[DragonWingAR]</color> Dragon_Player & World_Island sudah siap di scene aktif.");
                return;
            }

            // Muat Model Naga (Nagcu)
            GameObject dragonPrefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Assets 3D/Nagcu.fbx");
            if (dragonPrefab == null)
            {
                dragonPrefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Assets 3D/Nagcu.blend");
            }

            GameObject dragonRoot = new GameObject("Dragon_Player");
            dragonRoot.transform.position = new Vector3(0f, 15f, 0f);

            Rigidbody rb = dragonRoot.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;

            BoxCollider col = dragonRoot.AddComponent<BoxCollider>();
            col.center = Vector3.zero;
            col.size = new Vector3(4f, 2f, 5f);

            UDPPoseReceiver udpReceiver = dragonRoot.AddComponent<UDPPoseReceiver>();
            udpReceiver.port = 5052;
            udpReceiver.smoothingSpeed = 12f;
            udpReceiver.enableKeyboardFallback = true;

            DragonFlightController flightCtrl = dragonRoot.AddComponent<DragonFlightController>();
            flightCtrl.forwardSpeed = 12f;
            flightCtrl.fixedAltitudeY = 15f;
            flightCtrl.yawTurnSpeed = 65f;
            flightCtrl.maxRollAngle = 35f;

            GameObject visualChild;
            if (dragonPrefab != null)
            {
                visualChild = (GameObject)PrefabUtility.InstantiatePrefab(dragonPrefab, dragonRoot.transform);
                visualChild.name = "Visual_Dragon";
                visualChild.transform.localPosition = Vector3.zero;
                visualChild.transform.localRotation = Quaternion.identity;
                visualChild.transform.localScale = Vector3.one * 1.5f;

                foreach (Transform t in visualChild.GetComponentsInChildren<Transform>(true))
                {
                    if (t.name.StartsWith("Plane")) t.gameObject.SetActive(false);
                }

                Renderer[] renderers = visualChild.GetComponentsInChildren<Renderer>(true);
                if (renderers.Length > 0)
                {
                    Bounds b = new Bounds(visualChild.transform.position, Vector3.zero);
                    bool first = true;
                    foreach (var r in renderers)
                    {
                        if (r.gameObject.activeInHierarchy)
                        {
                            if (first) { b = r.bounds; first = false; }
                            else b.Encapsulate(r.bounds);
                        }
                    }
                    Vector3 diff = b.center - dragonRoot.transform.position;
                    visualChild.transform.position -= diff;
                }
            }
            else
            {
                visualChild = GameObject.CreatePrimitive(PrimitiveType.Cube);
                visualChild.name = "Visual_Dragon_Placeholder";
                visualChild.transform.SetParent(dragonRoot.transform, false);
            }

            flightCtrl.visualModel = visualChild.transform;
            dragonRoot.AddComponent<InGameFlightHUD>();

            // Hubungkan atau buat Main Camera
            Camera mainCam = Camera.main;
            if (mainCam != null)
            {
                mainCam.transform.SetParent(dragonRoot.transform, false);
                mainCam.transform.localPosition = new Vector3(0f, 10f, -28f);
                mainCam.transform.localRotation = Quaternion.Euler(15f, 0f, 0f);
            }

            Selection.activeGameObject = dragonRoot;
            EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
            Debug.Log("<color=#00FF88>[DragonWingAR]</color> Berhasil meng-inject Dragon_Player & Flight HUD ke Scene aktif!");
        }
    }
}
