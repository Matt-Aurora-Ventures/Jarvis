"""Jarvis CLI entrypoint."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from jarvis_cli.bootstrap import Bootstrapper
from jarvis_cli.capabilities import detect_capabilities
from jarvis_cli.profiles import get_profiles


ROOT = Path(__file__).resolve().parents[1]


def _tag(level: str) -> str:
    return f"[{level}]"


def _print_status(level: str, message: str) -> None:
    print(f"{_tag(level)} {message}")


def _print_capability_report() -> dict:
    report = detect_capabilities()
    tts_label = report.tts if report.tts_available else "TEXT OUTPUT"
    stt_label = report.stt if report.stt_available else "TEXT INPUT"
    fallbacks = " → ".join(report.llm_fallbacks) if report.llm_fallbacks else "none"
    _print_status("OK", f"TTS: {tts_label}")
    _print_status("OK", f"STT: {stt_label}")
    _print_status("OK", f"LLM: {report.llm_selected} (fallbacks: {fallbacks})")
    return {
        "tts_available": report.tts_available,
        "stt_available": report.stt_available,
    }


def _text_chat_loop(enable_tts: bool) -> None:
    from core import conversation, voice

    _print_status("OK", "Voice input unavailable; falling back to typed input.")
    _print_status("OK", "Type 'exit' or 'quit' to end the session.")
    session_history: List[Dict[str, str]] = []
    while True:
        try:
            user_text = input("You> ").strip()
        except EOFError:
            break
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break
        response = conversation.generate_response(
            user_text,
            "",
            session_history,
            channel="voice",
        )
        session_history.append({"source": "voice_chat_user", "text": user_text})
        session_history.append({"source": "voice_chat_assistant", "text": response})
        print(f"Jarvis> {response}")
        if enable_tts:
            voice.speak_text(response)


def _run_voice_profile(no_stt: bool, no_tts: bool) -> None:
    from core import voice

    capabilities = _print_capability_report()
    stt_available = capabilities["stt_available"] and not no_stt
    tts_available = capabilities["tts_available"] and not no_tts
    if stt_available:
        if not tts_available:
            _print_status("WARN", "TTS unavailable; responses will be printed.")
        voice.start_chat_session()
    else:
        _text_chat_loop(enable_tts=tts_available)


def _start_telegram(strict: bool, background: bool = False) -> Optional[subprocess.Popen]:
    profiles = get_profiles()
    missing = profiles["telegram"].missing_required(os.environ)
    if missing:
        msg = "Telegram disabled (missing TELEGRAM_BOT_TOKEN)."
        if strict:
            _print_status("ERROR", msg)
            raise SystemExit(1)
        _print_status("WARN", msg)
        return None
    command = [sys.executable, str(ROOT / "tg_bot" / "cli.py"), "start"]
    if background:
        _print_status("OK", "Starting Telegram bot in background.")
        return subprocess.Popen(command)
    _print_status("OK", "Starting Telegram bot.")
    subprocess.run(command, check=False)
    return None


def _start_twitter(strict: bool, background: bool = False) -> Optional[subprocess.Popen]:
    profiles = get_profiles()
    missing = profiles["twitter"].missing_required(os.environ)
    if missing:
        msg = "Twitter disabled (missing X API credentials)."
        if strict:
            _print_status("ERROR", msg)
            raise SystemExit(1)
        _print_status("WARN", msg)
        return None
    command = [sys.executable, str(ROOT / "bots" / "twitter" / "run_autonomous.py")]
    if background:
        _print_status("OK", "Starting Twitter bot in background.")
        return subprocess.Popen(command)
    _print_status("OK", "Starting Twitter bot.")
    subprocess.run(command, check=False)
    return None


def _summary(started: Dict[str, bool]) -> None:
    summary = ", ".join(f"{key}={'yes' if val else 'no'}" for key, val in started.items())
    _print_status("OK", f"Startup summary: {summary}")


def cmd_up(args: argparse.Namespace) -> int:
    bootstrapper = Bootstrapper()
    bootstrapper.doctor(install_deps=False)
    started = {"voice": False, "telegram": False, "twitter": False}

    if args.profile == "voice":
        _run_voice_profile(args.no_stt, args.no_tts)
        started["voice"] = True
    elif args.profile == "telegram":
        _start_telegram(args.strict, background=False)
        started["telegram"] = True
    elif args.profile == "twitter":
        _start_twitter(args.strict, background=False)
        started["twitter"] = True
    elif args.profile == "all":
        processes: List[subprocess.Popen] = []
        proc = _start_telegram(args.strict, background=True)
        if proc:
            processes.append(proc)
            started["telegram"] = True
        proc = _start_twitter(args.strict, background=True)
        if proc:
            processes.append(proc)
            started["twitter"] = True
        try:
            _run_voice_profile(args.no_stt, args.no_tts)
            started["voice"] = True
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGTERM)
    else:
        _print_status("ERROR", f"Unknown profile: {args.profile}")
        return 1

    _summary(started)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    bootstrapper = Bootstrapper()
    report = bootstrapper.run_validation()
    from jarvis_cli.bootstrap import BootstrapResult

    result = BootstrapResult(report=report)
    bootstrapper.write_report(result)
    print(report.summary())
    return 0 if report.passed else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    bootstrapper = Bootstrapper()
    result = bootstrapper.doctor(install_deps=args.install_deps)
    for fix in result.fixes:
        _print_status("OK", fix)
    for warning in result.warnings:
        _print_status("WARN", warning)
    for error in result.errors:
        _print_status("ERROR", error)
    if result.report:
        print(result.report.summary())
    return 0


def cmd_deps(args: argparse.Namespace) -> int:
    bootstrapper = Bootstrapper()
    result = bootstrapper.doctor(install_deps=True)
    for fix in result.fixes:
        _print_status("OK", fix)
    if result.errors:
        for error in result.errors:
            _print_status("ERROR", error)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis", description="Jarvis unified CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    up_parser = subparsers.add_parser("up", help="Start Jarvis with a profile.")
    up_parser.add_argument("--profile", default="voice", choices=get_profiles().keys())
    up_parser.add_argument("--strict", action="store_true", help="Fail on missing required config.")
    up_parser.add_argument("--no-stt", action="store_true", help="Disable voice input.")
    up_parser.add_argument("--no-tts", action="store_true", help="Disable speech output.")
    up_parser.set_defaults(func=cmd_up)

    doctor_parser = subparsers.add_parser("doctor", help="Diagnose and apply safe fixes.")
    doctor_parser.add_argument("--install-deps", action="store_true", help="Install Python dependencies.")
    doctor_parser.set_defaults(func=cmd_doctor)

    validate_parser = subparsers.add_parser("validate", help="Run startup validation report.")
    validate_parser.set_defaults(func=cmd_validate)

    deps_parser = subparsers.add_parser("deps", help="Install missing dependencies in venv.")
    deps_parser.set_defaults(func=cmd_deps)

    return parser


def run(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    exit_code = args.func(args)
    raise SystemExit(exit_code)
