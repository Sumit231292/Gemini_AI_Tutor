"""
EduNova Pitch Deck — Video Generator
=========================================
Generates a 5-minute pitch video from the HTML presentation with:
  - Automated slide screenshots via Playwright
  - Text-to-speech narration (gTTS or pyttsx3)
  - Background music & sound effects
  - Smooth transitions between slides

Usage:
    pip install playwright moviepy gTTS Pillow numpy
    playwright install chromium
    python create_video.py

Output: pitch_video.mp4
"""

import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------

PRESENTATION_FILE = Path(__file__).parent / "presentation.html"
OUTPUT_VIDEO = Path(__file__).parent / "pitch_video.mp4"
TEMP_DIR = Path(tempfile.mkdtemp(prefix="edunova_pitch_"))
SLIDE_WIDTH = 1920
SLIDE_HEIGHT = 1080
FPS = 24

# Narration scripts for each slide (edit these to match your pitch!)
NARRATION = [
    # Slide 1 — Intro (30 seconds)
    (
        "Hello everyone! Welcome to our pitch for EduNova — "
        "an AI tutor that sees and speaks. "
        "I'm Sumit Awate, and I built this project for the Gemini Live Agent Challenge. "
        "Let me show you what we've created."
    ),
    # Slide 2 — Problem Statement (30 seconds)
    (
        "The problem is huge. Over 1.5 billion students worldwide lack access to quality, "
        "personalized tutoring. Private tutors cost 50 to 100 dollars per hour, "
        "which is out of reach for most families. And 90 percent of existing AI tutors "
        "are text-only — no voice, no vision, no real interaction."
    ),
    # Slide 3 — Impact (30 seconds)
    (
        "EduNova can change this. It democratizes education by providing free, "
        "24/7 AI tutoring in over 20 languages. It showcases the full power of Google's "
        "Gemini 2.5 Flash with native audio and vision capabilities. Students learn deeper through "
        "guided, step-by-step explanations, and it's fully cloud-native and scalable on Google Cloud."
    ),
    # Slide 4 — Product (60 seconds)
    (
        "Here's our product. EduNova lets you talk to your tutor, show your homework, "
        "and get guided to the answer — in your own language, in real time. "
        "Our three key features are: First, real-time voice — natural, interruptible "
        "conversation powered by Gemini 2.5 Flash native audio model. Second, vision-enabled — point your "
        "camera at homework and the Gemini 2.5 Flash vision model analyzes it instantly. "
        "Third, guided learning — the tutor explains concepts step by step, "
        "walks you through the solution, and gives you the final answer."
    ),
    # Slide 5 — Demo (120 seconds)
    (
        "Let me walk you through the user journey. A student signs up with their profile — "
        "name, grade, and preferred language. Then they pick a subject like Mathematics or Physics. "
        "They click the microphone button and start asking questions using their voice. "
        "They can also point their camera at homework, and the tutor analyzes the image in real time. "
        "The tutor then walks them through the solution step by step with clear explanations. "
        "Under the hood, the browser captures audio and video, sends it via WebSocket to our "
        "FastAPI backend running on Cloud Run. The backend uses Google's ADK Agent framework "
        "with specialized tools for practice problems, concept explanations, and study plans. "
        "It uses Gemini 2.5 Flash native audio model for real-time voice via the Live API, "
        "and Gemini 2.5 Flash vision model for image analysis — a hybrid approach that combines "
        "the best of both models. "
        "The entire infrastructure is defined in Terraform and deployed with Cloud Build."
    ),
    # Slide 6 — Wrap Up (30 seconds)
    (
        "To wrap up — EduNova has massive market fit with over 1.5 billion students in need. "
        "Our unique selling point is the only AI tutor with real-time voice, camera vision, "
        "and guided step-by-step learning combined. It uses Gemini 2.5 Flash for both "
        "native audio and vision in a production-ready application. "
        "Thank you for watching! We'd love to hear your questions."
    ),
]

# Slide durations in seconds (should match narration length roughly)
SLIDE_DURATIONS = [8, 8, 8, 14, 25, 8]  # Will be auto-adjusted to narration length


def check_dependencies():
    """Check and report missing dependencies."""
    missing = []
    try:
        import playwright
    except ImportError:
        missing.append("playwright")
    try:
        from moviepy import ImageClip
    except ImportError:
        missing.append("moviepy")
    try:
        from gtts import gTTS
    except ImportError:
        missing.append("gTTS")
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")
    try:
        import numpy
    except ImportError:
        missing.append("numpy")

    if missing:
        print("=" * 60)
        print("Missing dependencies. Install them with:")
        print(f"  pip install {' '.join(missing)}")
        if "playwright" in missing:
            print("  playwright install chromium")
        print("=" * 60)
        sys.exit(1)


def capture_slides():
    """Use Playwright to screenshot each slide from the HTML presentation."""
    from playwright.sync_api import sync_playwright

    print("\n📸 Capturing slides...")
    slide_images = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": SLIDE_WIDTH, "height": SLIDE_HEIGHT})

        # Load the presentation
        file_url = PRESENTATION_FILE.resolve().as_uri()
        page.goto(file_url)
        page.wait_for_timeout(2000)  # Wait for animations

        # Count slides
        total_slides = page.evaluate("document.querySelectorAll('.slide').length")
        print(f"   Found {total_slides} slides")

        for i in range(total_slides):
            # Navigate to slide
            page.evaluate(f"""
                document.querySelectorAll('.slide').forEach((s, idx) => {{
                    s.classList.remove('active', 'exit-left');
                    if (idx === {i}) s.classList.add('active');
                }});
            """)
            page.wait_for_timeout(800)  # Wait for transition animation

            # Hide navigation bar for clean screenshot
            page.evaluate("document.querySelector('.nav-bar').style.display = 'none'")

            # Screenshot
            img_path = TEMP_DIR / f"slide_{i}.png"
            page.screenshot(path=str(img_path))
            slide_images.append(img_path)
            print(f"   ✅ Slide {i + 1}/{total_slides} captured")

        browser.close()

    return slide_images


def generate_narration():
    """Generate TTS audio for each slide's narration."""
    from gtts import gTTS
    from moviepy import AudioFileClip

    print("\n🎙️  Generating narration...")
    audio_files = []
    durations = []

    for i, text in enumerate(NARRATION):
        audio_path = TEMP_DIR / f"narration_{i}.mp3"
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(str(audio_path))

        # Get actual duration
        clip = AudioFileClip(str(audio_path))
        dur = clip.duration
        clip.close()

        audio_files.append(audio_path)
        durations.append(dur + 1.5)  # Add 1.5s padding
        print(f"   ✅ Slide {i + 1} narration: {dur:.1f}s")

    return audio_files, durations


def generate_sound_effects():
    """Generate simple sound effects using numpy (no external files needed)."""
    import numpy as np
    from scipy.io import wavfile

    print("\n🔊 Generating sound effects...")
    effects = {}
    sample_rate = 44100

    # --- Transition whoosh ---
    duration = 0.4
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    freq = np.linspace(800, 200, len(t))
    whoosh = np.sin(2 * np.pi * freq * t) * np.exp(-3 * t) * 0.3
    # Add noise for whoosh texture
    noise = np.random.randn(len(t)).astype(np.float32) * 0.05 * np.exp(-5 * t)
    whoosh = (whoosh + noise).astype(np.float32)
    path = TEMP_DIR / "whoosh.wav"
    wavfile.write(str(path), sample_rate, whoosh)
    effects["whoosh"] = path

    # --- Intro chime ---
    duration = 1.2
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    chime = (
        np.sin(2 * np.pi * 523 * t) * 0.3 +  # C5
        np.sin(2 * np.pi * 659 * t) * 0.2 +  # E5
        np.sin(2 * np.pi * 784 * t) * 0.15    # G5
    ) * np.exp(-2 * t)
    chime = chime.astype(np.float32)
    path = TEMP_DIR / "chime.wav"
    wavfile.write(str(path), sample_rate, chime)
    effects["chime"] = path

    # --- Outro / success ---
    duration = 1.5
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    outro = (
        np.sin(2 * np.pi * 440 * t) * 0.2 +
        np.sin(2 * np.pi * 554 * t) * 0.15 +
        np.sin(2 * np.pi * 659 * t) * 0.15 +
        np.sin(2 * np.pi * 880 * t) * 0.1
    ) * np.exp(-1.5 * t)
    outro = outro.astype(np.float32)
    path = TEMP_DIR / "outro.wav"
    wavfile.write(str(path), sample_rate, outro)
    effects["outro"] = path

    print("   ✅ Whoosh, chime, and outro sounds generated")
    return effects


def create_video(slide_images, audio_files, durations, effects):
    """Compose everything into a final video."""
    from moviepy import (
        ImageClip, AudioFileClip, CompositeAudioClip,
        concatenate_videoclips, vfx
    )

    print("\n🎬 Composing video...")
    video_clips = []
    all_audio = []
    current_time = 0

    for i, (img_path, audio_path, dur) in enumerate(zip(slide_images, audio_files, durations)):
        print(f"   Processing slide {i + 1}...")

        # Image clip with duration
        img_clip = (
            ImageClip(str(img_path))
            .with_duration(dur)
            .resized((SLIDE_WIDTH, SLIDE_HEIGHT))
        )

        # Fade in/out
        img_clip = img_clip.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
        video_clips.append(img_clip)

        # Narration audio
        narration = AudioFileClip(str(audio_path))
        # Start narration 0.8s into the slide (after transition)
        all_audio.append(narration.with_start(current_time + 0.8))

        # Transition whoosh sound (except for first slide)
        if i > 0:
            whoosh = AudioFileClip(str(effects["whoosh"]))
            all_audio.append(whoosh.with_start(current_time))

        # Chime on first slide
        if i == 0:
            chime = AudioFileClip(str(effects["chime"]))
            all_audio.append(chime.with_start(current_time))

        # Outro on last slide
        if i == len(slide_images) - 1:
            outro = AudioFileClip(str(effects["outro"]))
            all_audio.append(outro.with_start(current_time + dur - 2))

        current_time += dur

    # Concatenate video clips (use "chain" to avoid Pillow composite issues)
    final_video = concatenate_videoclips(video_clips, method="chain")

    # Mix all audio
    final_audio = CompositeAudioClip(all_audio)
    final_video = final_video.with_audio(final_audio)

    # Write output
    print(f"\n💾 Writing video to {OUTPUT_VIDEO}...")
    final_video.write_videofile(
        str(OUTPUT_VIDEO),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="ultrafast",
        threads=4,
    )

    # Cleanup
    final_video.close()
    for a in all_audio:
        a.close()

    print(f"\n✅ Video saved: {OUTPUT_VIDEO}")
    print(f"   Duration: {current_time:.0f} seconds")


def main():
    check_dependencies()

    print("=" * 60)
    print("🎓 EduNova — Pitch Video Generator")
    print("=" * 60)

    if not PRESENTATION_FILE.exists():
        print(f"❌ Presentation not found: {PRESENTATION_FILE}")
        sys.exit(1)

    # Step 1: Capture slide screenshots
    slide_images = capture_slides()

    # Step 2: Generate narration audio
    audio_files, durations = generate_narration()

    # Step 3: Generate sound effects
    effects = generate_sound_effects()

    # Step 4: Compose final video
    create_video(slide_images, audio_files, durations, effects)

    # Cleanup temp files after video is fully written
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        print("🧹 Temp files cleaned up")


if __name__ == "__main__":
    main()
