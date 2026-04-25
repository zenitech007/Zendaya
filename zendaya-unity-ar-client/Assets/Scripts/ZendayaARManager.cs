using UnityEngine;
using ReadyPlayerMe;

public class ZendayaARManager : MonoBehaviour
{
    [Header("Ready Player Me Avatar")]
    [SerializeField] private string avatarUrl = "https://readyplayer.me/avatar/default.glb"; // fallback
    private GameObject zendayaAvatar;
    private AvatarLoader loader;

    void Start()
    {
        // Load the avatar dynamically
        loader = new AvatarLoader();

        // Load avatar URL from environment (from backend)
        string envUrl = GetAvatarUrlFromBackend();

        if (!string.IsNullOrEmpty(envUrl))
            avatarUrl = envUrl;

        Debug.Log($"🧠 Loading Zendaya Hologram Avatar: {avatarUrl}");
        loader.LoadAvatar(avatarUrl, OnAvatarLoaded, OnAvatarFailed);
    }

    private void OnAvatarLoaded(GameObject avatar)
    {
        zendayaAvatar = avatar;
        zendayaAvatar.transform.position = new Vector3(0, -1.5f, 0);
        zendayaAvatar.transform.localScale = Vector3.one * 1.1f;
        zendayaAvatar.transform.rotation = Quaternion.Euler(0, 180, 0);

        Debug.Log("✅ Zendaya hologram avatar loaded successfully!");
    }

    private void OnAvatarFailed(FailureType type, string message)
    {
        Debug.LogError($"❌ Failed to load Zendaya avatar: {message}");
    }

    private string GetAvatarUrlFromBackend()
    {
        // (Optional) Fetch dynamically from backend API later
        // For now, just use .env version
        return "https://readyplayer.me/avatar/7e4f61b3332e7f9f9ddfa8d.glb";
    }
}
