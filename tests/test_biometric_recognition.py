"""
Tests for BiometricRecognitionSystem
"""
import pytest
import os
import tempfile
import shutil
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from zendaya_backend.knowledge.biometric_recognition import BiometricRecognitionSystem


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for biometric data"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Use a robust rmtree to handle potential file locks on Windows
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def biometric_system(temp_data_dir):
    """Create and properly tear down the BiometricRecognitionSystem instance"""
    system = BiometricRecognitionSystem(data_dir=temp_data_dir)
    yield system
    # Ensure the database connection is closed after each test
    system.close()


class TestBiometricRecognitionSystem:
    """Test BiometricRecognitionSystem"""

    def test_initialization(self, biometric_system, temp_data_dir):
        """Test system initialization"""
        assert biometric_system.data_dir.exists()
        assert biometric_system.voice_models_dir.exists()
        assert biometric_system.face_encodings_dir.exists()
        assert biometric_system.db_path.exists()

    def test_database_creation(self, biometric_system):
        """Test database tables are created"""
        import sqlite3

        with sqlite3.connect(biometric_system.db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='user_profiles'
            """)
            assert cursor.fetchone() is not None

            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='recognition_history'
            """)
            assert cursor.fetchone() is not None

    @patch('librosa.feature.spectral_rolloff')
    @patch('librosa.feature.spectral_centroid')
    @patch('librosa.feature.mfcc')
    @patch('librosa.load')
    def test_extract_voice_features(self, mock_load, mock_mfcc, mock_centroid, mock_rolloff, biometric_system):
        """Test voice feature extraction"""
        mock_load.return_value = (np.random.rand(22050), 22050)
        mock_mfcc.return_value = np.random.rand(13, 44)
        mock_centroid.return_value = np.random.rand(1, 44)
        mock_rolloff.return_value = np.random.rand(1, 44)

        audio_data = b"fake_audio_data"
        features = biometric_system._extract_voice_features(audio_data)

        assert features is not None
        assert isinstance(features, np.ndarray)

    @patch('face_recognition.face_encodings')
    @patch('cv2.cvtColor')
    @patch('cv2.imdecode')
    def test_extract_face_encoding(self, mock_imdecode, mock_cvtColor, mock_encodings, biometric_system):
        """Test face encoding extraction"""
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        mock_imdecode.return_value = mock_image
        mock_cvtColor.return_value = mock_image
        mock_encodings.return_value = [np.random.rand(128)]

        image_data = b"fake_image_data"
        encoding = biometric_system._extract_face_features(image_data)

        assert encoding is not None
        assert isinstance(encoding, np.ndarray)
        assert len(encoding) == 128

    def test_register_user_voice_only(self, biometric_system):
        """Test registering user with voice data only"""
        with patch.object(biometric_system, '_extract_voice_features') as mock_extract:
            mock_extract.return_value = np.random.rand(28)

            user_id = biometric_system.register_user(
                name="John Doe",
                relationship="family",
                audio_data=b"fake_audio",
                preferences={"language": "en", "tone": "casual"}
            )

            assert user_id is not None
            assert user_id in biometric_system.known_voices
            assert biometric_system.known_voices[user_id]['name'] == "John Doe"

    def test_register_user_face_only(self, biometric_system):
        """Test registering user with face data only"""
        with patch.object(biometric_system, '_extract_face_features') as mock_extract:
            mock_extract.return_value = np.random.rand(128)

            user_id = biometric_system.register_user(
                name="Jane Smith",
                relationship="friend",
                image_data=b"fake_image"
            )

            assert user_id is not None
            assert user_id in biometric_system.known_faces
            assert biometric_system.known_faces[user_id]['name'] == "Jane Smith"

    def test_register_user_both_biometrics(self, biometric_system):
        """Test registering user with both voice and face data"""
        with patch.object(biometric_system, '_extract_voice_features') as mock_voice, \
             patch.object(biometric_system, '_extract_face_features') as mock_face:

            mock_voice.return_value = np.random.rand(28)
            mock_face.return_value = np.random.rand(128)

            user_id = biometric_system.register_user(
                name="Bob Johnson",
                relationship="colleague",
                audio_data=b"fake_audio",
                image_data=b"fake_image"
            )

            assert user_id is not None
            assert user_id in biometric_system.known_voices
            assert user_id in biometric_system.known_faces

    def test_recognize_voice_success(self, biometric_system):
        """Test successful voice recognition"""
        with patch.object(biometric_system, '_extract_voice_features') as mock_extract:
            known_features = np.random.rand(28)
            mock_extract.return_value = known_features

            user_id = biometric_system.register_user(
                name="Alice",
                relationship="family",
                audio_data=b"fake_audio"
            )

            mock_extract.return_value = known_features

            result = biometric_system.verify_voice(b"new_audio")

            assert result is not None
            assert result['user_id'] == user_id
            assert result['name'] == "Alice"
            assert result['confidence'] >= 0.99

    def test_recognize_voice_failure(self, biometric_system):
        """Test voice recognition with unknown voice"""
        with patch.object(biometric_system, '_extract_voice_features') as mock_extract:
            mock_extract.return_value = np.random.rand(28)
            biometric_system.register_user(
                name="Known User",
                relationship="family",
                audio_data=b"fake_audio"
            )

            different_features = np.copy(mock_extract.return_value)
            different_features[0] += 100
            mock_extract.return_value = different_features
            
            result = biometric_system.verify_voice(b"unknown_audio")
            assert result is None

    def test_recognize_face_success(self, biometric_system):
        """Test successful face recognition"""
        with patch.object(biometric_system, '_extract_face_features') as mock_extract:
            known_encoding = np.random.rand(128)
            mock_extract.return_value = known_encoding

            user_id = biometric_system.register_user(
                name="Charlie",
                relationship="family",
                image_data=b"fake_image"
            )

            mock_extract.return_value = known_encoding

            result = biometric_system.verify_face(b"new_image")

            assert result is not None
            assert result['user_id'] == user_id
            assert result['name'] == "Charlie"

    def test_get_user_profile(self, biometric_system):
        """Test getting user profile"""
        with patch.object(biometric_system, '_extract_voice_features') as mock_extract:
            mock_extract.return_value = np.random.rand(28)

            user_id = biometric_system.register_user(
                name="David",
                relationship="family",
                audio_data=b"fake_audio",
                preferences={"theme": "dark", "notifications": True}
            )

            profile = biometric_system.get_user_profile(user_id)

            assert profile is not None
            assert profile['name'] == "David"
            assert profile['relationship'] == "family"
            assert profile['preferences']['theme'] == "dark"

    def test_get_all_users(self, biometric_system):
        """Test getting all registered users."""
        with patch.object(biometric_system, '_extract_voice_features') as mock_extract:
            mock_extract.return_value = np.random.rand(28)

            biometric_system.register_user("Alice", "family", audio_data=b"audio1")
            biometric_system.register_user("Bob", "family", audio_data=b"audio2")
            biometric_system.register_user("Charlie", "friend", audio_data=b"audio3")

            all_users = biometric_system.get_all_users()

            assert len(all_users) == 3
            user_names = {user['name'] for user in all_users}
            assert {"Alice", "Bob", "Charlie"} == user_names

    def test_get_recently_seen_users_empty(self, biometric_system):
        """Test recently seen users when none have been seen."""
        recent = biometric_system.get_recently_seen_users()
        assert recent == []

    def test_update_recognition_history(self, biometric_system):
        """Test recording recognition history"""
        import sqlite3

        with patch.object(biometric_system, '_extract_voice_features') as mock_extract:
            mock_extract.return_value = np.random.rand(28)

            user_id = biometric_system.register_user(
                name="Test User",
                relationship="family",
                audio_data=b"audio"
            )

            result = biometric_system.verify_voice(b"audio")
            assert result is not None

            with sqlite3.connect(biometric_system.db_path) as conn:
                history = conn.execute(
                    "SELECT COUNT(*) FROM recognition_history WHERE user_id = ?", (user_id,)
                ).fetchone()[0]

                assert history == 1

    def test_extract_voice_features_error_handling(self, biometric_system):
        """Test error handling in voice feature extraction"""
        with patch('librosa.load', side_effect=Exception("Audio error")):
            result = biometric_system._extract_voice_features(b"corrupted_audio")
            assert result is None

    def test_extract_face_encoding_no_face(self, biometric_system):
        """Test face encoding extraction with no face detected"""
        with patch('cv2.imdecode'), \
             patch('cv2.cvtColor'), \
             patch('face_recognition.face_encodings') as mock_encodings:

            mock_encodings.return_value = []

            encoding = biometric_system._extract_face_features(b"image_no_face")
            assert encoding is None

    def test_register_user_no_biometric_data(self, biometric_system):
        """Test registering user without any biometric data"""
        with pytest.raises(ValueError, match="Registration failed: No valid biometric data provided."):
            biometric_system.register_user(
                name="No Data User",
                relationship="friend"
            )

    def test_voice_feature_similarity_calculation(self):
        """Test voice feature similarity calculation (helper test, no fixture needed)"""
        feature1 = np.random.rand(28)
        feature2 = np.copy(feature1)

        from sklearn.metrics.pairwise import cosine_similarity
        similarity = cosine_similarity(np.array([feature1]), np.array([feature2]))[0][0]

        assert np.isclose(similarity, 1.0)

    def test_face_encoding_distance_calculation(self):
        """Test face encoding distance calculation (helper test, no fixture needed)"""
        encoding1 = np.random.rand(128)
        encoding2 = np.copy(encoding1)

        distance = np.linalg.norm(encoding1 - encoding2)

        assert np.isclose(distance, 0.0)