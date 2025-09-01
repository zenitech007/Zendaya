using UnityEngine;
using TMPro;

namespace ZendayaAR
{
    public class FloatingTextPrefab : MonoBehaviour
    {
        [Header("Animation Settings")]
        public float floatSpeed = 0.5f;
        public float rotationSpeed = 10f;
        public AnimationCurve scaleCurve = AnimationCurve.EaseInOut(0, 0, 1, 1);
        
        private TextMeshPro textMesh;
        private Vector3 initialPosition;
        private float startTime;

        private void Start()
        {
            textMesh = GetComponent<TextMeshPro>();
            initialPosition = transform.position;
            startTime = Time.time;
            
            // Initial scale animation
            transform.localScale = Vector3.zero;
            StartCoroutine(ScaleInAnimation());
        }

        private void Update()
        {
            // Gentle floating motion
            float elapsed = Time.time - startTime;
            float yOffset = Mathf.Sin(elapsed * floatSpeed) * 0.05f;
            transform.position = initialPosition + Vector3.up * yOffset;
            
            // Subtle rotation to keep it dynamic
            transform.Rotate(Vector3.up, rotationSpeed * Time.deltaTime);
            
            // Always face the camera
            Vector3 directionToCamera = Camera.main.transform.position - transform.position;
            directionToCamera.y = 0; // Keep it level
            if (directionToCamera != Vector3.zero)
            {
                Quaternion targetRotation = Quaternion.LookRotation(-directionToCamera);
                transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.deltaTime * 2f);
            }
        }

        private System.Collections.IEnumerator ScaleInAnimation()
        {
            float duration = 0.5f;
            float elapsed = 0f;
            
            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                float progress = elapsed / duration;
                float scale = scaleCurve.Evaluate(progress);
                transform.localScale = Vector3.one * scale;
                yield return null;
            }
            
            transform.localScale = Vector3.one;
        }

        public void SetText(string text, Color color)
        {
            if (textMesh != null)
            {
                textMesh.text = text;
                textMesh.color = color;
            }
        }

        public void SetLifetime(float lifetime)
        {
            Destroy(gameObject, lifetime);
        }
    }
}