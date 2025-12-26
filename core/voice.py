import gzip
import io
import os
import shutil
import subprocess
import tempfile
import threading
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from core import (
    config,
    conversation,
    evolution,
    memory,
    notes_manager,
    observation,
    providers,
    secrets,
    skill_manager,
    state,
    system_profiler,
)

VOICES_DIR = Path(__file__).resolve().parents[1] / "data" / "voices"
DEFAULT_PIPER_MODEL = "en_US-amy-low.onnx"
DEFAULT_PIPER_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US-amy-low.onnx.gz"
)
PIPER_BINARY = "piper"


@dataclass
class VoiceCommand:
    action: str
    payload: str


def _load_config() -> dict:
    return config.load_config()


def _wake_word_model_name(wake_word: str) -> str:
    wake_lower = wake_word.lower().strip()
    model_map = {
        "jarvis": "hey_jarvis",
        "hey jarvis": "hey_jarvis",
        "alexa": "alexa",
        "hey mycroft": "hey_mycroft",
        "mycroft": "hey_mycroft",
        "ok google": "ok_google",
        "hey google": "hey_google",
    }
    for key, model in model_map.items():
        if key in wake_lower:
            return model
    return "hey_jarvis"


def _voice_cfg() -> dict:
    cfg = _load_config()
    voice_cfg = cfg.get("voice", {}).copy()
    voice_cfg.setdefault("tts_engine", "piper")
    voice_cfg.setdefault("speak_responses", True)
    return voice_cfg


def _set_voice_error(message: str) -> None:
    """Persist the latest voice error so CLI/status can surface it."""
    state.update_state(voice_error=message[:160])


def _ensure_piper_model(voice_cfg: dict) -> Optional[Path]:
    model_path_value = voice_cfg.get("piper_model_path")
    if model_path_value:
        model_path = Path(model_path_value).expanduser()
    else:
        model_name = voice_cfg.get("piper_model", DEFAULT_PIPER_MODEL)
        model_path = VOICES_DIR / model_name
    if model_path.exists():
        return model_path

    download_url = voice_cfg.get("piper_download_url", DEFAULT_PIPER_URL)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        response = requests.get(download_url, timeout=120)
        response.raise_for_status()
        data = response.content
        if download_url.endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                with open(model_path, "wb") as handle:
                    shutil.copyfileobj(gz, handle)
        else:
            with open(model_path, "wb") as handle:
                handle.write(data)
    except Exception as exc:
        print(f"Failed to download Piper model: {exc}")
        return None
    return model_path


def _speak_with_piper(text: str, voice_cfg: dict) -> bool:
    model_path = _ensure_piper_model(voice_cfg)
    if not model_path:
        _set_voice_error("Missing Piper model; falling back to macOS say.")
        return False
    if shutil.which(PIPER_BINARY) is None:
        _set_voice_error("Piper binary not found in PATH; install piper.")
        return False
    tmp_wav = Path(tempfile.mkstemp(suffix=".wav")[1])
    cmd = [
        PIPER_BINARY,
        "--model",
        str(model_path),
        "--output_file",
        str(tmp_wav),
    ]
    speaker = voice_cfg.get("piper_speaker")
    if speaker:
        cmd.extend(["--speaker", str(speaker)])
    try:
        subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        subprocess.run(
            ["afplay", str(tmp_wav)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _set_voice_error(f"Piper TTS failed: {exc}")
        return False
    finally:
        if tmp_wav.exists():
            tmp_wav.unlink(missing_ok=True)


def _speak_with_say(text: str, voice_cfg: dict) -> bool:
    voice_name = str(voice_cfg.get("speech_voice", "")).strip()
    if voice_name.lower() == "morgan freeman":
        voice_name = "Reed (English (US))"

    def _test_voice(name: str) -> bool:
        result = subprocess.run(
            ["say", "-v", name, "test"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return result.returncode == 0 and "not found" not in result.stderr.lower()

    def _run_say(name: str = "") -> bool:
        cmd = ["say"]
        if name:
            cmd.extend(["-v", name])
        if voice_name.lower() == "morgan freeman":
            cmd.extend(["-r", "140"])
        try:
            subprocess.run(
                cmd,
                input=text,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    try:
        if voice_name and _test_voice(voice_name):
            if _run_say(voice_name):
                _set_voice_error("")
                return True
        success = _run_say()
        if success:
            _set_voice_error("")
        return success
    except Exception as exc:
        _set_voice_error(f"macOS say failed: {exc}")
        return False


def _speak(text: str) -> None:
    voice_cfg = _voice_cfg()
    if not voice_cfg.get("speak_responses", False):
        return

    engine = str(voice_cfg.get("tts_engine", "piper")).lower()
    spoke = False
    if engine == "piper":
        spoke = _speak_with_piper(text, voice_cfg)
    elif engine == "say":
        spoke = _speak_with_say(text, voice_cfg)
    else:
        _set_voice_error(f"Unsupported TTS engine '{engine}', falling back to say().")
    if not spoke:
        # Final fallback
        _speak_with_say(text, voice_cfg)


def _transcribe_once(timeout: int, phrase_time_limit: int) -> str:
    try:
        import speech_recognition as sr
    except Exception as e:
        return ""

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
    except Exception as e:
        return ""

    # Try Gemini STT (Multimodal)
    gemini_key = secrets.get_gemini_key()
    if gemini_key:
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio.get_wav_data())
                temp_path = f.name
            
            transcript = providers.transcribe_audio_gemini(temp_path)
            os.unlink(temp_path)
            if transcript:
                return transcript
        except Exception as e:
            pass

    # Try OpenAI Whisper
    openai_key = secrets.get_openai_key()
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio.get_wav_data())
                temp_path = f.name
            
            with open(temp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                )
            os.unlink(temp_path)
            if transcript.text:
                return transcript.text
        except Exception as e:
            pass

    # Fallback to Google
    try:
        return recognizer.recognize_google(audio)
    except Exception as e:
        pass

    # Fallback to Sphinx (Last resort)
    try:
        return recognizer.recognize_sphinx(audio)
    except Exception as e:
        return ""

def _stop_phrase_match(text: str, phrase: str) -> bool:
    return phrase.strip().lower() in text.strip().lower()


def parse_command(text: str) -> Optional[VoiceCommand]:
    lower = text.strip().lower()
    if not lower:
        return None
    if "stop listening" in lower:
        return VoiceCommand(action="listening_off", payload="")
    if "start listening" in lower:
        return VoiceCommand(action="listening_on", payload="")
    if lower.startswith("status") or "status" in lower:
        return VoiceCommand(action="status", payload="")
    if lower.startswith("diagnostics") or "diagnostics" in lower:
        return VoiceCommand(action="diagnostics", payload="")
    if lower.startswith("summarize") or "summarize" in lower:
        return VoiceCommand(action="summarize", payload="")
    if "overnight" in lower:
        return VoiceCommand(action="overnight", payload="")
    if "report" in lower:
        if "morning" in lower:
            return VoiceCommand(action="report_morning", payload="")
        if "afternoon" in lower:
            return VoiceCommand(action="report_afternoon", payload="")
        if "weekly" in lower:
            return VoiceCommand(action="report_weekly", payload="")
        return VoiceCommand(action="report_daily", payload="")
    if lower.startswith("log"):
        payload = lower.replace("log", "", 1).strip()
        return VoiceCommand(action="log", payload=payload)
    if (
        "improve yourself" in lower
        or "modify your code" in lower
        or "build ability" in lower
        or "add ability" in lower
        or "add skill" in lower
        or "build skill" in lower
    ):
        return VoiceCommand(action="evolve", payload=text)
    # Shutdown commands
    if (
        "shut down" in lower
        or "shutdown" in lower
        or "turn off" in lower
        or "go to sleep" in lower
        or "stop running" in lower
        or "goodbye jarvis" in lower
        or "bye jarvis" in lower
    ):
        return VoiceCommand(action="shutdown", payload="")
    return None


def _confirm_apply() -> bool:
    confirmation = _transcribe_once(timeout=4, phrase_time_limit=3)
    return "apply" in confirmation.lower() or "yes" in confirmation.lower()


def handle_command(command: VoiceCommand) -> str:
    from core import cli

    if command.action == "listening_off":
        state.update_state(voice_enabled=False, mic_status="off")
        return "Plain English:\n- What I did: Turned voice listening off.\n- Why I did it: You asked me to stop listening.\n- What happens next: Say or run 'start listening' to resume.\n- What I need from you: Nothing.\n\nTechnical Notes:\n- Modules/files involved: core/state.py\n- Key concepts/terms: Voice toggle\n- Commands executed (or would execute in dry-run): state update\n- Risks/constraints: None.\n"
    if command.action == "listening_on":
        state.update_state(voice_enabled=True, mic_status="idle")
        return "Plain English:\n- What I did: Turned voice listening on.\n- Why I did it: You asked me to start listening.\n- What happens next: Say 'status' or another command.\n- What I need from you: Nothing.\n\nTechnical Notes:\n- Modules/files involved: core/state.py\n- Key concepts/terms: Voice toggle\n- Commands executed (or would execute in dry-run): state update\n- Risks/constraints: None.\n"

    if command.action == "status":
        return cli.capture_status_text()

    if command.action == "diagnostics":
        return cli.capture_diagnostics_text(dry_run=True)

    if command.action == "summarize":
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled summarize because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Say 'summarize' again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/cli.py\n- Key concepts/terms: Apply confirmation\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        return cli.capture_summarize_text(dry_run=False)

    if command.action == "overnight":
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled overnight run because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Say 'overnight' again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/overnight.py\n- Key concepts/terms: Apply confirmation\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        return cli.capture_overnight_text(dry_run=False)

    if command.action.startswith("report"):
        kind = command.action.replace("report_", "")
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled report because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Say 'report' again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/reporting.py\n- Key concepts/terms: Apply confirmation\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        return cli.capture_report_text(kind=kind, dry_run=False)

    if command.action == "log":
        if not command.payload:
            return "Plain English:\n- What I did: Could not log because I did not hear the note.\n- Why I did it: Logging requires text.\n- What happens next: Say 'log' followed by your note.\n- What I need from you: Your note text.\n\nTechnical Notes:\n- Modules/files involved: core/voice.py\n- Key concepts/terms: Speech recognition\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled log because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Say 'log ...' again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/memory.py\n- Key concepts/terms: Apply confirmation\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        topic, body = notes_manager.extract_topic_and_body(command.payload)
        note_path, summary_path, _ = notes_manager.save_note(
            topic=topic,
            content=f"# {topic.title()}\n\n{body}",
            fmt="md",
            tags=["voice", "log"],
            source="voice.log",
            metadata={"command": "voice.log"},
        )
        memory.append_entry(command.payload, "voice_log", safety_context(apply=True))
        return (
            "Plain English:\n"
            "- What I did: Saved your note to memory and wrote a local file.\n"
            "- Why I did it: You asked to log a note.\n"
            "- What happens next: Say 'summarize' to route notes or open the saved file.\n"
            "- What I need from you: Nothing.\n\n"
            "Technical Notes:\n"
            "- Modules/files involved: core/memory.py, core/notes_manager.py\n"
            "- Key concepts/terms: JSONL memory buffer, local note store\n"
            "- Commands executed (or would execute in dry-run): Append entry; write note "
            f"({note_path}) and summary ({summary_path})\n"
            "- Risks/constraints: None.\n"
        )

    if command.action == "evolve":
        if not _confirm_apply():
            return "Plain English:\n- What I did: Canceled self-improvement because APPLY was not confirmed.\n- Why I did it: Safety gate.\n- What happens next: Ask again and confirm APPLY.\n- What I need from you: Say APPLY.\n\nTechnical Notes:\n- Modules/files involved: core/evolution.py\n- Key concepts/terms: Self-improvement\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
        return evolution.evolve_from_conversation(
            user_text=command.payload,
            conversation_history=[],
            context=safety_context(apply=True),
        )

    if command.action == "shutdown":
        _speak("Goodbye. Shutting down now.")
        # Signal daemon to stop
        pid = state.read_pid()
        if pid:
            try:
                import signal as sig
                os.kill(pid, sig.SIGTERM)
            except Exception as e:
                pass
        state.clear_pid()
        state.update_state(running=False)
        return "Plain English:\n- What I did: Shut down Jarvis.\n- Why I did it: You asked me to stop.\n- What happens next: Run 'lifeos on --apply' to start again.\n- What I need from you: Nothing.\n\nTechnical Notes:\n- Modules/files involved: core/state.py\n- Key concepts/terms: SIGTERM, graceful shutdown\n- Commands executed: kill daemon process\n- Risks/constraints: None.\n"

    return "Plain English:\n- What I did: I could not map that request.\n- Why I did it: The command did not match supported actions.\n- What happens next: Try 'status', 'log', 'report', or 'diagnostics'.\n- What I need from you: A supported command.\n\nTechnical Notes:\n- Modules/files involved: core/voice.py\n- Key concepts/terms: Intent parsing\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"


def safety_context(apply: bool):
    from core import safety

    if apply:
        return safety.SafetyContext(apply=True, dry_run=False)
    return safety.SafetyContext(apply=False, dry_run=True)


def _capture_screen_context(tracker: Optional[observation.MouseTracker]) -> str:
    return observation.format_snapshot(tracker)


def _chat_response(
    user_text: str,
    tracker: Optional[observation.MouseTracker],
    session_history: list[dict],
) -> str:
    screen_context = _capture_screen_context(tracker)
    return conversation.generate_response(user_text, screen_context, session_history)


def chat_session() -> None:
    cfg = _load_config()
    voice_cfg = cfg.get("voice", {})
    greeting = voice_cfg.get(
        "chat_greeting", "Hi, I'm here. What do you want me to do?"
    )
    stop_phrase = voice_cfg.get("chat_stop_phrase", "thank you goodbye for now")
    silence_limit = int(voice_cfg.get("chat_silence_limit", 3))
    timeout = int(voice_cfg.get("command_timeout_seconds", 6))
    phrase_limit = int(voice_cfg.get("phrase_time_limit", 6))
    track_mouse = bool(voice_cfg.get("track_mouse", True))

    state.update_state(chat_active=True, mic_status="chat")
    if greeting:
        _speak(greeting)
        print(greeting)

    tracker = observation.MouseTracker() if track_mouse else None
    if tracker:
        tracker.start()

    silence_count = 0
    session_history: list[dict] = []
    try:
        while True:
            text = _transcribe_once(timeout=timeout, phrase_time_limit=phrase_limit)
            if not text:
                silence_count += 1
                if silence_count >= silence_limit:
                    farewell = "Ending chat due to silence."
                    _speak(farewell)
                    print(farewell)
                    break
                continue
            silence_count = 0
            if _stop_phrase_match(text, stop_phrase):
                farewell = "Thank you. Goodbye for now."
                _speak(farewell)
                print(farewell)
                break
            session_history.append({"source": "voice_chat_user", "text": text})
            command = parse_command(text)
            if command:
                response = handle_command(command)
            else:
                response = _chat_response(text, tracker, session_history)
            session_history.append({"source": "voice_chat_assistant", "text": response})
            _speak(response)
            print(response)
    finally:
        if tracker:
            tracker.stop()
        state.update_state(chat_active=False, mic_status="idle")


_chat_lock = threading.Lock()


def start_chat_session() -> None:
    if state.read_state().get("chat_active"):
        return
    if not _chat_lock.acquire(blocking=False):
        return

    def _run() -> None:
        try:
            chat_session()
        finally:
            _chat_lock.release()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


class VoiceManager(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._listening = False

    def stop(self) -> None:
        self._stop_event.set()

    def _wake_word_loop(self) -> None:
        try:
            import numpy as np
            import openwakeword
            import pyaudio
        except Exception as e:
            state.update_state(
                voice_mode="push-to-talk",
                mic_status="off",
                voice_error="openwakeword_unavailable",
            )
            return

        cfg = _load_config()
        wake_word = cfg.get("voice", {}).get("wake_word", "jarvis")
        model_name = _wake_word_model_name(wake_word)
        threshold = float(cfg.get("voice", {}).get("wake_word_threshold", 0.6))
        frame_length = int(cfg.get("voice", {}).get("frame_length", 1280))

        model_meta = openwakeword.MODELS.get(model_name, {})
        model_path = model_meta.get("model_path")
        if model_path and not Path(model_path).exists():
            try:
                from openwakeword import utils as oww_utils

                oww_utils.download_models([model_name])
            except Exception as e:
                state.update_state(
                    voice_mode="push-to-talk",
                    mic_status="off",
                    voice_error="wakeword_model_unavailable",
                )
                return
        try:
            model = openwakeword.Model(wakeword_models=[model_name])
        except Exception as e:
            state.update_state(
                voice_mode="push-to-talk",
                mic_status="off",
                voice_error="wakeword_model_unavailable",
            )
            return
        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=frame_length,
            )
        except Exception as e:
            state.update_state(
                voice_mode="push-to-talk",
                mic_status="off",
                voice_error="microphone_unavailable",
            )
            pa.terminate()
            return

        state.update_state(voice_mode="wake-word", mic_status="listening", voice_error="none")
        self._listening = True

        try:
            while not self._stop_event.is_set():
                if state.read_state().get("chat_active"):
                    break
                data = stream.read(frame_length, exception_on_overflow=False)
                audio = np.frombuffer(data, dtype=np.int16)
                prediction = model.predict(audio)
                score = float(prediction.get(model_name, 0.0))
                if score >= threshold:
                    state.update_state(mic_status="capturing")
                    text = _transcribe_once(
                        timeout=6,
                        phrase_time_limit=int(
                            cfg.get("voice", {}).get("phrase_time_limit", 6)
                        ),
                    )
                    command = parse_command(text)
                    if command:
                        response = handle_command(command)
                        _speak(response)
                    state.update_state(mic_status="listening")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            self._listening = False

    def run(self) -> None:
        while not self._stop_event.is_set():
            cfg = _load_config()
            if not cfg.get("voice", {}).get("enabled", True):
                state.update_state(voice_enabled=False, mic_status="off")
                time.sleep(2)
                continue

            if state.read_state().get("chat_active"):
                state.update_state(mic_status="chat")
                time.sleep(1)
                continue

            runtime_voice_enabled = state.read_state().get("voice_enabled", True)
            if not runtime_voice_enabled:
                state.update_state(mic_status="off")
                time.sleep(2)
                continue

            profile = system_profiler.read_profile()
            max_cpu_load = float(cfg.get("voice", {}).get("max_cpu_load", 4.0))
            if profile.cpu_load and profile.cpu_load > max_cpu_load:
                state.update_state(
                    voice_mode="push-to-talk",
                    mic_status="off",
                    voice_error="cpu_load_high",
                )
                time.sleep(5)
                continue

            mode = cfg.get("voice", {}).get("mode", "wake-word")
            state_mode = state.read_state().get("voice_mode", mode)
            if mode == "wake-word" and state_mode != "push-to-talk":
                self._wake_word_loop()
                time.sleep(1)
                continue

            state.update_state(voice_mode="push-to-talk", mic_status="idle")
            time.sleep(2)


def listen_once() -> str:
    cfg = _load_config()
    text = _transcribe_once(
        timeout=int(cfg.get("voice", {}).get("command_timeout_seconds", 6)),
        phrase_time_limit=int(cfg.get("voice", {}).get("phrase_time_limit", 6)),
    )
    command = parse_command(text)
    if not command:
        return "Plain English:\n- What I did: I did not catch a valid command.\n- Why I did it: The audio was unclear or unsupported.\n- What happens next: Try again and speak clearly.\n- What I need from you: A supported command.\n\nTechnical Notes:\n- Modules/files involved: core/voice.py\n- Key concepts/terms: Speech recognition\n- Commands executed (or would execute in dry-run): None\n- Risks/constraints: No changes made.\n"
    response = handle_command(command)
    _speak(response)
    return response
