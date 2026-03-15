# 🎓 EduNova — AI Tutor That Sees & Speaks

> **Real-time, vision-enabled AI tutor** powered by Google Gemini Live API.  
> Talk naturally, show your homework, and get step-by-step guidance.
>
> Built for the **Gemini Live Agent Challenge** hackathon — Category: **Live Agents** 🗣️

---

## ✨ Features

| Feature | Description |
|---|---|
| 🗣️ **Real-time Voice** | Natural conversation with your tutor — speak and get spoken responses via Gemini Live API (native audio) |
| 📸 **Vision-Enabled** | Show your homework via camera or upload an image — analyzed by Gemini 2.5 Flash vision model |
| 🧠 **Balanced Teaching** | Guides you to understand concepts, then provides complete solutions with step-by-step explanations |
| ⚡ **Interruptible** | Break in at any time — the tutor handles interruptions gracefully |
| 🌐 **Language Selection** | Choose from 20+ languages (English, Hindi, Spanish, French, etc.) — the tutor responds in your preferred language |
| 📚 **Multi-Subject** | Mathematics, Physics, Chemistry, Biology, CS, Language Arts, History |
| 🛠️ **ADK Agent Tools** | Structured tools for practice problems, concept explanations, study plans |
| � **User Authentication** | Sign up / log in with username & password — passwords hashed with SHA-256 + salt |
| 👤 **Student Profiles** | Name, grade, gender, age, language — persisted to Google Cloud Firestore |
| ☁️ **Google Cloud** | Deployed on Cloud Run with Terraform IaC, user data stored in Firestore |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐ │
│  │ Mic/Audio│  │  Camera  │  │   Chat UI / Controls  │ │
│  └────┬─────┘  └────┬─────┘  └──────────┬────────────┘ │
│       │              │                    │              │
│       └──────────────┼────────────────────┘              │
│                      │ WebSocket (wss://)                │
└──────────────────────┼──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│              Google Cloud Run                            │
│  ┌───────────────────┴───────────────────────────────┐  │
│  │            FastAPI + WebSocket Server              │  │
│  │  ┌─────────────┐    ┌──────────────────────────┐  │  │
│  │  │ Session Mgr │    │   ADK Tutor Agent         │  │  │
│  │  │ (Live API   │    │  ┌────────────────────┐  │  │  │
│  │  │  sessions)  │    │  │ Tools:             │  │  │  │
│  │  │             │    │  │ • Practice Probs   │  │  │  │
│  │  │             │    │  │ • Concept Explain  │  │  │  │
│  │  │             │    │  │ • Check Solution   │  │  │  │
│  │  │             │    │  │ • Study Plan       │  │  │  │
│  │  │             │    │  │ • Step-by-Step     │  │  │  │
│  │  └──────┬──────┘    │  └────────────────────┘  │  │  │
│  │         │           └──────────────────────────┘  │  │
│  └─────────┼─────────────────────────────────────────┘  │
│            │                                             │
└────────────┼─────────────────────────────────────────────┘
             │ Bidirectional Streaming
┌────────────┼─────────────────────────────────────────────┐
│            ▼                                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Gemini 2.5 Flash (Native Audio + Vision)  │   │
│  │  • Real-time audio input/output (native audio)   │   │
│  │  • Image/vision understanding (2.5 Flash vision) │   │
│  │  • Hybrid: voice via Live API, vision via API    │   │
│  │  • Interruption handling                         │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│                 Google AI Platform                        │
└──────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **AI Models** | Gemini 2.5 Flash Native Audio (Live API — voice) + Gemini 2.5 Flash (vision/image analysis) |
| **Agent Framework** | Google ADK (Agent Development Kit) |
| **SDK** | Google GenAI SDK (`google-genai` v1.x) |
| **Backend** | Python 3.12, FastAPI, uvicorn, WebSockets |
| **Database** | Google Cloud Firestore (user profiles & session data) |
| **Frontend** | Vanilla HTML/CSS/JS (no build step) |
| **Google Cloud** | Cloud Run, Vertex AI, Cloud Build, Firestore |
| **IaC** | Terraform + Cloud Build YAML |
| **Containerization** | Docker (multi-stage build) |

---

## 🚀 Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- A [Google AI API Key](https://aistudio.google.com/apikey) **or** a Google Cloud project with Vertex AI enabled
- Microphone + Camera (for full experience)

### 1. Clone the Repository

```bash
git clone https://github.com/Sumit231292/Gemini_AI_Tutor.git
cd Gemini_AI_Tutor
```

### 2. Set Up Environment

```bash
# Create and activate virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Configure API Key

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your API key
GOOGLE_API_KEY=your-api-key-here

# Set your GCP project for Firestore (user storage)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```

### 3b. Set Up Firestore (for persistent user storage)

```bash
# Authenticate with GCP
gcloud auth application-default login --project YOUR_PROJECT_ID

# Create Firestore database (one-time)
gcloud firestore databases create --project=YOUR_PROJECT_ID --location=nam5 --type=firestore-native
```

> Without Firestore, the app automatically falls back to a local JSON file (`backend/data/users.json`).

### 4. Run the Server

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Open in Browser

Navigate to **http://localhost:8000** — select a subject and start learning!

> **Note**: For microphone/camera access, use `localhost` or HTTPS. Browsers block media APIs on non-secure origins.

---

## ☁️ Deploy to Google Cloud

### Option A: One-Command Deploy Script

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy
chmod +x deploy/deploy.sh
./deploy/deploy.sh YOUR_PROJECT_ID us-central1
```

### Option B: Cloud Build (CI/CD)

```bash
# Trigger a build from the repo root
gcloud builds submit \
    --config deploy/cloudbuild.yaml \
    --project YOUR_PROJECT_ID \
    --substitutions _REGION=us-central1
```

### Option C: Terraform (IaC — Bonus Points!)

```bash
cd deploy

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan -var="project_id=YOUR_PROJECT_ID"

# Apply
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

After deployment, set your API key:

```bash
gcloud run services update edunova \
    --region us-central1 \
    --set-env-vars GOOGLE_API_KEY=your-api-key
```

---

## 📁 Project Structure

```
edunova/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Package init
│   │   ├── config.py            # Environment configuration
│   │   ├── main.py              # FastAPI server + WebSocket endpoints
│   │   ├── live_api.py          # Gemini Live API session manager
│   │   └── tutor_agent.py       # ADK agent with tutoring tools
│   ├── requirements.txt         # Python dependencies
│   └── Dockerfile               # Container for Cloud Run
├── frontend/
│   ├── index.html               # Main UI
│   ├── style.css                # Styling (glass-morphism design)
│   └── app.js                   # Client-side logic
├── deploy/
│   ├── deploy.sh                # One-click deploy script
│   ├── cloudbuild.yaml          # Cloud Build CI/CD config
│   └── main.tf                  # Terraform IaC config
├── .env.example                 # Environment template
├── .gitignore
└── README.md                    # This file
```

---

## 🎮 How to Use

1. **Create an account** — sign up with a username, password, name, grade, and preferred language
2. **Log in** — returning users log in with username and password
3. **Select a subject** from the landing page
4. **Talk to your tutor** — click the mic button and speak naturally
5. **Show your homework** — use the camera button to capture a photo, or upload an image
6. **Type messages** — use the text input for typed questions
7. **Change language** — switch language anytime from the landing page
8. **Get guided** — the tutor explains concepts step-by-step and gives you the final answer
9. **Interrupt anytime** — the tutor handles interruptions gracefully
10. **Log out** — click the logout button to switch accounts

---

## 🔑 Key Hackathon Requirements Checklist

| Requirement | Status | Details |
|---|---|---|
| ✅ Gemini model | ✔️ | Gemini 2.5 Flash Native Audio (Live API) + Gemini 2.5 Flash (vision) |
| ✅ Google GenAI SDK or ADK | ✔️ | Both — GenAI SDK for Live API + ADK for agent tools |
| ✅ Google Cloud service | ✔️ | Cloud Run, Vertex AI, Cloud Build, Firestore |
| ✅ Multimodal input | ✔️ | Voice (audio) + Vision (camera/image) + Text |
| ✅ Beyond text-in/text-out | ✔️ | Real-time voice conversation + image understanding |
| ✅ Multi-language | ✔️ | 20+ languages with per-session language selection |
| ✅ User persistence | ✔️ | Student profiles stored in Google Cloud Firestore |
| ✅ Live Agent category | ✔️ | Real-time interruptible voice + vision tutor |
| ✅ Public code repo | ✔️ | This repository |
| ✅ Spin-up instructions | ✔️ | See Quick Start above |
| ✅ Architecture diagram | ✔️ | See Architecture section |
| ✅ IaC deployment (bonus) | ✔️ | Terraform + Cloud Build |

---

## 📝 Findings & Learnings

### What Worked Well
- **Gemini Live API** with native audio model provides remarkably natural real-time conversations with low latency
- **Hybrid vision approach** — using Gemini 2.5 Flash for image analysis and feeding results into the native audio session creates a seamless "sees and speaks" experience
- **Vision + Voice combo** creates a powerful tutoring experience — students can literally "show" their homework
- **Balanced teaching approach** combines guided learning with actual answers — the tutor explains step-by-step AND gives the final answer
- **ADK tools** provide structured capabilities (practice problems, study plans) beyond free-form conversation
- **Language selection** ensures the tutor always responds in the student's preferred language
- **Firestore integration** provides durable, serverless storage for student profiles across sessions

### Challenges
- **Native audio model limitations** — the `gemini-2.5-flash-native-audio-latest` model doesn't support direct image input, requiring a hybrid approach with a separate vision model call
- **Audio format handling** — bridging browser MediaRecorder PCM format to Gemini's expected input required careful sample rate and encoding management
- **WebSocket lifecycle** — managing the bidirectional bridge between client WebSocket and Gemini Live API session required careful async handling
- **Interruption handling** — ensuring smooth interruption UX when the student speaks while the tutor is responding

### Future Ideas
- Real-time whiteboard/drawing for working through math problems visually
- Progress tracking across sessions with Firestore persistence
- Integration with curriculum standards (Common Core, etc.)
- Google OAuth as alternative login method
- Support for more Gemini model variants as they become available

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ using Google Gemini Live API · ADK · Google Cloud<br>
  <strong>#GeminiLiveAgentChallenge</strong>
</p>
