using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace ZendayaAR
{
    public class SettingsManager : MonoBehaviour
    {
        [Header("UI References")]
        public GameObject settingsPanel;
        public TMP_InputField ipAddressInput;
        public Button saveButton;
        public Button cancelButton;
        public Button openSettingsButton;

        [Header("Default Settings")]
        public string defaultIP = "192.168.1.100";
        public int defaultPort = 8000;

        private APIManager apiManager;
        private string currentServerUrl;

        private void Start()
        {
            apiManager = FindObjectOfType<APIManager>();
            
            // Setup UI events
            saveButton.onClick.AddListener(SaveSettings);
            cancelButton.onClick.AddListener(CloseSettings);
            openSettingsButton.onClick.AddListener(OpenSettings);
            
            // Load saved settings
            LoadSettings();
            
            // Hide settings panel initially
            settingsPanel.SetActive(false);
        }

        public void OpenSettings()
        {
            settingsPanel.SetActive(true);
            
            // Parse current URL to show in input field
            if (!string.IsNullOrEmpty(currentServerUrl))
            {
                var uri = new System.Uri(currentServerUrl);
                ipAddressInput.text = uri.Host;
            }
            else
            {
                ipAddressInput.text = defaultIP;
            }
        }

        public void CloseSettings()
        {
            settingsPanel.SetActive(false);
        }

        public void SaveSettings()
        {
            string ipAddress = ipAddressInput.text.Trim();
            
            if (string.IsNullOrEmpty(ipAddress))
            {
                Debug.LogWarning("[Settings] IP address cannot be empty");
                return;
            }

            // Validate IP address format
            if (!IsValidIPAddress(ipAddress))
            {
                Debug.LogWarning("[Settings] Invalid IP address format");
                return;
            }

            // Construct new server URL
            string newServerUrl = $"http://{ipAddress}:{defaultPort}";
            
            // Save to PlayerPrefs
            PlayerPrefs.SetString("ServerURL", newServerUrl);
            PlayerPrefs.Save();
            
            // Update API manager
            if (apiManager != null)
            {
                apiManager.UpdateServerUrl(newServerUrl);
            }
            
            currentServerUrl = newServerUrl;
            
            Debug.Log($"[Settings] Server URL updated to: {newServerUrl}");
            CloseSettings();
        }

        private void LoadSettings()
        {
            currentServerUrl = PlayerPrefs.GetString("ServerURL", $"http://{defaultIP}:{defaultPort}");
            
            if (apiManager != null)
            {
                apiManager.UpdateServerUrl(currentServerUrl);
            }
            
            Debug.Log($"[Settings] Loaded server URL: {currentServerUrl}");
        }

        private bool IsValidIPAddress(string ipAddress)
        {
            // Basic IP address validation
            string[] parts = ipAddress.Split('.');
            
            if (parts.Length != 4)
                return false;
            
            foreach (string part in parts)
            {
                if (!int.TryParse(part, out int num) || num < 0 || num > 255)
                    return false;
            }
            
            return true;
        }

        public string GetCurrentServerUrl()
        {
            return currentServerUrl;
        }
    }
}