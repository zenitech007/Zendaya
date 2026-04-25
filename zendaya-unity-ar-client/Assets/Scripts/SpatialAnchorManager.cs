using System.Collections.Generic;
using UnityEngine;
using Microsoft.MixedReality.Toolkit.Utilities;

namespace ZendayaAR
{
    [System.Serializable]
    public class AnchoredResponse
    {
        public string id;
        public string text;
        public Vector3 position;
        public Quaternion rotation;
        public string timestamp;
    }

    public class SpatialAnchorManager : MonoBehaviour
    {
        [Header("Anchor Settings")]
        public GameObject anchoredTextPrefab;
        public float maxAnchorDistance = 5.0f;
        public int maxAnchors = 10;

        [Header("Visual Indicators")]
        public GameObject anchorIndicatorPrefab;
        public Material anchorMaterial;

        private Dictionary<string, GameObject> anchoredObjects = new Dictionary<string, GameObject>();
        private List<AnchoredResponse> savedAnchors = new List<AnchoredResponse>();
        private const string ANCHOR_SAVE_KEY = "ZendayaAnchors";

        private void Start()
        {
            LoadAnchors();
            RestoreAnchoredObjects();
        }

        public void CreateAnchor(string responseText, Vector3 worldPosition)
        {
            // Check if we're within anchor distance limits
            if (Vector3.Distance(worldPosition, Camera.main.transform.position) > maxAnchorDistance)
            {
                Debug.LogWarning("[Spatial Anchor] Position too far for anchoring");
                return;
            }

            // Check anchor limit
            if (anchoredObjects.Count >= maxAnchors)
            {
                RemoveOldestAnchor();
            }

            // Create unique ID
            string anchorId = System.Guid.NewGuid().ToString();

            // Create anchored object
            GameObject anchoredObject = CreateAnchoredObject(responseText, worldPosition, Quaternion.identity);
            anchoredObjects[anchorId] = anchoredObject;

            // Save anchor data
            AnchoredResponse anchorData = new AnchoredResponse
            {
                id = anchorId,
                text = responseText,
                position = worldPosition,
                rotation = Quaternion.identity,
                timestamp = System.DateTime.Now.ToString()
            };
            savedAnchors.Add(anchorData);

            // Persist to storage
            SaveAnchors();

            Debug.Log($"[Spatial Anchor] Created anchor at {worldPosition}");
        }

        public void CreateAnchorAtGaze(string responseText)
        {
            // Use eye tracking or head gaze to determine position
            Vector3 gazePosition = GetGazePosition();
            CreateAnchor(responseText, gazePosition);
        }

        private Vector3 GetGazePosition()
        {
            // Use MRTK's gaze provider
            var gazeProvider = CoreServices.InputSystem?.GazeProvider;
            if (gazeProvider != null)
            {
                if (gazeProvider.HitInfo.raycastValid)
                {
                    return gazeProvider.HitInfo.point;
                }
            }

            // Fallback: position in front of user
            Vector3 userPosition = Camera.main.transform.position;
            Vector3 userForward = Camera.main.transform.forward;
            return userPosition + userForward * 2.0f;
        }

        private GameObject CreateAnchoredObject(string text, Vector3 position, Quaternion rotation)
        {
            GameObject anchoredObj = Instantiate(anchoredTextPrefab, position, rotation);
            
            // Configure text
            var textMesh = anchoredObj.GetComponent<TMPro.TextMeshPro>();
            if (textMesh != null)
            {
                textMesh.text = text;
                textMesh.color = Color.cyan;
                textMesh.fontSize = 0.08f;
            }

            // Add gesture handler
            var gestureHandler = anchoredObj.GetComponent<GestureHandler>();
            if (gestureHandler != null)
            {
                gestureHandler.SetText(text);
            }

            // Add visual anchor indicator
            CreateAnchorIndicator(position);

            // Add persistent behavior
            var persistentAnchor = anchoredObj.AddComponent<PersistentAnchor>();
            persistentAnchor.Initialize(text, position, rotation);

            return anchoredObj;
        }

        private void CreateAnchorIndicator(Vector3 position)
        {
            if (anchorIndicatorPrefab != null)
            {
                GameObject indicator = Instantiate(anchorIndicatorPrefab, position, Quaternion.identity);
                
                // Make it subtle and small
                indicator.transform.localScale = Vector3.one * 0.1f;
                
                // Add gentle pulsing animation
                StartCoroutine(PulseIndicator(indicator));
            }
        }

        private System.Collections.IEnumerator PulseIndicator(GameObject indicator)
        {
            Vector3 originalScale = indicator.transform.localScale;
            
            while (indicator != null)
            {
                // Pulse animation
                for (float t = 0; t < 1; t += Time.deltaTime)
                {
                    float scale = Mathf.Lerp(1.0f, 1.2f, Mathf.Sin(t * Mathf.PI));
                    indicator.transform.localScale = originalScale * scale;
                    yield return null;
                }
            }
        }

        private void RemoveOldestAnchor()
        {
            if (savedAnchors.Count > 0)
            {
                var oldestAnchor = savedAnchors[0];
                RemoveAnchor(oldestAnchor.id);
            }
        }

        public void RemoveAnchor(string anchorId)
        {
            if (anchoredObjects.ContainsKey(anchorId))
            {
                Destroy(anchoredObjects[anchorId]);
                anchoredObjects.Remove(anchorId);
            }

            savedAnchors.RemoveAll(a => a.id == anchorId);
            SaveAnchors();
        }

        public void ClearAllAnchors()
        {
            foreach (var obj in anchoredObjects.Values)
            {
                if (obj != null)
                {
                    Destroy(obj);
                }
            }
            
            anchoredObjects.Clear();
            savedAnchors.Clear();
            SaveAnchors();
        }

        private void SaveAnchors()
        {
            string json = JsonUtility.ToJson(new SerializableList<AnchoredResponse>(savedAnchors));
            PlayerPrefs.SetString(ANCHOR_SAVE_KEY, json);
            PlayerPrefs.Save();
        }

        private void LoadAnchors()
        {
            string json = PlayerPrefs.GetString(ANCHOR_SAVE_KEY, "");
            if (!string.IsNullOrEmpty(json))
            {
                var loadedData = JsonUtility.FromJson<SerializableList<AnchoredResponse>>(json);
                savedAnchors = loadedData.items;
            }
        }

        private void RestoreAnchoredObjects()
        {
            foreach (var anchor in savedAnchors)
            {
                GameObject restoredObj = CreateAnchoredObject(anchor.text, anchor.position, anchor.rotation);
                anchoredObjects[anchor.id] = restoredObj;
            }
        }

        // Helper class for JSON serialization
        [System.Serializable]
        private class SerializableList<T>
        {
            public List<T> items;
            
            public SerializableList(List<T> items)
            {
                this.items = items;
            }
        }
    }

    // Component for individual anchored objects
    public class PersistentAnchor : MonoBehaviour
    {
        private string anchorText;
        private Vector3 anchorPosition;
        private Quaternion anchorRotation;

        public void Initialize(string text, Vector3 position, Quaternion rotation)
        {
            anchorText = text;
            anchorPosition = position;
            anchorRotation = rotation;
        }

        private void Update()
        {
            // Ensure the anchor stays in its designated position
            if (Vector3.Distance(transform.position, anchorPosition) > 0.1f)
            {
                transform.position = Vector3.Lerp(transform.position, anchorPosition, Time.deltaTime * 2f);
            }
        }
    }
}