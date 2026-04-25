using UnityEngine;
using TMPro;

namespace ZendayaAR
{
    public class WeatherVisualization : MonoBehaviour
    {
        [Header("Weather Models")]
        public GameObject sunModel;
        public GameObject cloudModel;
        public GameObject rainModel;
        public GameObject snowModel;
        
        [Header("Animation Settings")]
        public float rotationSpeed = 30f;
        public float bobSpeed = 1f;
        public float bobHeight = 0.1f;
        
        private GameObject currentWeatherModel;
        private Vector3 initialPosition;
        private float bobTimer;

        private void Start()
        {
            initialPosition = transform.position;
        }

        private void Update()
        {
            if (currentWeatherModel != null)
            {
                // Rotate the weather model
                currentWeatherModel.transform.Rotate(Vector3.up, rotationSpeed * Time.deltaTime);
                
                // Add gentle bobbing motion
                bobTimer += Time.deltaTime * bobSpeed;
                Vector3 newPosition = initialPosition + Vector3.up * Mathf.Sin(bobTimer) * bobHeight;
                currentWeatherModel.transform.position = newPosition;
            }
        }

        public void ShowWeather(string weatherCondition, string temperature)
        {
            // Clear existing model
            if (currentWeatherModel != null)
            {
                Destroy(currentWeatherModel);
            }

            // Determine which model to show based on weather condition
            GameObject modelToInstantiate = null;
            string condition = weatherCondition.ToLower();

            if (condition.Contains("sun") || condition.Contains("clear"))
            {
                modelToInstantiate = sunModel;
            }
            else if (condition.Contains("cloud") || condition.Contains("overcast"))
            {
                modelToInstantiate = cloudModel;
            }
            else if (condition.Contains("rain") || condition.Contains("drizzle"))
            {
                modelToInstantiate = rainModel;
            }
            else if (condition.Contains("snow") || condition.Contains("blizzard"))
            {
                modelToInstantiate = snowModel;
            }
            else
            {
                // Default to cloud for unknown conditions
                modelToInstantiate = cloudModel;
            }

            if (modelToInstantiate != null)
            {
                // Instantiate the weather model
                currentWeatherModel = Instantiate(modelToInstantiate, transform.position, transform.rotation);
                currentWeatherModel.transform.SetParent(transform);
                
                // Scale it appropriately for AR
                currentWeatherModel.transform.localScale = Vector3.one * 0.3f;
                
                // Add temperature text below the model
                CreateTemperatureText(temperature);
            }
        }

        private void CreateTemperatureText(string temperature)
        {
            GameObject textObj = new GameObject("TemperatureText");
            textObj.transform.SetParent(transform);
            textObj.transform.localPosition = Vector3.down * 0.5f;
            
            TextMeshPro textMesh = textObj.AddComponent<TextMeshPro>();
            textMesh.text = temperature;
            textMesh.fontSize = 0.2f;
            textMesh.color = Color.white;
            textMesh.alignment = TextAlignmentOptions.Center;
            
            // Make text face the camera
            textObj.transform.LookAt(Camera.main.transform);
            textObj.transform.Rotate(0, 180, 0);
        }

        public void HideWeather()
        {
            if (currentWeatherModel != null)
            {
                Destroy(currentWeatherModel);
                currentWeatherModel = null;
            }
        }
    }
}