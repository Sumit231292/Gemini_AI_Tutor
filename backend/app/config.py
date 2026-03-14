"""
Configuration for EduNova backend.
Loads settings from environment variables.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # Google Cloud / Gemini
    google_api_key: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_API_KEY", "")
    )
    google_cloud_project: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    )
    google_cloud_region: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    )

    # Gemini model settings
    gemini_model: str = field(
        default_factory=lambda: os.environ.get(
            "GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest"
        )
    )
    gemini_vision_model: str = field(
        default_factory=lambda: os.environ.get(
            "GEMINI_VISION_MODEL", "gemini-2.5-flash"
        )
    )

    # Server settings
    host: str = field(default_factory=lambda: os.environ.get("HOST", "0.0.0.0"))
    port: int = field(
        default_factory=lambda: int(os.environ.get("PORT", "8000"))
    )
    debug: bool = field(
        default_factory=lambda: os.environ.get("DEBUG", "false").lower() == "true"
    )

    # Audio settings
    audio_sample_rate: int = 24000  # Gemini Live API uses 24kHz
    audio_channels: int = 1

    # Session settings
    max_session_duration: int = 3600  # 1 hour max session
    session_cleanup_interval: int = 300  # Clean up stale sessions every 5 min

    def validate(self) -> None:
        """Validate required settings are present."""
        if not self.google_api_key and not self.google_cloud_project:
            raise ValueError(
                "Either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT must be set"
            )


settings = Settings()
