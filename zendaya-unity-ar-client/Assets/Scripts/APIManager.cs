using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace ZendayaAR
{
    [System.Serializable]
    public class ChatRequest
    {
        public string message;
        public string user_id = "unity_ar_client";
        public bool voice_enabled = true;
    }

    [System.Serializable]
    public class ChatResponse
    {
        public string text;
        public string audio_url;
        public string timestamp;
    }

    public class APIManager : MonoBehaviour
    {
        [Header("API Configuration")]
        public string baseUrl = "http://localhost:8000";
        
        [Header("Debug")]
        public bool enableDebugLogs = true;

        private void Start()
        {
            // Test connection on start
            StartCoroutine(TestConnection());
        }

        public void SendMessage(string message, System.Action<ChatResponse> onSuccess, System.Action<string> onError)
        {
            StartCoroutine(SendMessageCoroutine(message, onSuccess, onError));
        }

        private IEnumerator SendMessageCoroutine(string message, System.Action<ChatResponse> onSuccess, System.Action<string> onError)
        {
            var request = new ChatRequest
            {
                message = message,
                user_id = "unity_ar_client",
                voice_enabled = true
            };

            string jsonData = JsonUtility.ToJson(request);
            byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonData);

            using (UnityWebRequest webRequest = new UnityWebRequest($"{baseUrl}/chat", "POST"))
            {
                webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
                webRequest.downloadHandler = new DownloadHandlerBuffer();
                webRequest.SetRequestHeader("Content-Type", "application/json");

                if (enableDebugLogs)
                {
                    Debug.Log($"[Zendaya API] Sending message: {message}");
                }

                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    try
                    {
                        ChatResponse response = JsonUtility.FromJson<ChatResponse>(webRequest.downloadHandler.text);
                        
                        if (enableDebugLogs)
                        {
                            Debug.Log($"[Zendaya API] Response received: {response.text}");
                        }

                        onSuccess?.Invoke(response);
                    }
                    catch (Exception e)
                    {
                        string error = $"JSON parsing error: {e.Message}";
                        Debug.LogError($"[Zendaya API] {error}");
                        onError?.Invoke(error);
                    }
                }
                else
                {
                    string error = $"Request failed: {webRequest.error}";
                    Debug.LogError($"[Zendaya API] {error}");
                    onError?.Invoke(error);
                }
            }
        }

        private IEnumerator TestConnection()
        {
            using (UnityWebRequest webRequest = UnityWebRequest.Get($"{baseUrl}/health"))
            {
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    Debug.Log("[Zendaya API] Connection successful - Backend is online");
                }
                else
                {
                    Debug.LogWarning($"[Zendaya API] Connection failed: {webRequest.error}");
                }
            }
        }

        public void GetHealth(System.Action<string> onResult)
        {
            StartCoroutine(GetHealthCoroutine(onResult));
        }

        private IEnumerator GetHealthCoroutine(System.Action<string> onResult)
        {
            using (UnityWebRequest webRequest = UnityWebRequest.Get($"{baseUrl}/health"))
            {
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    onResult?.Invoke(webRequest.downloadHandler.text);
                }
                else
                {
                    onResult?.Invoke($"Health check failed: {webRequest.error}");
                }
            }
        }
    }
}