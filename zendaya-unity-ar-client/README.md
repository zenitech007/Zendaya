# Zendaya Unity AR Client

HoloLens 2 augmented reality client for the Zendaya AI Assistant system.

## 🥽 Features

- **3D Floating Responses**: AI responses appear as floating text objects in AR space
- **Voice Commands**: Use "Zendaya [command]" to interact hands-free
- **MRTK Integration**: Built with Microsoft Mixed Reality Toolkit
- **Real-time Communication**: Direct connection to Zendaya backend API

## 🛠️ Setup Requirements

### Unity Version
- Unity 2022.3 LTS or newer
- Universal Windows Platform (UWP) build support

### Required Packages
- Mixed Reality Toolkit (MRTK) 2.8+
- TextMeshPro
- Universal Windows Platform support

### HoloLens 2 Requirements
- Windows 10/11 with Developer Mode enabled
- Visual Studio 2022 with UWP workload
- HoloLens 2 device or HoloLens 2 Emulator

## 🚀 Setup Instructions

### 1. Unity Project Setup
1. Open Unity Hub and create new 3D project
2. Import MRTK 2.8+ from Package Manager
3. Configure MRTK for HoloLens 2:
   - Go to Mixed Reality > Toolkit > Configure
   - Select HoloLens 2 configuration profile

### 2. Scene Setup
1. Create empty GameObject named "ZendayaManager"
2. Attach `ZendayaARManager.cs` script
3. Create TextMeshPro prefab for floating responses
4. Configure MRTK speech input for voice commands

### 3. Build Configuration
1. File > Build Settings
2. Switch platform to Universal Windows Platform
3. Set Target Device Family to HoloLens
4. Set Architecture to ARM64 (for device) or x64 (for emulator)

### 4. Backend Connection
- Ensure Zendaya backend is running on accessible network
- Update `baseUrl` in APIManager to point to your backend
- For HoloLens device, use your computer's IP address

## 🎮 Usage

### Voice Commands
- **"Zendaya hello"** - Greet the assistant
- **"Zendaya help"** - Get assistance
- **"Zendaya weather"** - Check weather
- **"Zendaya time"** - Get current time
- **"Zendaya calendar"** - Check calendar events

### Interaction Flow
1. Say "Zendaya [your command]"
2. Voice command is sent to backend API
3. AI response appears as floating 3D text
4. Text automatically faces user and gently animates
5. Responses auto-expire after 10 seconds

## 🔧 Development

### Key Scripts
- **`ZendayaARManager.cs`**: Main AR interaction manager
- **`APIManager.cs`**: Backend API communication
- **`FloatingTextPrefab.cs`**: 3D text response behavior

### Customization
- Modify voice commands in `ZendayaARManager.OnEnable()`
- Adjust floating text behavior in `FloatingTextPrefab.cs`
- Configure response positioning and lifetime in inspector

### Testing
1. **Unity Editor**: Test API calls without AR features
2. **HoloLens Emulator**: Full AR testing without device
3. **HoloLens Device**: Complete experience testing

## 📱 Deployment

### For HoloLens Device
1. Build UWP solution from Unity
2. Open generated Visual Studio solution
3. Set to ARM64, Release mode
4. Deploy to HoloLens 2 via USB or WiFi

### For HoloLens Emulator
1. Build UWP solution from Unity
2. Open in Visual Studio
3. Set to x64, Debug mode
4. Deploy to HoloLens 2 Emulator

## 🎯 Future Enhancements

- [ ] Gesture-based interactions
- [ ] 3D visualization of data
- [ ] Spatial anchoring for persistent responses
- [ ] Multi-user AR collaboration
- [ ] Advanced voice recognition with wake words
- [ ] Integration with HoloLens eye tracking

---

**Experience the future of AI interaction in augmented reality.**