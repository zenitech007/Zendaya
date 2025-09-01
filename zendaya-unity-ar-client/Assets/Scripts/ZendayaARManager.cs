using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Microsoft.MixedReality.Toolkit.UI;
using Microsoft.MixedReality.Toolkit.Input;
using TMPro;

namespace ZendayaAR
{
    public class ZendayaARManager : MonoBehaviour, IMixedRealitySpeechHandler
    {
        [Header("UI References")]
        public GameObject responseTextPrefab;
        public Transform responseContainer;
        public TextMeshPro statusText;
        public PressableButton sendButton;

        [Header("Configuration")]
        public float responseDistance = 2.0f;
        public float responseLifetime = 10.0f;
        public int maxActiveResponses = 5;

        private APIManager apiManager;
        private Queue<GameObject> activeResponses = new Queue<GameObject>();
        private bool isProcessing = false;

        private void Start()
        {
            // Get API Manager
            apiManager = FindObjectOfType<APIManager>();
            if (apiManager == null)
            {
                Debug.LogError("[Zendaya AR] APIManager not found!");
                return;
            }

            // Setup UI
            if (sendButton != null)
            {
                sendButton.ButtonPressed.AddListener(OnSendButtonPressed);
            }

            // Register for speech input
            CoreServices.InputSystem?.RegisterHandler<IMixedRealitySpeechHandler>(this);

            UpdateStatus("Zendaya AR System Online");
            
            // Send welcome message
            ProcessUserInput("Hello Zendaya, I'm using the AR interface");
        }

        private void OnDestroy()
        {
            // Unregister speech handler
            CoreServices.InputSystem?.UnregisterHandler<IMixedRealitySpeechHandler>(this);
        }

        public void OnSpeechKeywordRecognized(SpeechEventData eventData)
        {
            string command = eventData.Command.Keyword;
            
            if (command.ToLower().Contains("zendaya"))
            {
                // Extract the actual command after "Zendaya"
                string[] parts = command.Split(new string[] { "zendaya" }, StringSplitOptions.IgnoreCase);
                if (parts.Length > 1)
                {
                    string actualCommand = parts[1].Trim();
                    if (!string.IsNullOrEmpty(actualCommand))
                    {
                        ProcessUserInput(actualCommand);
                    }
                }
            }
        }

        private void OnSendButtonPressed()
        {
            // For demo purposes, send a predefined message
            ProcessUserInput("What can you help me with?");
        }

        public void ProcessUserInput(string input)
        {
            if (isProcessing || string.IsNullOrEmpty(input))
                return;

            isProcessing = true;
            UpdateStatus("Processing...");

            apiManager.SendMessage(
                input,
                OnResponseReceived,
                OnError
            );
        }

        private void OnResponseReceived(ChatResponse response)
        {
            isProcessing = false;
            UpdateStatus("Ready");

            // Create 3D floating text response
            CreateFloatingResponse(response.text);
        }

        private void OnError(string error)
        {
            isProcessing = false;
            UpdateStatus($"Error: {error}");
            
            // Show error as floating text
            CreateFloatingResponse($"System Error: {error}", true);
        }

        private void CreateFloatingResponse(string text, bool isError = false)
        {
            if (responseTextPrefab == null || responseContainer == null)
            {
                Debug.LogWarning("[Zendaya AR] Response prefab or container not set");
                return;
            }

            // Calculate position in front of user
            Vector3 userPosition = Camera.main.transform.position;
            Vector3 userForward = Camera.main.transform.forward;
            Vector3 spawnPosition = userPosition + userForward * responseDistance;

            // Add some randomness to avoid overlapping
            spawnPosition += new Vector3(
                Random.Range(-0.5f, 0.5f),
                Random.Range(-0.2f, 0.3f),
                Random.Range(-0.2f, 0.2f)
            );

            // Create response object
            GameObject responseObj = Instantiate(responseTextPrefab, spawnPosition, Quaternion.identity, responseContainer);
            
            // Configure text
            TextMeshPro textMesh = responseObj.GetComponent<TextMeshPro>();
            if (textMesh != null)
            {
                textMesh.text = text;
                textMesh.color = isError ? Color.red : Color.cyan;
                textMesh.fontSize = 0.1f;
                textMesh.alignment = TextAlignmentOptions.Center;
            }

            // Make it face the user
            responseObj.transform.LookAt(Camera.main.transform);
            responseObj.transform.Rotate(0, 180, 0); // Flip to face user

            // Add to queue and manage count
            activeResponses.Enqueue(responseObj);
            if (activeResponses.Count > maxActiveResponses)
            {
                GameObject oldResponse = activeResponses.Dequeue();
                if (oldResponse != null)
                {
                    Destroy(oldResponse);
                }
            }

            // Auto-destroy after lifetime
            Destroy(responseObj, responseLifetime);

            // Add floating animation
            StartCoroutine(AnimateFloatingText(responseObj));
        }

        private IEnumerator AnimateFloatingText(GameObject textObj)
        {
            Vector3 startPos = textObj.transform.position;
            float elapsedTime = 0f;
            float animationDuration = 2f;

            while (textObj != null && elapsedTime < animationDuration)
            {
                elapsedTime += Time.deltaTime;
                float progress = elapsedTime / animationDuration;
                
                // Gentle floating motion
                float yOffset = Mathf.Sin(progress * Mathf.PI * 2) * 0.1f;
                textObj.transform.position = startPos + Vector3.up * yOffset;
                
                yield return null;
            }
        }

        private void UpdateStatus(string message)
        {
            if (statusText != null)
            {
                statusText.text = $"[Zendaya] {message}";
            }
            
            if (enableDebugLogs)
            {
                Debug.Log($"[Zendaya AR] Status: {message}");
            }
        }

        // Voice command keywords that MRTK should recognize
        private void OnEnable()
        {
            // Register voice commands
            var speechCommands = new string[]
            {
                "Zendaya hello",
                "Zendaya help",
                "Zendaya status",
                "Zendaya weather",
                "Zendaya time",
                "Zendaya calendar"
            };

            // In a real implementation, you'd register these with MRTK's speech system
        }
    }
}