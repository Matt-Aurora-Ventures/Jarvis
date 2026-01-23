# PersonaPlex-7B Setup Guide

## Overview

PersonaPlex-7B is NVIDIA's breakthrough full-duplex conversational AI model that eliminates the traditional ASR→LLM→TTS pipeline friction. It can listen and speak **simultaneously**, enabling natural conversation with:

- **Ultra-low latency**: 170ms turn-taking, 240ms interruption response
- **End-to-end speech-to-speech**: No pipeline, direct audio→audio
- **Zero-shot persona control**: Text prompts define personality/role
- **Voice conditioning**: Audio samples control voice characteristics
- **Full-duplex**: True simultaneous listen/speak like human conversation

## Prerequisites

### Hardware Requirements

**Minimum:**
- NVIDIA GPU with Ampere architecture (RTX 3000 series, A100)
- 16GB VRAM
- CUDA 11.8+

**Recommended:**
- NVIDIA A100 (80GB) or H100
- 32GB+ VRAM
- CUDA 12.1+

**Note:** PersonaPlex requires GPU acceleration. CPU-only mode is not supported.

### Software Requirements

- Python 3.10+
- CUDA Toolkit (11.8 or 12.1)
- HuggingFace account with model license accepted

## Installation Steps

### 1. Install CUDA-Enabled PyTorch

Choose the correct command for your CUDA version:

**CUDA 11.8:**
```bash
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**CUDA 12.1:**
```bash
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**CUDA 12.8 (Blackwell/latest):**
```bash
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Verify CUDA availability:
```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

### 2. Install Moshi (PersonaPlex Foundation)

PersonaPlex is built on Moshi architecture. Clone and install:

```bash
# Clone PersonaPlex repository
git clone https://github.com/NVIDIA/personaplex.git
cd personaplex

# Install Moshi
pip install ./moshi/
```

### 3. Install Additional Dependencies

```bash
# Audio processing
pip install librosa soundfile scipy

# HuggingFace & Transformers
pip install transformers accelerate huggingface-hub

# Audio I/O for full-duplex
pip install pyaudio sounddevice

# Optional: For advanced audio processing
pip install webrtcvad
```

### 4. HuggingFace Authentication

PersonaPlex-7B weights require license acceptance and authentication.

**Step 1:** Create HuggingFace account at https://huggingface.co/join

**Step 2:** Accept model license at https://huggingface.co/nvidia/personaplex-7b-v1

**Step 3:** Generate access token:
- Visit https://huggingface.co/settings/tokens
- Create new token with "Read" permissions
- Copy token

**Step 4:** Set environment variable:

**Linux/macOS:**
```bash
export HF_TOKEN="hf_your_token_here"
# Add to ~/.bashrc or ~/.zshrc for persistence
echo 'export HF_TOKEN="hf_your_token_here"' >> ~/.bashrc
```

**Windows (PowerShell):**
```powershell
$env:HF_TOKEN = "hf_your_token_here"
# For persistence, add to system environment variables
[System.Environment]::SetEnvironmentVariable('HF_TOKEN', 'hf_your_token_here', 'User')
```

**Windows (CMD):**
```cmd
set HF_TOKEN=hf_your_token_here
# For persistence, use System Properties > Environment Variables
```

Verify authentication:
```bash
python -c "from huggingface_hub import HfApi; api = HfApi(); print(api.whoami())"
```

### 5. Download PersonaPlex Model

On first use, the model will be automatically downloaded (~14GB). To pre-download:

```bash
from transformers import AutoModel
model = AutoModel.from_pretrained("nvidia/personaplex-7b-v1", token="your_hf_token")
```

Or use HuggingFace CLI:
```bash
huggingface-cli login
huggingface-cli download nvidia/personaplex-7b-v1
```

## Configuration

### Enable PersonaPlex in Jarvis

Edit your Jarvis configuration (`~/.lifeos/config.yaml` or `lifeos/config/config.yaml`):

```yaml
voice:
  tts_engine: personaplex  # Use PersonaPlex for TTS/STT

  # PersonaPlex-specific settings
  personaplex:
    enabled: true
    device: cuda  # or "cuda:0" for specific GPU
    persona: jarvis  # Options: jarvis, morgan_freeman, custom

    # Custom persona (if persona: custom)
    custom_persona:
      role_prompt: "You are a wise AI assistant..."
      temperature: 0.7
      max_tokens: 256
      interrupt_threshold: 0.5

    # Voice conditioning (optional)
    voice_prompt: "data/voices/jarvis_reference.wav"  # 24kHz WAV file

    # Full-duplex settings
    full_duplex: true
    barge_in_enabled: true
    barge_in_sensitivity: 0.5  # 0.0-1.0, higher = more sensitive
```

### Voice Conditioning

To use custom voice characteristics, provide a reference audio sample:

**Requirements:**
- Format: WAV (16-bit PCM)
- Sample rate: 24kHz (PersonaPlex requirement)
- Duration: 5-10 seconds recommended
- Content: Clean speech, no background noise

**Convert existing audio to 24kHz:**
```bash
# Using FFmpeg
ffmpeg -i input.wav -ar 24000 -ac 1 output_24k.wav

# Using SoX
sox input.wav -r 24000 -c 1 output_24k.wav
```

Place reference audio in `data/voices/` directory.

## Testing Installation

### Quick Test

```python
from core.personaplex_engine import PersonaPlexEngine, create_jarvis_persona

# Initialize engine
engine = PersonaPlexEngine()
if engine.initialize():
    print("✅ PersonaPlex initialized successfully!")

    # Set persona
    persona = create_jarvis_persona()
    engine.set_persona(persona)

    # Check health
    health = engine.check_health()
    print(f"Health: {health}")
else:
    print("❌ PersonaPlex initialization failed")
```

### Full-Duplex Test

Test the full conversational capability:

```python
import numpy as np
from core.personaplex_engine import get_engine, create_jarvis_persona

engine = get_engine()
persona = create_jarvis_persona()
engine.set_persona(persona)

# Simulate audio input (replace with real microphone input)
sample_audio = np.random.randn(PERSONAPLEX_SAMPLE_RATE * 2)  # 2 seconds

# Process audio stream
output = engine.process_audio_stream(sample_audio, sample_rate=24000)
if output is not None:
    print(f"✅ Generated {len(output)} audio samples")
```

## Usage Examples

### Basic Speech Synthesis

```python
from core.personaplex_engine import get_engine, create_jarvis_persona

engine = get_engine()
engine.set_persona(create_jarvis_persona())

audio_path = engine.synthesize_speech(
    text="Hello, I am Jarvis, your personal assistant.",
    output_path=Path("output/jarvis_greeting.wav")
)
print(f"Audio saved to: {audio_path}")
```

### Full-Duplex Conversation

```python
import sounddevice as sd
from core.personaplex_engine import get_engine, create_jarvis_persona

engine = get_engine()
engine.set_persona(create_jarvis_persona())

def audio_callback(output_audio):
    """Callback to play generated audio."""
    sd.play(output_audio, PERSONAPLEX_SAMPLE_RATE)

# Start full-duplex session
engine.start_full_duplex_session(audio_callback)

# ... conversation happens ...

# Stop session
engine.stop_full_duplex_session()
```

### Custom Persona

```python
from core.personaplex_engine import PersonaConfig, get_engine

custom_persona = PersonaConfig(
    role_prompt=(
        "You are a cybersecurity expert with deep knowledge of "
        "Solana blockchain security. You speak technically but clearly."
    ),
    temperature=0.6,  # Lower = more focused
    max_tokens=512,
    interrupt_threshold=0.4,  # Less sensitive to interruption
)

engine = get_engine()
engine.set_persona(custom_persona)
```

## Integration with Jarvis Voice System

PersonaPlex integrates seamlessly with Jarvis's existing voice infrastructure:

### Daemon Integration

The daemon (`core/daemon.py`) automatically initializes PersonaPlex when configured:

```python
# Daemon startup checks PersonaPlex health
from core.personaplex_engine import get_engine

engine = get_engine()
if engine and engine.is_initialized:
    print("✅ PersonaPlex ready for full-duplex conversations")
```

### Voice Manager Integration

PersonaPlex works with the existing `VoiceManager` in [`core/voice.py`](core/voice.py:1505):

```python
# Full-duplex replaces wake-word loop
if tts_engine == "personaplex":
    # Use PersonaPlex full-duplex instead of traditional pipeline
    engine = get_engine()
    engine.start_full_duplex_session(...)
```

## Troubleshooting

### CUDA Out of Memory

**Symptoms:** `RuntimeError: CUDA out of memory`

**Solutions:**
1. Reduce `max_tokens` in PersonaConfig (256→128)
2. Use gradient checkpointing (if available)
3. Close other GPU applications
4. Use a GPU with more VRAM (32GB+)

### Model Download Fails

**Symptoms:** `OSError: Connection error` or `401 Unauthorized`

**Solutions:**
1. Verify HF_TOKEN is set: `echo $HF_TOKEN`
2. Check license accepted at https://huggingface.co/nvidia/personaplex-7b-v1
3. Test token: `huggingface-cli whoami`
4. Regenerate token if expired

### Audio Quality Issues

**Symptoms:** Distorted or robotic voice output

**Solutions:**
1. Verify 24kHz sample rate: All audio must be 24kHz
2. Check voice conditioning audio quality
3. Adjust `temperature` (0.7-0.9 for more natural speech)
4. Ensure clean input audio (no background noise)

### Slow Inference

**Symptoms:** High latency (>500ms)

**Solutions:**
1. Verify GPU is being used: Check `health["device"]`
2. Reduce `max_tokens` for faster generation
3. Use FP16 instead of BF16 (if supported)
4. Close background GPU applications

### Import Errors

**Symptoms:** `ModuleNotFoundError: No module named 'moshi'`

**Solutions:**
```bash
# Reinstall Moshi
cd personaplex
pip install --force-reinstall ./moshi/

# Verify installation
python -c "import moshi; print(moshi.__version__)"
```

## Performance Optimization

### Latency Optimization

For minimal latency:
```python
persona = PersonaConfig(
    role_prompt="...",
    max_tokens=128,  # Reduce for faster generation
    temperature=0.7,
    interrupt_threshold=0.3,  # Higher sensitivity = faster interrupts
)
```

### Memory Optimization

For lower VRAM usage:
```python
import torch

# Load model in FP16 instead of BF16
model = AutoModel.from_pretrained(
    "nvidia/personaplex-7b-v1",
    torch_dtype=torch.float16,  # Instead of bfloat16
    device_map="cuda",
)
```

### Batch Processing

For offline processing of multiple requests:
```python
texts = ["Hello", "How are you?", "Goodbye"]
for text in texts:
    engine.synthesize_speech(text, output_path=Path(f"output/{text}.wav"))
```

## Advanced Features

### Voice Cloning

Use your own voice or a specific reference:

1. Record 10-15 seconds of clean speech at 24kHz
2. Save as `data/voices/my_voice.wav`
3. Configure:
```yaml
personaplex:
  voice_prompt: "data/voices/my_voice.wav"
```

### Persona Templates

Create reusable persona templates in `core/personaplex_engine.py`:

```python
def create_security_expert_persona() -> PersonaConfig:
    return PersonaConfig(
        role_prompt="You are a Solana security auditor...",
        temperature=0.6,
        max_tokens=512,
    )
```

## References

- **GitHub Repository**: https://github.com/NVIDIA/personaplex
- **HuggingFace Model**: https://huggingface.co/nvidia/personaplex-7b-v1
- **Research Paper**: [PersonaPlex: Voice and Role Control for Full Duplex Conversational](https://research.nvidia.com/labs/adlr/personaplex/)
- **NVIDIA ADLR Project Page**: https://research.nvidia.com/labs/adlr/personaplex/

## License

- **Code**: MIT License
- **Model Weights**: NVIDIA Open Model License + CC-BY-4.0

Review license terms at: https://huggingface.co/nvidia/personaplex-7b-v1

---

**Next Steps:**
1. Test basic synthesis: `python -c "from core.personaplex_engine import *; test_engine()"`
2. Configure persona in `config.yaml`
3. Start Jarvis daemon with PersonaPlex enabled
4. Try "Hey Jarvis" wake word → full-duplex conversation!
