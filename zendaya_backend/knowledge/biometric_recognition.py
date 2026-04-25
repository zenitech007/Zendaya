# main_biometric_system.py

"""
Production-Ready Biometric Recognition System

This system combines a robust SQLite backend for profile management and history
logging with advanced feature extraction for face and voice recognition.

Key Features:
- Persistent profiles and recognition history stored in a SQLite database.
- Advanced voice feature extraction (MFCCs, spectral analysis).
- Face recognition using dlib's state-of-the-art model.
- Verification APIs for both face and voice modalities.
- Helper method for real-time processing of media streams (e.g., from WebSockets).
- Designed for robustness with lazy-loading of heavy libraries and safe
  database handling for multi-threaded environments.
"""

import os
import json
import sqlite3
import pickle
import hashlib
import base64
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from typing_extensions import TYPE_CHECKING
if TYPE_CHECKING:
    import numpy as np

# Light standard libraries are imported at the top.
# Heavy libraries (numpy, cv2, face_recognition, etc.) are lazy-loaded
# inside methods to ensure fast application startup and test-friendliness.


class BiometricRecognitionSystem:
    """A comprehensive system for face and voice biometric recognition."""

    def __init__(self, data_dir: str = "biometric_system_data"):
        """
        Initializes the biometric system.

        :param data_dir: The root directory to store all biometric data,
                         including the SQLite database and embedding files.
        """
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Define paths for database and embedding storage
        self.db_path = self.data_dir / "profiles.db"
        self.voice_models_dir = self.data_dir / "voice_models"
        self.face_encodings_dir = self.data_dir / "face_encodings"

        self.voice_models_dir.mkdir(exist_ok=True)
        self.face_encodings_dir.mkdir(exist_ok=True)

        # In-memory cache for loaded biometric data
        self.known_voices: Dict[str, Dict[str, Any]] = {}
        self.known_faces: Dict[str, Dict[str, Any]] = {}

        # Use check_same_thread=False for safe use in multi-threaded apps (like web servers)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)

        self._initialize_database()
        self._load_known_profiles()
        print(f"✅ Biometric system initialized. Data stored in: {self.data_dir}")

    @property
    def profiles_db(self):
        """For test compatibility: alias for db_path"""
        return self.db_path

    # ---------------------------------------------------------------------- #
    # Initialization and Data Loading
    # ---------------------------------------------------------------------- #

    def _initialize_database(self):
        """Creates the necessary SQLite tables if they don't exist."""
        if not self.conn:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    relationship TEXT,
                    voice_profile_path TEXT,
                    face_encoding_path TEXT,
                    preferences TEXT,
                    last_seen TIMESTAMP,
                    recognition_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recognition_history (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    recognition_type TEXT NOT NULL, -- 'face' or 'voice'
                    confidence REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
                )
                """
            )

    def _load_known_profiles(self):
        """Loads all existing user profiles and their biometric data from disk into memory."""
        if not self.conn:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        cursor = self.conn.execute("SELECT user_id, name, voice_profile_path, face_encoding_path FROM user_profiles")
        profiles = cursor.fetchall()

        for user_id, name, voice_path, face_path in profiles:
            # Load voice profile if it exists and is valid
            if voice_path and Path(voice_path).exists():
                try:
                    with open(voice_path, "rb") as f:
                        self.known_voices[user_id] = {"name": name, "features": pickle.load(f)}
                except (pickle.UnpicklingError, EOFError) as e:
                    print(f"⚠️ Warning: Could not load voice profile for {user_id}: {e}")

            # Load face encoding if it exists and is valid
            if face_path and Path(face_path).exists():
                try:
                    with open(face_path, "rb") as f:
                        self.known_faces[user_id] = {"name": name, "encoding": pickle.load(f)}
                except (pickle.UnpicklingError, EOFError) as e:
                    print(f"⚠️ Warning: Could not load face profile for {user_id}: {e}")
        
        print(f"👤 Loaded {len(self.known_faces)} face profiles and {len(self.known_voices)} voice profiles from disk.")

    # ---------------------------------------------------------------------- #
    # Core Feature Extraction (Internal Methods)
    # ---------------------------------------------------------------------- #

    def _extract_face_features(self, image_data: bytes) -> Optional['np.ndarray']:
        """Extracts a 128-dimension face encoding from image bytes."""
        try:
            import numpy as np
            import cv2
            import face_recognition
        except ImportError as e:
            print(f"🚨 Error: Missing required libraries for face recognition: {e}")
            return None

        try:
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                return None

            # Convert from BGR (OpenCV default) to RGB (face_recognition default)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Use the first face found
            face_encodings = face_recognition.face_encodings(rgb_image)
            return face_encodings[0] if face_encodings else None
        except Exception as e:
            # For production, replace print with a proper logger
            print(f"Error during face feature extraction: {e}")
            return None

    def _extract_voice_features(self, audio_data: bytes) -> Optional['np.ndarray']:
        """Extracts a feature vector from audio bytes using advanced metrics."""
        try:
            import numpy as np
            import librosa
        except ImportError as e:
            print(f"🚨 Error: Missing required libraries for voice recognition: {e}")
            return None

        # Use a temporary file to handle audio data, as librosa works best with file paths
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(audio_data)

        try:
            y, sr = librosa.load(temp_path, sr=16000, mono=True)
            
            # Extract a richer set of features
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            
            features = np.concatenate([
                np.mean(mfccs, axis=1),
                np.std(mfccs, axis=1),
                np.atleast_1d(np.mean(spectral_centroids)),
                np.atleast_1d(np.mean(spectral_rolloff)),
            ])
            
            # Normalize the feature vector
            norm = np.linalg.norm(features)
            return features / norm if norm != 0 else features

        except Exception as e:
            print(f"Error during voice feature extraction: {e}")
            return None
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    # ---------------------------------------------------------------------- #
    # Public API: Registration and Verification
    # ---------------------------------------------------------------------- #

    def register_user(
        self,
        name: str,
        relationship: str,
        image_data: Optional[bytes] = None,
        audio_data: Optional[bytes] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Registers a new user with their biometric data.

        Raises:
            ValueError: If no valid biometric data (image or audio) is provided.
        Returns:
            The unique user_id for the newly registered user.
        """
        user_id = hashlib.md5(f"{name}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        
        face_path, voice_path = None, None
        has_biometrics = False

        # Process and save face encoding
        if image_data:
            face_encoding = self._extract_face_features(image_data)
            if face_encoding is not None:
                face_path = str(self.face_encodings_dir / f"{user_id}_face.pkl")
                with open(face_path, "wb") as f:
                    pickle.dump(face_encoding, f)
                self.known_faces[user_id] = {"name": name, "encoding": face_encoding}
                has_biometrics = True

        # Process and save voice features
        if audio_data:
            voice_features = self._extract_voice_features(audio_data)
            if voice_features is not None:
                voice_path = str(self.voice_models_dir / f"{user_id}_voice.pkl")
                with open(voice_path, "wb") as f:
                    pickle.dump(voice_features, f)
                self.known_voices[user_id] = {"name": name, "features": voice_features}
                has_biometrics = True

        if not has_biometrics:
            raise ValueError("Registration failed: No valid biometric data provided.")

        # Save user profile to the database
        if not self.conn:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO user_profiles (user_id, name, relationship, face_encoding_path, voice_profile_path, preferences)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, name, relationship, face_path, voice_path, json.dumps(preferences or {})),
            )
        
        print(f"✅ User '{name}' registered successfully with ID: {user_id}")
        return user_id

    def verify_face(self, image_data: bytes, threshold: float = 0.6) -> Optional[Dict[str, Any]]:
        """
        Verifies an image against all known faces.

        :param image_data: The image bytes to verify.
        :param threshold: Distance threshold for a match. Lower is stricter.
        :return: A dictionary with match details or None if no match is found.
        """
        if not self.known_faces:
            return None
            
        import numpy as np

        unknown_encoding = self._extract_face_features(image_data)
        if unknown_encoding is None:
            return None

        distances = {
            user_id: np.linalg.norm(unknown_encoding - profile["encoding"])
            for user_id, profile in self.known_faces.items()
        }
        
        if not distances:
            return None

        best_match_id = min(distances.items(), key=lambda x: x[1])[0]
        best_distance = distances[best_match_id]

        if best_distance < threshold:
            confidence = max(0.0, 1.0 - (best_distance / threshold))
            result = {
                "user_id": best_match_id,
                "name": self.known_faces[best_match_id]["name"],
                "distance": best_distance,
                "confidence": confidence,
            }
            self._log_recognition(best_match_id, "face", float(confidence))
            return result
        
        return None

    def verify_voice(self, audio_data: bytes, threshold: float = 0.7) -> Optional[Dict[str, Any]]:
        """
        Verifies an audio clip against all known voices.
        
        :param audio_data: The audio bytes to verify.
        :param threshold: Cosine similarity threshold. Higher is stricter.
        :return: A dictionary with match details or None.
        """
        if not self.known_voices:
            return None

        from sklearn.metrics.pairwise import cosine_similarity

        unknown_features = self._extract_voice_features(audio_data)
        if unknown_features is None:
            return None

        similarities = {}
        for user_id, profile in self.known_voices.items():
            sim = cosine_similarity(unknown_features.reshape(1, -1), profile["features"].reshape(1, -1))[0][0]
            similarities[user_id] = sim

        if not similarities:
            return None
        
        best_match_id = max(similarities, key=lambda k: similarities[k])
        best_similarity = similarities[best_match_id]

        if best_similarity >= threshold:
            result = {
                "user_id": best_match_id,
                "name": self.known_voices[best_match_id]["name"],
                "similarity": best_similarity,
                "confidence": best_similarity,
            }
            self._log_recognition(best_match_id, "voice", best_similarity)
            return result
        
        return None

    # ---------------------------------------------------------------------- #
    # Real-time Processing and Profile Management
    # ---------------------------------------------------------------------- #

    def process_realtime_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processes a message from a real-time stream (e.g., WebSocket).
        
        Expected format:
        {
            "media_type": "image" | "audio",
            "encoding": "<base64_encoded_string>"
        }
        """
        try:
            media_type = message.get("media_type")
            b64_data = message.get("encoding")

            if not media_type or not b64_data:
                return None

            data = base64.b64decode(b64_data)
            result = None

            if media_type == "image":
                result = self.verify_face(data)
                if result:
                    return {"event": "face_recognized", "result": result, "timestamp": datetime.now().isoformat()}
            
            elif media_type == "audio":
                result = self.verify_voice(data)
                if result:
                    return {"event": "voice_recognized", "result": result, "timestamp": datetime.now().isoformat()}
            
            return None
        except Exception as e:
            print(f"Error processing real-time message: {e}")
            return None

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a user's full profile from the database."""
        if not self.conn:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        cursor = self.conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        profile = dict(zip(columns, row))
        profile["preferences"] = json.loads(profile.get("preferences") or "{}")
        return profile

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Returns a list of all registered users."""
        cursor = self.conn.execute("SELECT user_id, name, relationship, recognition_count, last_seen FROM user_profiles ORDER BY name") # type: ignore
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_all_family_members(self):
        """Returns all users (for test compatibility, includes all relationships)."""
        if not self.conn:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        cursor = self.conn.execute("SELECT user_id, name, relationship FROM user_profiles")
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def is_family_present(self):
        """Returns a list of family members recognized recently (for test compatibility)."""
        # For test, just return empty if no recognition history
        recent = self.get_recently_seen_users(minutes=30)
        return [user for user in recent if user.get('relationship') == 'family']

    def get_recently_seen_users(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Returns users recognized in the last N minutes.
        """
        if not self.conn:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        query = """
            SELECT DISTINCT up.user_id, up.name, up.relationship, MAX(rh.timestamp) as last_event_time
            FROM user_profiles up
            JOIN recognition_history rh ON up.user_id = rh.user_id
            WHERE rh.timestamp > datetime('now', ?)
            GROUP BY up.user_id
            ORDER BY last_event_time DESC
        """
        cursor = self.conn.execute(query, (f'-{minutes} minutes',))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # ---------------------------------------------------------------------- #
    # Internal Logging and Maintenance
    # ---------------------------------------------------------------------- #

    def _log_recognition(self, user_id: str, recognition_type: str, confidence: float):
        """Logs a recognition event to the history table and updates the user's profile."""
        if not self.conn:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        with self.conn:
            # Log the event
            self.conn.execute(
                "INSERT INTO recognition_history (user_id, recognition_type, confidence) VALUES (?, ?, ?)",
                (user_id, recognition_type, confidence)
            )
            # Update the user's last seen time and count
            self.conn.execute(
                "UPDATE user_profiles SET last_seen = CURRENT_TIMESTAMP, recognition_count = recognition_count + 1 WHERE user_id = ?",
                (user_id,)
            )

    def close(self):
        """Closes the database connection gracefully."""
        if self.conn:
            self.conn.close()
            self.conn = None
            print("Database connection closed.")

    def recognize_voice(self, audio_data: bytes, threshold: float = 0.7):
        return self.verify_voice(audio_data, threshold)

    def recognize_face(self, image_data: bytes, threshold: float = 0.6):
        return self.verify_face(image_data, threshold)


# ---------------------------------------------------------------------- #
# Example Usage
# ---------------------------------------------------------------------- #
def create_dummy_image(text="face"):
    """Creates a dummy JPEG image bytes for testing."""
    import numpy as np
    import cv2
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, text, (10, 70), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
    _, buffer = cv2.imencode('.jpg', img)
    return buffer.tobytes()

def create_dummy_audio():
    """Creates dummy WAV audio bytes for testing."""
    import numpy as np
    import scipy.io.wavfile
    import io
    
    sample_rate = 16000
    duration = 2 # seconds
    frequency = 440 # Hz
    t = np.linspace(0., duration, int(sample_rate * duration))
    amplitude = np.iinfo(np.int16).max * 0.5
    data = amplitude * np.sin(2. * np.pi * frequency * t)
    
    buffer = io.BytesIO()
    scipy.io.wavfile.write(buffer, sample_rate, data.astype(np.int16))
    return buffer.getvalue()


if __name__ == "__main__":
    # Note: For this example to run, you need to install the required libraries:
    # pip install numpy opencv-python dlib face_recognition librosa scikit-learn scipy
    
    print("--- Biometric System Demo ---")
    
    # Initialize the system
    # This will create a 'biometric_system_data' folder in your current directory
    try:
        system = BiometricRecognitionSystem()
    
        # Create dummy data (replace with real data in a real application)
        # IMPORTANT: face_recognition will not find a face in this dummy image.
        # This part of the demo is for API illustration. Use a real photo for registration.
        print("\nCreating dummy biometric data for demonstration...")
        # dummy_face_data = create_dummy_image("John") 
        dummy_voice_data = create_dummy_audio()
    
        # For a real test, load an actual image file
        # For example: with open("path/to/your_photo.jpg", "rb") as f: real_face_data = f.read()
        
        # Step 1: Register a new user
        print("\n--- Step 1: Registering User ---")
        try:
            # You would use real_face_data here instead of None
            user_id_john = system.register_user(
                name="John Doe",
                relationship="Friend",
                audio_data=dummy_voice_data,
                image_data=None # Replace with real_face_data
            )
            print(f"John Doe's profile: {system.get_user_profile(user_id_john)}")
        except ValueError as e:
            print(f"Registration Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during registration: {e}")
            print("Please ensure dlib and face_recognition are installed correctly.")

        # Step 2: Verify a user
        print("\n--- Step 2: Verifying User ---")
        # Let's try to verify John's voice
        verification_result = system.verify_voice(dummy_voice_data)
        if verification_result:
            print(f"Voice verification successful: {verification_result}")
        else:
            print("Voice verification failed.")
            
        # Step 3: List all users
        print("\n--- Step 3: Listing All Users ---")
        all_users = system.get_all_users()
        print(json.dumps(all_users, indent=2))
    
        # Step 4: Check for recently seen users
        print("\n--- Step 4: Checking Recently Seen Users ---")
        recent_users = system.get_recently_seen_users(minutes=5)
        print(f"Users seen in the last 5 minutes: {json.dumps(recent_users, indent=2)}")
        
        # Clean up
        system.close()
        
    except ImportError as e:
        print("\n🚨 DEMO FAILED: A required library is not installed.")
        print(f"Error: {e}")
        print("Please run: pip install numpy opencv-python dlib face_recognition librosa scikit-learn scipy")
    except Exception as e:
        print(f"\n🚨 An unexpected error occurred: {e}")