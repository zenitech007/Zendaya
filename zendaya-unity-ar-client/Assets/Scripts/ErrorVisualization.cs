using UnityEngine;
using TMPro;
using System.Collections;

namespace ZendayaAR
{
    public class ErrorVisualization : MonoBehaviour
    {
        [Header("Error Effects")]
        public ParticleSystem shatterEffect;
        public AudioClip errorSound;
        public AudioClip dissolveSound;
        
        [Header("Animation Settings")]
        public float shatterDuration = 2.0f;
        public float dissolveDuration = 1.5f;
        public AnimationCurve shatterCurve = AnimationCurve.EaseInOut(0, 0, 1, 1);
        public AnimationCurve dissolveCurve = AnimationCurve.EaseInOut(0, 1, 1, 0);

        private TextMeshPro textMesh;
        private AudioSource audioSource;
        private Material originalMaterial;
        private Material errorMaterial;

        private void Start()
        {
            textMesh = GetComponent<TextMeshPro>();
            audioSource = GetComponent<AudioSource>();
            
            if (textMesh != null)
            {
                originalMaterial = textMesh.material;
                CreateErrorMaterial();
            }
        }

        private void CreateErrorMaterial()
        {
            // Create a material with dissolve shader properties
            errorMaterial = new Material(originalMaterial);
            errorMaterial.color = Color.red;
        }

        public void ShowError(string errorMessage, ErrorType errorType = ErrorType.General)
        {
            if (textMesh != null)
            {
                textMesh.text = errorMessage;
                textMesh.material = errorMaterial;
            }

            switch (errorType)
            {
                case ErrorType.Critical:
                    StartCoroutine(ShatterEffect());
                    break;
                case ErrorType.Network:
                    StartCoroutine(DissolveEffect());
                    break;
                case ErrorType.Timeout:
                    StartCoroutine(FadeOutEffect());
                    break;
                default:
                    StartCoroutine(GlitchEffect());
                    break;
            }
        }

        private IEnumerator ShatterEffect()
        {
            // Play shatter sound
            if (audioSource != null && errorSound != null)
            {
                audioSource.PlayOneShot(errorSound);
            }

            // Activate particle effect
            if (shatterEffect != null)
            {
                shatterEffect.Play();
            }

            // Shatter animation
            Vector3 originalScale = transform.localScale;
            Vector3 originalPosition = transform.position;
            
            float elapsed = 0f;
            while (elapsed < shatterDuration)
            {
                elapsed += Time.deltaTime;
                float progress = elapsed / shatterDuration;
                float curveValue = shatterCurve.Evaluate(progress);
                
                // Scale down and fragment
                transform.localScale = Vector3.Lerp(originalScale, Vector3.zero, curveValue);
                
                // Add random jitter
                Vector3 jitter = Random.insideUnitSphere * 0.1f * curveValue;
                transform.position = originalPosition + jitter;
                
                // Fade out
                if (textMesh != null)
                {
                    Color color = textMesh.color;
                    color.a = 1f - curveValue;
                    textMesh.color = color;
                }
                
                yield return null;
            }
            
            // Destroy after effect
            Destroy(gameObject);
        }

        private IEnumerator DissolveEffect()
        {
            // Play dissolve sound
            if (audioSource != null && dissolveSound != null)
            {
                audioSource.PlayOneShot(dissolveSound);
            }

            float elapsed = 0f;
            while (elapsed < dissolveDuration)
            {
                elapsed += Time.deltaTime;
                float progress = elapsed / dissolveDuration;
                float curveValue = dissolveCurve.Evaluate(progress);
                
                if (textMesh != null)
                {
                    Color color = textMesh.color;
                    color.a = curveValue;
                    textMesh.color = color;
                    
                    // Add dissolve effect by modifying vertices
                    ApplyDissolveEffect(progress);
                }
                
                yield return null;
            }
            
            Destroy(gameObject);
        }

        private IEnumerator FadeOutEffect()
        {
            float elapsed = 0f;
            Color originalColor = textMesh.color;
            
            while (elapsed < 1.0f)
            {
                elapsed += Time.deltaTime;
                float alpha = Mathf.Lerp(1f, 0f, elapsed);
                
                if (textMesh != null)
                {
                    Color color = originalColor;
                    color.a = alpha;
                    textMesh.color = color;
                }
                
                yield return null;
            }
            
            Destroy(gameObject);
        }

        private IEnumerator GlitchEffect()
        {
            string originalText = textMesh.text;
            string glitchChars = "!@#$%^&*()_+-=[]{}|;:,.<>?";
            
            for (int i = 0; i < 10; i++)
            {
                // Create glitched text
                string glitchedText = "";
                foreach (char c in originalText)
                {
                    if (Random.value < 0.3f)
                    {
                        glitchedText += glitchChars[Random.Range(0, glitchChars.Length)];
                    }
                    else
                    {
                        glitchedText += c;
                    }
                }
                
                textMesh.text = glitchedText;
                
                // Random color flicker
                textMesh.color = Random.value < 0.5f ? Color.red : Color.yellow;
                
                yield return new WaitForSeconds(0.1f);
            }
            
            // Restore original text and fade out
            textMesh.text = originalText;
            textMesh.color = Color.red;
            
            yield return StartCoroutine(FadeOutEffect());
        }

        private void ApplyDissolveEffect(float progress)
        {
            // This would require a custom shader for proper dissolve effect
            // For now, we'll simulate it with vertex manipulation
            if (textMesh != null)
            {
                textMesh.ForceMeshUpdate();
                var mesh = textMesh.mesh;
                var vertices = mesh.vertices;
                
                for (int i = 0; i < vertices.Length; i++)
                {
                    if (Random.value < progress)
                    {
                        vertices[i] += Random.insideUnitSphere * 0.01f;
                    }
                }
                
                mesh.vertices = vertices;
                textMesh.canvasRenderer.SetMesh(mesh);
            }
        }

        public enum ErrorType
        {
            General,
            Critical,
            Network,
            Timeout,
            Authentication
        }
    }
}