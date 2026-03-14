/* ================================================================
   EduNova - Main Application Script
   Handles WebSocket communication, audio/video capture, and UI
   ================================================================ */

(() => {
    "use strict";

    // ── State ───────────────────────────────────────────────────
    const state = {
        ws: null,
        sessionId: null,
        selectedSubject: null,
        isConnected: false,
        isRecording: false,
        audioContext: null,
        mediaStream: null,
        mediaRecorder: null,
        audioWorklet: null,
        cameraStream: null,
        capturedImageData: null,
        timerInterval: null,
        sessionSeconds: 0,
        audioQueue: [],
        isPlayingAudio: false,
        currentTutorMessage: "",
        // New state for speech recognition & indicators
        speechRecognition: null,
        currentSpeechBubble: null,
        currentSpeechText: "",
        audioChunksSent: 0,
        userProfile: null,
    };

    // ── DOM Elements ────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const els = {
        // Screens
        signin: $("#signin"),
        landing: $("#landing"),
        session: $("#session"),

        // Sign-in / Sign-up
        signinForm: $("#signinForm"),
        loginForm: $("#loginForm"),
        inputUsername: $("#inputUsername"),
        inputPassword: $("#inputPassword"),
        loginUsername: $("#loginUsername"),
        loginPassword: $("#loginPassword"),
        inputName: $("#inputName"),
        inputGrade: $("#inputGrade"),
        inputAge: $("#inputAge"),
        inputLanguage: $("#inputLanguage"),
        authTabs: $$("#signin .auth-tab"),
        btnLogout: $("#btnLogout"),

        // Subject
        subjectGrid: $("#subjectGrid"),
        sessionLanguage: $("#sessionLanguage"),

        // Session header
        sessionSubject: $("#sessionSubject"),
        sessionStatus: $("#sessionStatus"),
        sessionTimer: $("#sessionTimer"),
        btnBack: $("#btnBack"),

        // Chat
        chatArea: $("#chatArea"),
        chatMessages: $("#chatMessages"),

        // Controls
        btnMic: $("#btnMic"),
        btnCamera: $("#btnCamera"),
        btnUpload: $("#btnUpload"),
        btnEndSession: $("#btnEndSession"),
        textInput: $("#textInput"),
        btnSendText: $("#btnSendText"),

        // Camera
        cameraPreview: $("#cameraPreview"),
        cameraVideo: $("#cameraVideo"),
        btnCapture: $("#btnCapture"),
        btnCloseCamera: $("#btnCloseCamera"),
        captureCanvas: $("#captureCanvas"),

        // Image preview
        imagePreview: $("#imagePreview"),
        previewImage: $("#previewImage"),
        btnSendImage: $("#btnSendImage"),
        btnDiscardImage: $("#btnDiscardImage"),

        // File upload
        fileInput: $("#fileInput"),

        // Toast
        toastContainer: $("#toastContainer"),
    };

    // ── Initialization ──────────────────────────────────────────
    function init() {
        // Check for existing profile in localStorage
        const saved = localStorage.getItem("edunova_profile");
        if (saved) {
            try {
                state.userProfile = JSON.parse(saved);
                applyTheme(state.userProfile.gender);
                showLandingWithGreeting();
            } catch (_) {
                showScreen("signin");
            }
        }

        // Sign-in form (sign-up)
        if (els.signinForm) {
            els.signinForm.addEventListener("submit", handleSignUp);
        }

        // Login form
        if (els.loginForm) {
            els.loginForm.addEventListener("submit", handleLogin);
        }

        // Auth tab switching
        els.authTabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                els.authTabs.forEach((t) => t.classList.remove("active"));
                tab.classList.add("active");
                const mode = tab.dataset.tab;
                if (mode === "login") {
                    els.loginForm.style.display = "";
                    els.signinForm.style.display = "none";
                } else {
                    els.loginForm.style.display = "none";
                    els.signinForm.style.display = "";
                }
            });
        });

        // Logout
        if (els.btnLogout) {
            els.btnLogout.addEventListener("click", handleLogout);
        }

        // Subject selection
        els.subjectGrid.addEventListener("click", (e) => {
            const card = e.target.closest(".subject-card");
            if (card) {
                const subject = card.dataset.subject;
                startSession(subject);
            }
        });

        // Session controls
        els.btnBack.addEventListener("click", endSession);
        els.btnEndSession.addEventListener("click", endSession);

        // Language selector on landing page
        if (els.sessionLanguage) {
            els.sessionLanguage.addEventListener("change", () => {
                if (state.userProfile) {
                    state.userProfile.language = els.sessionLanguage.value;
                    localStorage.setItem("edunova_profile", JSON.stringify(state.userProfile));
                }
            });
        }

        // Mic: click to toggle (not hold)
        els.btnMic.addEventListener("click", toggleRecording);

        els.btnCamera.addEventListener("click", toggleCamera);
        els.btnUpload.addEventListener("click", () => els.fileInput.click());
        els.fileInput.addEventListener("change", handleFileUpload);

        // Camera controls
        els.btnCapture.addEventListener("click", captureImage);
        els.btnCloseCamera.addEventListener("click", closeCamera);

        // Image preview
        els.btnSendImage.addEventListener("click", sendCapturedImage);
        els.btnDiscardImage.addEventListener("click", discardImage);

        // Text input
        els.btnSendText.addEventListener("click", sendTextMessage);
        els.textInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendTextMessage();
            }
        });

        console.log("EduNova initialized");
    }

    // ── Sign-Up ─────────────────────────────────────────────────
    async function handleSignUp(e) {
        e.preventDefault();

        const genderRadio = document.querySelector('input[name="gender"]:checked');
        if (!genderRadio) {
            showToast("Please select your gender.", "error");
            return;
        }

        const username = els.inputUsername.value.trim();
        const password = els.inputPassword.value;

        if (!username || username.length < 3) {
            showToast("Username must be at least 3 characters.", "error");
            return;
        }
        if (!password || password.length < 6) {
            showToast("Password must be at least 6 characters.", "error");
            return;
        }

        const profile = {
            username: username,
            password: password,
            name: els.inputName.value.trim(),
            gender: genderRadio.value,
            grade: els.inputGrade.value,
            age: parseInt(els.inputAge.value, 10) || 0,
            language: els.inputLanguage.value || "en",
        };

        if (!profile.name) {
            showToast("Please enter your name.", "error");
            return;
        }

        // Register on backend
        try {
            const res = await fetch("/api/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(profile),
            });
            const data = await res.json();
            if (!res.ok) {
                showToast(data.detail || "Registration failed.", "error");
                return;
            }
            profile.id = data.user?.id;
        } catch (_) {
            showToast("Server unreachable. Please try again.", "error");
            return;
        }

        // Don't store password locally
        const localProfile = { ...profile };
        delete localProfile.password;
        state.userProfile = localProfile;
        localStorage.setItem("edunova_profile", JSON.stringify(localProfile));

        applyTheme(profile.gender);
        showToast(`Account created! Welcome, ${profile.name}!`, "success");
        showLandingWithGreeting();
    }

    // ── Log-In ──────────────────────────────────────────────────
    async function handleLogin(e) {
        e.preventDefault();

        const username = els.loginUsername.value.trim();
        const password = els.loginPassword.value;

        if (!username || !password) {
            showToast("Please enter username and password.", "error");
            return;
        }

        try {
            const res = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });
            const data = await res.json();
            if (!res.ok) {
                showToast(data.detail || "Invalid username or password.", "error");
                return;
            }

            const profile = data.user;
            state.userProfile = profile;
            localStorage.setItem("edunova_profile", JSON.stringify(profile));

            applyTheme(profile.gender);
            showToast(`Welcome back, ${profile.name}!`, "success");
            showLandingWithGreeting();
        } catch (_) {
            showToast("Server unreachable. Please try again.", "error");
        }
    }

    // ── Logout ───────────────────────────────────────────────────
    function handleLogout() {
        state.userProfile = null;
        localStorage.removeItem("edunova_profile");
        document.body.classList.remove("theme-pink", "theme-blue");
        showScreen("signin");
        showToast("Logged out.", "success");
    }

    function applyTheme(gender) {
        document.body.classList.remove("theme-pink", "theme-blue");
        if (gender === "girl") {
            document.body.classList.add("theme-pink");
        } else {
            document.body.classList.add("theme-blue");
        }
    }

    function showLandingWithGreeting() {
        showScreen("landing");
        // Sync language selector with profile
        if (state.userProfile && state.userProfile.language && els.sessionLanguage) {
            els.sessionLanguage.value = state.userProfile.language;
        }
        // Add welcome greeting if user profile exists
        if (state.userProfile) {
            let greeting = $("#landingGreeting");
            if (!greeting) {
                greeting = document.createElement("p");
                greeting.id = "landingGreeting";
                greeting.className = "welcome-greeting";
                const heroTitle = $(".landing-main .hero-title");
                if (heroTitle) heroTitle.before(greeting);
            }
            greeting.innerHTML = `Hi <span class="user-name">${escapeHtml(state.userProfile.name)}</span>! Choose a subject:`;
        }
    }

    // ── Screen Navigation ───────────────────────────────────────
    function showScreen(screenId) {
        $$(".screen").forEach((s) => s.classList.remove("active"));
        $(`#${screenId}`).classList.add("active");
    }

    // ── WebSocket Management ────────────────────────────────────
    function getWsUrl() {
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        return `${proto}//${location.host}/ws/tutor`;
    }

    function connectWebSocket(subject) {
        return new Promise((resolve, reject) => {
            const wsUrl = getWsUrl();
            console.log("Connecting to", wsUrl);
            state.ws = new WebSocket(wsUrl);

            state.ws.onopen = () => {
                console.log("WebSocket connected");
                // Send start message with language preference
                const lang = (state.userProfile && state.userProfile.language) || "en";
                state.ws.send(JSON.stringify({
                    type: "start",
                    subject: subject,
                    language: lang,
                }));
            };

            state.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    handleServerMessage(msg);

                    if (msg.type === "session_started") {
                        resolve(msg);
                    }
                } catch (e) {
                    console.error("Failed to parse message:", e);
                }
            };

            state.ws.onerror = (error) => {
                console.error("WebSocket error:", error);
                reject(error);
                showToast("Connection error. Please try again.", "error");
            };

            state.ws.onclose = () => {
                console.log("WebSocket closed");
                state.isConnected = false;
                updateStatus("Disconnected", "error");
            };

            // Timeout
            setTimeout(() => {
                if (!state.isConnected) {
                    reject(new Error("Connection timeout"));
                }
            }, 15000);
        });
    }

    function handleServerMessage(msg) {
        switch (msg.type) {
            case "session_started":
                state.sessionId = msg.session_id;
                state.isConnected = true;
                updateStatus("Connected", "connected");
                addSystemMessage("Session started! Speak, type, or show your homework.");
                break;

            case "audio":
                showTutorSpeaking(true);
                removeProcessingIndicator();
                handleAudioResponse(msg.data);
                break;

            case "text":
                removeProcessingIndicator();
                handleTextResponse(msg.data);
                break;

            case "turn_complete":
                handleTurnComplete();
                showTutorSpeaking(false);
                break;

            case "error":
                showToast(msg.message, "error");
                removeProcessingIndicator();
                console.error("Server error:", msg.message);
                break;

            case "session_ended":
                state.isConnected = false;
                updateStatus("Ended", "error");
                break;
        }
    }

    // ── Tutor Speaking Indicator ────────────────────────────────
    function showTutorSpeaking(speaking) {
        if (speaking) {
            updateStatus("Tutor is speaking...", "connected");
        } else if (state.isConnected) {
            updateStatus("Connected", "connected");
        }
    }

    // ── Session Management ──────────────────────────────────────
    async function startSession(subject) {
        state.selectedSubject = subject;
        showScreen("session");

        // Update UI
        const subjectNames = {
            mathematics: "Mathematics",
            physics: "Physics",
            chemistry: "Chemistry",
            biology: "Biology",
            computer_science: "Computer Science",
            language_arts: "Language Arts",
            history: "History",
            general: "General",
        };
        els.sessionSubject.textContent = subjectNames[subject] || subject;
        updateStatus("Connecting...", "");
        els.chatMessages.innerHTML = "";

        // Start timer
        state.sessionSeconds = 0;
        updateTimer();
        state.timerInterval = setInterval(() => {
            state.sessionSeconds++;
            updateTimer();
        }, 1000);

        // Connect WebSocket
        try {
            await connectWebSocket(subject);
            showToast("Connected! Your tutor is ready.", "success");
        } catch (e) {
            showToast("Failed to connect. Please check your connection.", "error");
            updateStatus("Connection failed", "error");
        }
    }

    function endSession() {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type: "stop" }));
            state.ws.close();
        }
        if (state.isRecording) stopRecording();
        stopSpeechRecognition();
        closeCamera();

        if (state.timerInterval) {
            clearInterval(state.timerInterval);
            state.timerInterval = null;
        }
        stopAudioPlayback();

        state.ws = null;
        state.sessionId = null;
        state.isConnected = false;
        state.currentTutorMessage = "";
        state.audioQueue = [];
        state.audioChunksSent = 0;

        showLandingWithGreeting();
    }

    // ── Audio Recording (Toggle) ────────────────────────────────
    function toggleRecording() {
        if (state.isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    }

    async function startRecording() {
        if (state.isRecording || !state.isConnected) return;

        try {
            state.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });

            state.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000,
            });

            const source = state.audioContext.createMediaStreamSource(state.mediaStream);
            const processor = state.audioContext.createScriptProcessor(4096, 1, 1);

            state.audioChunksSent = 0;

            processor.onaudioprocess = (e) => {
                if (!state.isRecording || !state.isConnected) return;

                const inputData = e.inputBuffer.getChannelData(0);
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
                }

                const base64 = arrayBufferToBase64(pcm16.buffer);
                if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                    state.ws.send(JSON.stringify({ type: "audio", data: base64 }));
                    state.audioChunksSent++;
                }
            };

            source.connect(processor);
            processor.connect(state.audioContext.destination);

            state.isRecording = true;
            els.btnMic.classList.add("recording");
            els.btnMic.querySelector(".btn-label").textContent = "Stop";

            addRecordingIndicator();
            startSpeechRecognition();
            updateStatus("Listening...", "connected");

        } catch (e) {
            console.error("Failed to start recording:", e);
            showToast("Microphone access denied. Please allow microphone access.", "error");
        }
    }

    function stopRecording() {
        if (!state.isRecording) return;

        state.isRecording = false;
        els.btnMic.classList.remove("recording");
        els.btnMic.querySelector(".btn-label").textContent = "Talk";

        if (state.mediaStream) {
            state.mediaStream.getTracks().forEach((t) => t.stop());
            state.mediaStream = null;
        }
        if (state.audioContext) {
            state.audioContext.close();
            state.audioContext = null;
        }

        finalizeSpeechBubble();
        stopSpeechRecognition();
        removeRecordingIndicator();

        if (state.isConnected) {
            updateStatus("Connected", "connected");
        }
    }

    // ── Recording Indicator ─────────────────────────────────────
    function addRecordingIndicator() {
        removeRecordingIndicator();
        const div = document.createElement("div");
        div.className = "chat-msg system recording-msg";
        div.innerHTML = `
            <div class="recording-indicator">
                <div class="recording-dot"></div>
                <span class="recording-status">Listening...</span>
            </div>
        `;
        els.chatMessages.appendChild(div);
        scrollToBottom();
    }

    function removeRecordingIndicator() {
        const existing = els.chatMessages.querySelector(".recording-msg");
        if (existing) existing.remove();
    }

    // ── Speech Recognition (Browser) ────────────────────────────
    function startSpeechRecognition() {
        const SpeechRecog = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecog) {
            console.log("SpeechRecognition not supported — audio still sent to Gemini");
            return;
        }

        state.speechRecognition = new SpeechRecog();
        state.speechRecognition.continuous = true;
        state.speechRecognition.interimResults = true;
        // Map language code to BCP-47 for browser SpeechRecognition
        const langMap = {
            en: "en-US", hi: "hi-IN", es: "es-ES", fr: "fr-FR", de: "de-DE",
            ja: "ja-JP", ko: "ko-KR", zh: "zh-CN", pt: "pt-BR", ar: "ar-SA",
            bn: "bn-IN", ta: "ta-IN", te: "te-IN", mr: "mr-IN", gu: "gu-IN",
            kn: "kn-IN", ml: "ml-IN", pa: "pa-IN", ru: "ru-RU", it: "it-IT",
        };
        const userLang = (state.userProfile && state.userProfile.language) || "en";
        state.speechRecognition.lang = langMap[userLang] || "en-US";
        state.currentSpeechText = "";
        state.currentSpeechBubble = null;

        state.speechRecognition.onresult = (event) => {
            let interimTranscript = "";
            let finalTranscript = "";

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }

            if (finalTranscript) {
                state.currentSpeechText += finalTranscript + " ";
            }

            const displayText = (state.currentSpeechText + interimTranscript).trim();
            if (!displayText) return;

            if (!state.currentSpeechBubble || !state.currentSpeechBubble.isConnected) {
                state.currentSpeechBubble = document.createElement("div");
                state.currentSpeechBubble.className = "chat-msg student speech-live";
                state.currentSpeechBubble.innerHTML = `
                    <div class="msg-label">\uD83C\uDFA4 You (speaking)</div>
                    <div class="msg-content"></div>
                `;
                els.chatMessages.appendChild(state.currentSpeechBubble);
            }
            state.currentSpeechBubble.querySelector(".msg-content").textContent = displayText;
            scrollToBottom();
        };

        state.speechRecognition.onerror = (e) => {
            if (e.error !== "aborted") {
                console.log("Speech recognition error:", e.error);
            }
        };

        state.speechRecognition.onend = () => {
            if (state.isRecording && state.speechRecognition) {
                try { state.speechRecognition.start(); } catch (_) {}
            }
        };

        try {
            state.speechRecognition.start();
        } catch (_) {}
    }

    function stopSpeechRecognition() {
        if (state.speechRecognition) {
            try { state.speechRecognition.stop(); } catch (_) {}
            state.speechRecognition = null;
        }
    }

    function finalizeSpeechBubble() {
        if (state.currentSpeechBubble && state.currentSpeechBubble.isConnected) {
            state.currentSpeechBubble.classList.remove("speech-live");
            const label = state.currentSpeechBubble.querySelector(".msg-label");
            if (label) label.textContent = "You (voice)";
            const content = state.currentSpeechBubble.querySelector(".msg-content");
            if (content && !content.textContent.trim()) {
                content.textContent = "(audio sent to tutor)";
            }
        }
        state.currentSpeechBubble = null;
        state.currentSpeechText = "";
    }

    // ── Audio Playback ──────────────────────────────────────────
    // Reuse a single AudioContext and schedule buffers back-to-back
    let playbackCtx = null;
    let nextPlayTime = 0;

    function getPlaybackCtx() {
        if (!playbackCtx || playbackCtx.state === "closed") {
            playbackCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
            nextPlayTime = 0;
        }
        if (playbackCtx.state === "suspended") playbackCtx.resume();
        return playbackCtx;
    }

    function handleAudioResponse(base64Data) {
        try {
            const ctx = getPlaybackCtx();
            const rawData = base64ToArrayBuffer(base64Data);
            const int16 = new Int16Array(rawData);
            if (int16.length === 0) return;

            const float32 = new Float32Array(int16.length);
            for (let i = 0; i < int16.length; i++) {
                float32[i] = int16[i] / 32768.0;
            }

            const buffer = ctx.createBuffer(1, float32.length, 24000);
            buffer.getChannelData(0).set(float32);

            const source = ctx.createBufferSource();
            source.buffer = buffer;
            source.connect(ctx.destination);

            // Schedule seamlessly after the previous chunk
            const now = ctx.currentTime;
            const startAt = Math.max(now, nextPlayTime);
            source.start(startAt);
            nextPlayTime = startAt + buffer.duration;
        } catch (e) {
            console.error("Audio playback error:", e);
        }
    }

    function stopAudioPlayback() {
        state.audioQueue = [];
        state.isPlayingAudio = false;
        if (playbackCtx && playbackCtx.state !== "closed") {
            playbackCtx.close();
            playbackCtx = null;
        }
        nextPlayTime = 0;
    }

    // ── Text Handling ───────────────────────────────────────────
    function cleanThinkingText(text) {
        // Native-audio model may return markdown thinking headers.
        // Clean them for display while keeping useful content.
        return text
            .replace(/^\*\*.*?\*\*\s*/gm, "")   // Remove **bold headers**
            .replace(/^\s*\n/gm, "")              // Remove blank lines
            .trim();
    }

    function handleTextResponse(text) {
        state.currentTutorMessage += text;

        const cleaned = cleanThinkingText(state.currentTutorMessage);
        if (!cleaned) return;

        const lastMsg = els.chatMessages.querySelector(".chat-msg.tutor.streaming");
        if (lastMsg) {
            lastMsg.querySelector(".msg-content").textContent = cleaned;
        } else {
            addTutorMessage(cleaned, true);
        }
        scrollToBottom();
    }

    function handleTurnComplete() {
        const streamingMsg = els.chatMessages.querySelector(".chat-msg.tutor.streaming");
        if (streamingMsg) {
            const cleaned = cleanThinkingText(state.currentTutorMessage);
            if (cleaned) {
                streamingMsg.querySelector(".msg-content").textContent = cleaned;
                streamingMsg.classList.remove("streaming");
                const typing = streamingMsg.querySelector(".typing-indicator");
                if (typing) typing.remove();
            } else {
                streamingMsg.remove();
            }
        }
        state.currentTutorMessage = "";
    }

    function sendTextMessage() {
        const text = els.textInput.value.trim();
        if (!text || !state.isConnected) return;

        addStudentMessage(text);
        els.textInput.value = "";
        addProcessingIndicator();

        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type: "text", data: text }));
        }
    }

    // ── Processing Indicator ────────────────────────────────────
    function addProcessingIndicator() {
        removeProcessingIndicator();
        const div = document.createElement("div");
        div.className = "chat-msg tutor processing-msg";
        div.innerHTML = `
            <div class="msg-label">Tutor</div>
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        `;
        els.chatMessages.appendChild(div);
        scrollToBottom();
    }

    function removeProcessingIndicator() {
        const existing = els.chatMessages.querySelector(".processing-msg");
        if (existing) existing.remove();
    }

    // ── Camera / Image ──────────────────────────────────────────
    async function toggleCamera() {
        if (els.cameraPreview.style.display !== "none") {
            closeCamera();
            return;
        }

        try {
            state.cameraStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: "environment", // Rear camera for homework
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
            });
            els.cameraVideo.srcObject = state.cameraStream;
            els.cameraPreview.style.display = "block";
        } catch (e) {
            console.error("Camera access failed:", e);
            showToast("Camera access denied. Please allow camera access.", "error");
        }
    }

    function closeCamera() {
        if (state.cameraStream) {
            state.cameraStream.getTracks().forEach((t) => t.stop());
            state.cameraStream = null;
        }
        els.cameraVideo.srcObject = null;
        els.cameraPreview.style.display = "none";
    }

    function captureImage() {
        const video = els.cameraVideo;
        const canvas = els.captureCanvas;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0);

        const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
        state.capturedImageData = dataUrl.split(",")[1]; // Base64 part

        // Show preview
        els.previewImage.src = dataUrl;
        els.imagePreview.style.display = "block";

        // Close camera
        closeCamera();
    }

    function handleFileUpload(e) {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (evt) => {
            const dataUrl = evt.target.result;
            state.capturedImageData = dataUrl.split(",")[1];

            els.previewImage.src = dataUrl;
            els.imagePreview.style.display = "block";
        };
        reader.readAsDataURL(file);

        // Reset input
        els.fileInput.value = "";
    }

    function sendCapturedImage() {
        if (!state.capturedImageData || !state.isConnected) return;

        // Add image to chat
        addStudentImageMessage(els.previewImage.src);

        // Send via WebSocket
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({
                type: "image",
                data: state.capturedImageData,
                mime_type: "image/jpeg",
            }));
        }

        discardImage();
        showToast("Image sent! Analyzing...", "success");
        addProcessingIndicator();
    }

    function discardImage() {
        state.capturedImageData = null;
        els.imagePreview.style.display = "none";
        els.previewImage.src = "";
    }

    // ── Chat UI Helpers ─────────────────────────────────────────
    function addTutorMessage(text, streaming = false) {
        const div = document.createElement("div");
        div.className = `chat-msg tutor${streaming ? " streaming" : ""}`;
        div.innerHTML = `
            <div class="msg-label">Tutor</div>
            <div class="msg-content">${escapeHtml(text)}</div>
            ${streaming ? '<div class="typing-indicator"><span></span><span></span><span></span></div>' : ""}
        `;
        els.chatMessages.appendChild(div);
        scrollToBottom();
    }

    function addStudentMessage(text) {
        const div = document.createElement("div");
        div.className = "chat-msg student";
        div.innerHTML = `
            <div class="msg-label">You</div>
            <div class="msg-content">${escapeHtml(text)}</div>
        `;
        els.chatMessages.appendChild(div);
        scrollToBottom();
    }

    function addStudentImageMessage(src) {
        const div = document.createElement("div");
        div.className = "chat-msg student";
        div.innerHTML = `
            <div class="msg-label">You</div>
            <div class="msg-content">Sent an image for analysis</div>
            <img src="${src}" alt="Uploaded homework">
        `;
        els.chatMessages.appendChild(div);
        scrollToBottom();
    }

    function addSystemMessage(text) {
        const div = document.createElement("div");
        div.className = "chat-msg system";
        div.textContent = text;
        els.chatMessages.appendChild(div);
        scrollToBottom();
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            els.chatArea.scrollTop = els.chatArea.scrollHeight;
        });
    }

    // ── Status & Timer ──────────────────────────────────────────
    function updateStatus(text, statusClass) {
        const dot = els.sessionStatus.querySelector(".status-dot");
        dot.className = "status-dot";
        if (statusClass) dot.classList.add(statusClass);
        els.sessionStatus.querySelector(".status-dot").nextSibling.textContent = ` ${text}`;
    }

    function updateTimer() {
        const m = String(Math.floor(state.sessionSeconds / 60)).padStart(2, "0");
        const s = String(state.sessionSeconds % 60).padStart(2, "0");
        els.sessionTimer.textContent = `${m}:${s}`;
    }

    // ── Toast Notifications ─────────────────────────────────────
    function showToast(message, type = "") {
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.textContent = message;
        els.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3500);
    }

    // ── Utilities ───────────────────────────────────────────────
    function arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    function base64ToArrayBuffer(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Start ───────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", init);
})();
