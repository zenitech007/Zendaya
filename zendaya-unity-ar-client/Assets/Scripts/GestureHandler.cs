using UnityEngine;
using Microsoft.MixedReality.Toolkit.Input;
using Microsoft.MixedReality.Toolkit.Utilities;
using TMPro;

namespace ZendayaAR
{
    public class GestureHandler : MonoBehaviour, IMixedRealityPointerHandler, IMixedRealityFocusHandler
    {
        [Header("Visual Feedback")]
        public Material highlightMaterial;
        public Material defaultMaterial;
        
        private TextMeshPro textMesh;
        private Renderer textRenderer;
        private bool isHighlighted = false;
        private string originalText;

        private void Start()
        {
            textMesh = GetComponent<TextMeshPro>();
            textRenderer = GetComponent<Renderer>();
            
            if (textMesh != null)
            {
                originalText = textMesh.text;
            }
        }

        public void OnPointerDown(MixedRealityPointerEventData eventData)
        {
            // Handle air tap gesture
            if (enableDebugLogs)
            {
                Debug.Log("[Gesture] Air tap detected on floating text");
            }
            
            OnTextSelected();
        }

        public void OnPointerUp(MixedRealityPointerEventData eventData)
        {
            // Handle pointer up if needed
        }

        public void OnPointerDragged(MixedRealityPointerEventData eventData)
        {
            // Handle drag if needed
        }

        public void OnPointerClicked(MixedRealityPointerEventData eventData)
        {
            // Handle click if needed
        }

        public void OnFocusEnter(MixedRealityFocusEventData eventData)
        {
            // User is looking at this text
            HighlightText(true);
        }

        public void OnFocusExit(MixedRealityFocusEventData eventData)
        {
            // User looked away
            HighlightText(false);
        }

        private void HighlightText(bool highlight)
        {
            isHighlighted = highlight;
            
            if (textRenderer != null)
            {
                textRenderer.material = highlight ? highlightMaterial : defaultMaterial;
            }
            
            if (textMesh != null)
            {
                // Slightly increase size when highlighted
                float scale = highlight ? 1.1f : 1.0f;
                transform.localScale = Vector3.one * scale;
                
                // Add visual indicator
                if (highlight)
                {
                    textMesh.text = $"👁️ {originalText}";
                }
                else
                {
                    textMesh.text = originalText;
                }
            }
        }

        private void OnTextSelected()
        {
            if (textMesh != null)
            {
                // Copy text to clipboard (simulated)
                string textToCopy = originalText;
                
                // In a real implementation, you'd use platform-specific clipboard APIs
                Debug.Log($"[Gesture] Copied to clipboard: {textToCopy}");
                
                // Visual feedback
                StartCoroutine(ShowCopyFeedback());
                
                // Play selection sound
                PlaySelectionSound();
            }
        }

        private System.Collections.IEnumerator ShowCopyFeedback()
        {
            if (textMesh != null)
            {
                string originalColor = textMesh.color.ToString();
                textMesh.color = Color.green;
                textMesh.text = "✅ Copied!";
                
                yield return new WaitForSeconds(1.0f);
                
                textMesh.color = Color.white;
                textMesh.text = originalText;
            }
        }

        private void PlaySelectionSound()
        {
            // Play a subtle selection sound
            AudioSource audioSource = GetComponent<AudioSource>();
            if (audioSource != null)
            {
                audioSource.Play();
            }
        }

        // Public method to set the text content
        public void SetText(string text)
        {
            originalText = text;
            if (textMesh != null)
            {
                textMesh.text = text;
            }
        }
    }
}