"""
FastAPI server for EduNova.
Handles WebSocket connections for real-time voice/vision tutoring
and REST endpoints for image analysis and session management.
"""

import asyncio
import base64
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Load environment variables (look in backend/, project root, and Gemini_AI_Tutor/)
_env_path = Path(__file__).parent.parent / ".env"
if not _env_path.exists():
    _env_path = Path(__file__).parent.parent.parent / ".env"
if not _env_path.exists():
    _env_path = Path(__file__).parent.parent.parent / "Gemini_AI_Tutor" / ".env"
load_dotenv(_env_path)

from .config import settings
from .live_api import LiveSession, session_manager
from .tutor_agent import analyze_image_with_agent, create_tutor_agent
from .user_store import save_user, get_user, get_all_users, login_user

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🎓 EduNova starting up...")
    try:
        settings.validate()
        logger.info("✅ Configuration validated")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")

    yield

    # Shutdown: clean up all sessions
    logger.info("🔄 Shutting down, cleaning up sessions...")
    await session_manager.cleanup_all()
    logger.info("👋 EduNova stopped")


app = FastAPI(
    title="EduNova",
    description="AI-powered tutor using Gemini Live API for real-time voice and vision tutoring",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
if not FRONTEND_DIR.exists():
    # Alternative path when project has subfolder structure
    FRONTEND_DIR = Path(__file__).parent.parent.parent / "Gemini_AI_Tutor" / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main frontend page."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>EduNova API</h1><p>Frontend not found. Place files in /frontend directory.</p>"
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {
        "status": "healthy",
        "service": "edunova",
        "active_sessions": session_manager.active_count,
    }


@app.get("/api/config")
async def get_client_config():
    """Return non-sensitive configuration for the frontend."""
    return {
        "audio_sample_rate": settings.audio_sample_rate,
        "audio_channels": settings.audio_channels,
        "max_session_duration": settings.max_session_duration,
        "supported_subjects": [
            {"id": "mathematics", "name": "Mathematics", "icon": "📐"},
            {"id": "physics", "name": "Physics", "icon": "⚛️"},
            {"id": "chemistry", "name": "Chemistry", "icon": "🧪"},
            {"id": "biology", "name": "Biology", "icon": "🧬"},
            {"id": "computer_science", "name": "Computer Science", "icon": "💻"},
            {"id": "language_arts", "name": "Language Arts", "icon": "📝"},
            {"id": "history", "name": "History", "icon": "📜"},
            {"id": "general", "name": "General", "icon": "📚"},
        ],
    }


@app.post("/api/analyze-image")
async def analyze_image(request: dict):
    """Analyze an uploaded image using the vision model.
    
    Expected body:
    {
        "image": "base64-encoded-image-data",
        "mime_type": "image/jpeg",
        "question": "optional question about the image"
    }
    """
    image_data = request.get("image")
    if not image_data:
        raise HTTPException(status_code=400, detail="No image data provided")

    mime_type = request.get("mime_type", "image/jpeg")
    question = request.get(
        "question",
        "Analyze this homework/study material and help me understand it.",
    )

    result = await analyze_image_with_agent(image_data, mime_type, question)
    return {"analysis": result}


@app.post("/api/register")
async def register_user(profile: dict):
    """Register a new student profile.

    Expected body:
    {
        "username": "alice123",
        "password": "secret",
        "name": "Alice",
        "gender": "girl",
        "grade": "10",
        "age": 15,
        "language": "en"
    }
    """
    name = profile.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    try:
        record = save_user(profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"user": record}


@app.post("/api/login")
async def login(credentials: dict):
    """Log in with username and password.

    Expected body:
    {
        "username": "alice123",
        "password": "secret"
    }
    """
    username = credentials.get("username", "").strip()
    password = credentials.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    user = login_user(username, password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return {"user": user}


@app.get("/api/users")
async def list_users():
    """List all registered users (admin / demo)."""
    return {"users": get_all_users()}


# ---------------------------------------------------------------------------
# WebSocket Endpoint for Live Tutoring
# ---------------------------------------------------------------------------

@app.websocket("/ws/tutor")
async def websocket_tutor(websocket: WebSocket):
    """WebSocket endpoint for real-time voice/vision tutoring.
    
    Protocol:
    Client sends JSON messages:
    - {"type": "start", "subject": "mathematics"}  → Start a new session
    - {"type": "audio", "data": "base64..."}        → Send audio chunk
    - {"type": "image", "data": "base64...", "mime_type": "image/jpeg"} → Send image
    - {"type": "text", "data": "hello"}             → Send text message
    - {"type": "stop"}                               → End session
    
    Server sends JSON messages:
    - {"type": "session_started", "session_id": "..."}
    - {"type": "audio", "data": "base64..."}         → Audio response chunk
    - {"type": "text", "data": "Hello!"}             → Text response
    - {"type": "turn_complete"}                       → Model finished speaking
    - {"type": "error", "message": "..."}            → Error
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    session: LiveSession = None
    
    try:
        while True:
            # Receive message from client
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = message.get("type")

            # ── START SESSION ──
            if msg_type == "start":
                subject = message.get("subject", "general")
                language = message.get("language", "en")

                # Create callbacks that send data back over WebSocket
                async def on_audio(data: str):
                    try:
                        await websocket.send_json({"type": "audio", "data": data})
                    except Exception:
                        pass

                async def on_text(data: str):
                    try:
                        await websocket.send_json({"type": "text", "data": data})
                    except Exception:
                        pass

                async def on_turn_complete():
                    try:
                        await websocket.send_json({"type": "turn_complete"})
                    except Exception:
                        pass

                # Create and connect session
                session = session_manager.create_session(
                    on_audio=on_audio,
                    on_text=on_text,
                    on_turn_complete=on_turn_complete,
                )

                try:
                    await session.connect(subject=subject, language=language)
                    await websocket.send_json({
                        "type": "session_started",
                        "session_id": session.session_id,
                    })
                    logger.info(f"Session started: {session.session_id}")
                except Exception as e:
                    logger.error(f"Failed to start session: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to connect to Gemini: {str(e)}",
                    })
                    session = None

            # ── SEND AUDIO ──
            elif msg_type == "audio" and session:
                audio_data = message.get("data", "")
                if audio_data:
                    logger.debug(f"Sending audio chunk: {len(audio_data)} chars")
                    await session.send_audio(audio_data)

            # ── SEND IMAGE ──
            elif msg_type == "image" and session:
                image_data = message.get("data", "")
                mime_type = message.get("mime_type", "image/jpeg")
                if image_data:
                    # Vision analysis is handled inside send_image
                    # (uses vision model + feeds result to live session)
                    await session.send_image(image_data, mime_type)

            # ── SEND TEXT ──
            elif msg_type == "text" and session:
                text_data = message.get("data", "")
                if text_data:
                    logger.info(f"Sending text: {text_data[:100]}")
                    await session.send_text(text_data)

            # ── STOP SESSION ──
            elif msg_type == "stop":
                if session:
                    await session_manager.remove_session(session.session_id)
                    session = None
                await websocket.send_json({"type": "session_ended"})
                break

            elif not session and msg_type in ("audio", "image", "text"):
                await websocket.send_json({
                    "type": "error",
                    "message": "No active session. Send {\"type\": \"start\"} first.",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up session on disconnect
        if session:
            await session_manager.remove_session(session.session_id)
        logger.info("WebSocket connection closed")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the server."""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    main()
