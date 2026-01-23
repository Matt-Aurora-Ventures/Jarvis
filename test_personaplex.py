#!/usr/bin/env python
"""
PersonaPlex Installation Verification Script
=============================================

Tests the PersonaPlex-7B integration to ensure everything is properly installed.
"""

import sys
from pathlib import Path

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_imports():
    """Test that all required modules can be imported."""
    print_section("Testing Imports")

    errors = []

    # Test Moshi
    try:
        import moshi
        print("[OK] moshi-personaplex imported successfully")
    except ImportError as e:
        errors.append(f"[FAIL] moshi: {e}")
        print(f"[FAIL] moshi-personaplex import failed: {e}")

    # Test dependencies
    deps = [
        ("torch", "PyTorch"),
        ("transformers", "HuggingFace Transformers"),
        ("sounddevice", "SoundDevice"),
        ("librosa", "Librosa"),
        ("numpy", "NumPy"),
    ]

    for module, name in deps:
        try:
            __import__(module)
            print(f"[OK] {name} imported successfully")
        except ImportError as e:
            errors.append(f"[FAIL] {name}: {e}")
            print(f"[FAIL] {name} import failed: {e}")

    # Test PersonaPlex engine
    try:
        from core.personaplex_engine import PersonaPlexEngine, create_jarvis_persona
        print("[OK] PersonaPlex engine modules imported successfully")
    except ImportError as e:
        errors.append(f"[FAIL] PersonaPlex engine: {e}")
        print(f"[FAIL] PersonaPlex engine import failed: {e}")

    return len(errors) == 0, errors

def test_cuda():
    """Test CUDA availability."""
    print_section("Testing CUDA GPU")

    try:
        import torch

        cuda_available = torch.cuda.is_available()
        if cuda_available:
            device_name = torch.cuda.get_device_name(0)
            device_count = torch.cuda.device_count()
            print(f"[OK] CUDA available: {device_name}")
            print(f"   GPU count: {device_count}")
            print(f"   CUDA version: {torch.version.cuda}")

            # Check VRAM
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                total_memory = props.total_memory / (1024**3)  # Convert to GB
                print(f"   Total VRAM: {total_memory:.1f} GB")

                if total_memory < 16:
                    print(f"[WARN]  Warning: PersonaPlex requires 16GB+ VRAM (you have {total_memory:.1f}GB)")
                    return False

            return True
        else:
            print("[FAIL] CUDA not available")
            print("   PersonaPlex requires NVIDIA GPU with CUDA support")
            print("   Install CUDA toolkit and PyTorch with CUDA:")
            print("   pip install torch --index-url https://download.pytorch.org/whl/cu121")
            return False
    except ImportError:
        print("[FAIL] PyTorch not installed")
        return False
    except Exception as e:
        print(f"[FAIL] CUDA check failed: {e}")
        return False

def test_huggingface_token():
    """Test HuggingFace token."""
    print_section("Testing HuggingFace Token")

    import os

    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")

    if hf_token:
        print(f"[OK] HuggingFace token found (length: {len(hf_token)})")
        print(f"   Token prefix: {hf_token[:10]}...")
        return True
    else:
        print("[FAIL] HuggingFace token not found")
        print("   Set HF_TOKEN environment variable:")
        print("   export HF_TOKEN='hf_your_token_here'")
        print("   Get token from: https://huggingface.co/settings/tokens")
        print("   Accept license: https://huggingface.co/nvidia/personaplex-7b-v1")
        return False

def test_engine_init():
    """Test PersonaPlex engine initialization."""
    print_section("Testing PersonaPlex Engine")

    try:
        from core.personaplex_engine import get_engine, create_jarvis_persona

        print("Initializing PersonaPlex engine...")
        print("(This may take a few minutes on first run - downloading model)")

        engine = get_engine()

        if engine and engine.is_initialized:
            print("[OK] PersonaPlex engine initialized successfully")

            # Check health
            health = engine.check_health()
            print(f"   Device: {health.get('device', 'unknown')}")
            print(f"   CUDA available: {health.get('cuda_available', False)}")
            if health.get('cuda_device'):
                print(f"   GPU: {health['cuda_device']}")
            if health.get('cuda_memory_allocated'):
                print(f"   VRAM allocated: {health['cuda_memory_allocated']:.2f} GB")

            # Test persona
            print("\nTesting persona configuration...")
            persona = create_jarvis_persona()
            engine.set_persona(persona)
            print("[OK] Jarvis persona configured")

            return True
        else:
            print("[FAIL] PersonaPlex engine initialization failed")
            print("   Check logs for details")
            return False

    except Exception as e:
        print(f"[FAIL] PersonaPlex engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_voice_integration():
    """Test voice.py integration."""
    print_section("Testing Voice Integration")

    try:
        from core.voice_personaplex_integration import (
            _personaplex_configured,
            _speak_with_personaplex,
            _start_personaplex_process,
        )
        print("[OK] Voice integration functions available")

        # Check if PersonaPlex is imported in voice.py
        try:
            from core import voice
            if hasattr(voice, 'PERSONAPLEX_AVAILABLE'):
                if voice.PERSONAPLEX_AVAILABLE:
                    print("[OK] PersonaPlex integrated into voice.py")
                else:
                    print("[WARN]  PersonaPlex integration present but not available")
            else:
                print("[FAIL] PersonaPlex not integrated into voice.py")
                print("   Run the integration manually")
                return False
        except Exception as e:
            print(f"[WARN]  Could not check voice.py integration: {e}")

        return True

    except ImportError as e:
        print(f"[FAIL] Voice integration not available: {e}")
        return False

def main():
    """Run all tests."""
    print("""
============================================================
     PersonaPlex-7B Installation Verification
     NVIDIA Full-Duplex Conversational AI
============================================================
    """)

    results = {
        "Imports": test_imports(),
        "CUDA GPU": (test_cuda(), []),
        "HuggingFace Token": (test_huggingface_token(), []),
        "Voice Integration": (test_voice_integration(), []),
    }

    # Skip engine init if dependencies failed
    all_deps_ok = all([results["Imports"][0], results["CUDA GPU"][0], results["HuggingFace Token"][0]])

    if all_deps_ok:
        results["Engine Initialization"] = (test_engine_init(), [])
    else:
        print_section("Skipping Engine Test")
        print("[WARN]  Prerequisites not met - skipping engine initialization test")
        print("   Fix the issues above and run this script again")

    # Summary
    print_section("Test Summary")

    passed = sum(1 for r in results.values() if r[0])
    total = len(results)

    for name, (success, errors) in results.items():
        status = "[OK] PASS" if success else "[FAIL] FAIL"
        print(f"{status} - {name}")

        if errors:
            for error in errors:
                print(f"     {error}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! PersonaPlex is ready to use.")
        print("\nNext steps:")
        print("1. Configure in config.yaml:")
        print("   voice:")
        print("     tts_engine: personaplex")
        print("     personaplex:")
        print("       enabled: true")
        print("       device: cuda")
        print("       persona: jarvis")
        print("\n2. Start the daemon: python jarvis_daemon.py")
        print("3. See docs/personaplex_setup.md for full guide")
    else:
        print("\n[WARN]  Some tests failed. Fix the issues above and retry.")
        print("\nQuick fixes:")
        print("- Install dependencies: pip install -r requirements-personaplex.txt")
        print("- Install Moshi: pip install ~/Desktop/personaplex/moshi/")
        print("- Set HF token: export HF_TOKEN='your_token'")
        print("- Check CUDA: nvidia-smi")

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
