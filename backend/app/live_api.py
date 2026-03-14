"""
Gemini Live API session manager.
Handles real-time bidirectional streaming with Gemini for voice + vision tutoring.
"""

import asyncio
import base64
import json
import logging
import uuid
from typing import Any, Callable, Optional

from google import genai
from google.genai import types

from .config import settings

logger = logging.getLogger(__name__)

# System instruction for the AI tutor
TUTOR_SYSTEM_INSTRUCTION = """You are GeminiTutor, a friendly AI tutor.

Rules:
- Use the Socratic method: guide students to answers, don't give solutions directly.
- Be encouraging and patient. Use analogies and real-world examples.
- Keep voice responses SHORT — 1-3 sentences at a time. Be concise.
- When shown homework (image), identify the topic, ask what they've tried, then guide step-by-step.
- Speak naturally and conversationally. Verbalize math clearly.
- Handle interruptions gracefully.
- IMPORTANT: You MUST always respond in {language}. All your spoken and text responses must be in {language}. Never switch to a different language unless the student explicitly asks."""


class LiveSession:
    """Manages a single Gemini Live API session for real-time tutoring."""

    def __init__(
        self,
        session_id: str,
        on_audio: Optional[Callable] = None,
        on_text: Optional[Callable] = None,
        on_turn_complete: Optional[Callable] = None,
    ):
        self._ctx_manager = None  # async context manager for the live connection
        self.session_id = session_id
        self.on_audio = on_audio
        self.on_text = on_text
        self.on_turn_complete = on_turn_complete
        self._session = None
        self._client = None
        self._receive_task: Optional[asyncio.Task] = None
        self._active = False
        self._subject_context = ""

    async def connect(self, subject: str = "general", language: str = "en") -> None:
        """Establish connection to Gemini Live API."""
        self._subject_context = subject

        # Map language codes to full names for clearer instructions
        lang_names = {
            "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French",
            "de": "German", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
            "pt": "Portuguese", "ar": "Arabic", "bn": "Bengali", "ta": "Tamil",
            "te": "Telugu", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada",
            "ml": "Malayalam", "pa": "Punjabi", "ru": "Russian", "it": "Italian",
        }
        lang_full = lang_names.get(language, "English")
        system_instruction = TUTOR_SYSTEM_INSTRUCTION.format(language=lang_full)

        # Initialize the GenAI client
        if settings.google_api_key:
            self._client = genai.Client(api_key=settings.google_api_key)
        else:
            self._client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_region,
            )

        # Configure the Live API session
        # Use AUDIO modality for native audio model
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[
                    types.Part(
                        text=f"{system_instruction}\nSubject: {subject}."
                    )
                ]
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    silence_duration_ms=300,
                ),
            ),
            # Enable server-side transcription of AI audio output
            output_audio_transcription=types.AudioTranscriptionConfig(),
            # Enable server-side transcription of user audio input
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )

        # Connect to the Live API (returns an async context manager)
        logger.info(f"Connecting to Gemini model: {settings.gemini_model}")
        self._ctx_manager = self._client.aio.live.connect(
            model=settings.gemini_model,
            config=config,
        )
        self._session = await self._ctx_manager.__aenter__()
        self._active = True

        # Start the background receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())

        logger.info(f"Live session {self.session_id} connected (subject: {subject})")

    async def _receive_loop(self) -> None:
        """Background task that receives responses from Gemini Live API."""
        try:
            while self._active and self._session:
                try:
                    async for response in self._session.receive():
                        if not self._active:
                            break

                        server_content = response.server_content
                        if server_content is None:
                            continue

                        # Process parts of the response
                        if server_content.model_turn and server_content.model_turn.parts:
                            for part in server_content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    # Audio response
                                    audio_data = part.inline_data.data
                                    if isinstance(audio_data, bytes):
                                        encoded = base64.b64encode(audio_data).decode("utf-8")
                                    else:
                                        encoded = audio_data
                                    if self.on_audio:
                                        await self.on_audio(encoded)

                                elif part.text:
                                    # Text from native-audio model is its
                                    # reasoning / transcript — send it so the
                                    # frontend can display it in the chat.
                                    if self.on_text:
                                        await self.on_text(part.text)

                        # Server-side transcription of AI audio output
                        if server_content.output_transcription and server_content.output_transcription.text:
                            if self.on_text:
                                await self.on_text(server_content.output_transcription.text)

                        # Check if turn is complete
                        if server_content.turn_complete:
                            logger.info(f"Turn complete for session {self.session_id}")
                            if self.on_turn_complete:
                                await self.on_turn_complete()

                except asyncio.CancelledError:
                    raise  # re-raise so outer handler catches it
                except Exception as e:
                    if self._active:
                        logger.error(f"Error in receive loop: {e}", exc_info=True)
                    # Don't break — try to keep receiving on transient errors
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"Receive loop cancelled for session {self.session_id}")
        except Exception as e:
            logger.error(f"Fatal error in receive loop for {self.session_id}: {e}", exc_info=True)

    async def send_audio(self, audio_data: str) -> None:
        """Send audio data to Gemini Live API.
        
        Args:
            audio_data: Base64-encoded PCM audio data
        """
        if not self._session or not self._active:
            return

        try:
            raw_audio = base64.b64decode(audio_data)
            await self._session.send_realtime_input(
                media=types.Blob(
                    data=raw_audio,
                    mime_type="audio/pcm;rate=16000",
                )
            )
        except Exception as e:
            logger.error(f"Error sending audio: {e}")

    async def send_image(self, image_data: str, mime_type: str = "image/jpeg") -> None:
        """Send an image to Gemini Live API (e.g., photo of homework).
        
        Args:
            image_data: Base64-encoded image data
            mime_type: MIME type of the image
        """
        if not self._session or not self._active:
            return

        try:
            raw_image = base64.b64decode(image_data)
            await self._session.send_realtime_input(
                media=types.Blob(
                    data=raw_image,
                    mime_type=mime_type,
                )
            )
            logger.info(f"Image sent to session {self.session_id}")
        except Exception as e:
            logger.error(f"Error sending image: {e}")

    async def send_text(self, text: str) -> None:
        """Send a text message to Gemini Live API.
        
        Args:
            text: Text message from the student
        """
        if not self._session or not self._active:
            return

        try:
            await self._session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text=text)],
                ),
                turn_complete=True,
            )
        except Exception as e:
            logger.error(f"Error sending text: {e}")

    async def disconnect(self) -> None:
        """Close the Live API session."""
        self._active = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._session:
            try:
                await self._ctx_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            self._session = None
            self._ctx_manager = None

        logger.info(f"Live session {self.session_id} disconnected")


class SessionManager:
    """Manages multiple concurrent Live API sessions."""

    def __init__(self):
        self._sessions: dict[str, LiveSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_session(
        self,
        on_audio: Optional[Callable] = None,
        on_text: Optional[Callable] = None,
        on_turn_complete: Optional[Callable] = None,
    ) -> LiveSession:
        """Create a new tutoring session."""
        session_id = str(uuid.uuid4())
        session = LiveSession(
            session_id=session_id,
            on_audio=on_audio,
            on_text=on_text,
            on_turn_complete=on_turn_complete,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[LiveSession]:
        """Retrieve an existing session."""
        return self._sessions.get(session_id)

    async def remove_session(self, session_id: str) -> None:
        """Disconnect and remove a session."""
        session = self._sessions.pop(session_id, None)
        if session:
            await session.disconnect()

    async def cleanup_all(self) -> None:
        """Disconnect all sessions (for shutdown)."""
        for session_id in list(self._sessions.keys()):
            await self.remove_session(session_id)

    @property
    def active_count(self) -> int:
        return len(self._sessions)


# Global session manager
session_manager = SessionManager()
