"""LLM client with SOUL loading and MOLT error handling."""
import asyncio
import os
import logging
import aiohttp
import json
from typing import Optional
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class MOLTMetrics:
    """Track errors and performance metrics."""
    def __init__(self):
        self.errors = {}
        self.latencies = {}
        self.last_success = {}

    def record_error(self, provider, error_type):
        key = f"{provider}:{error_type}"
        self.errors[key] = self.errors.get(key, 0) + 1
        logger.warning(f"MOLT:Monitor - {key} errors: {self.errors[key]}")

    def record_latency(self, provider, latency_ms):
        if provider not in self.latencies:
            self.latencies[provider] = []
        self.latencies[provider].append(latency_ms)
        if len(self.latencies[provider]) > 100:
            self.latencies[provider].pop(0)
        avg = sum(self.latencies[provider]) / len(self.latencies[provider])
        logger.info(f"MOLT:Observe - {provider} avg latency: {avg:.0f}ms")

    def record_success(self, provider):
        self.last_success[provider] = time.time()


molt_metrics = MOLTMetrics()


class LLMClient:
    def __init__(self, provider, soul_file=None):
        self.provider = provider.lower()
        self.api_key = None
        self.soul_prompt = ""
        self.retries = 3
        self.backoff_base = 2
        self.request_timeout = 60

        if self.provider == "openai":
            self.request_timeout = 120

        self._load_api_keys()
        if soul_file:
            self._load_soul(soul_file)

    def _load_api_keys(self):
        """Load API keys from environment file."""
        keys_file = "/root/clawdbots/api_keys.env"
        if os.path.exists(keys_file):
            with open(keys_file) as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        if self.provider == "xai" and k == "XAI_API_KEY":
                            self.api_key = v
                        elif self.provider == "anthropic" and k == "ANTHROPIC_API_KEY":
                            self.api_key = v
                        elif self.provider == "openai" and k == "OPENAI_API_KEY":
                            self.api_key = v

        if not self.api_key:
            logger.warning(f"MOLT:Log - No API key for {self.provider}")

    def _load_soul(self, soul_file):
        """Load SOUL prompt + IDENTITY + BOOTSTRAP from files."""
        base_path = Path("/root/clawdbots")
        context_parts = []

        # Load IDENTITY first (shared context)
        identity_path = base_path / "IDENTITY.md"
        if identity_path.exists():
            context_parts.append(identity_path.read_text())
            logger.info("MOLT:Log - Loaded IDENTITY.md")

        # Load BOOTSTRAP (wake-up protocol)
        bootstrap_path = base_path / "BOOTSTRAP.md"
        if bootstrap_path.exists():
            context_parts.append(bootstrap_path.read_text())
            logger.info("MOLT:Log - Loaded BOOTSTRAP.md")

        # Load specific SOUL file
        soul_path = base_path / soul_file
        if soul_path.exists():
            context_parts.append(soul_path.read_text())
            logger.info(f"MOLT:Log - Loaded SOUL from {soul_file}")
        else:
            logger.error(f"MOLT:Log - SOUL file not found: {soul_file}")

        # Combine all context
        self.soul_prompt = "\n\n---\n\n".join(context_parts)
        logger.info(f"MOLT:Log - Total context: {len(self.soul_prompt)} chars")

    async def ask(self, question, system_prompt=None):
        """Ask the LLM with MOLT error handling and retries."""
        start_time = time.time()
        effective_prompt = self.soul_prompt if self.soul_prompt else (system_prompt or "")

        if effective_prompt:
            msg = f"{effective_prompt[:2000]}\n\nUser: {question}"
        else:
            msg = question

        for attempt in range(self.retries):
            try:
                result = await self._call_provider(msg)
                latency_ms = (time.time() - start_time) * 1000
                molt_metrics.record_latency(self.provider, latency_ms)
                molt_metrics.record_success(self.provider)
                logger.info(f"MOLT:Monitor - {self.provider} success in {latency_ms:.0f}ms")
                return result

            except asyncio.TimeoutError:
                molt_metrics.record_error(self.provider, "timeout")
                if attempt < self.retries - 1:
                    backoff = self.backoff_base ** attempt
                    logger.warning(f"MOLT:Observe - {self.provider} timeout, retry {attempt+1}/{self.retries} after {backoff}s")
                    await asyncio.sleep(backoff)
                else:
                    return "Timeout after multiple attempts. Try simpler question?"

            except aiohttp.ClientError as e:
                molt_metrics.record_error(self.provider, "network")
                if attempt < self.retries - 1:
                    backoff = self.backoff_base ** attempt
                    logger.warning(f"MOLT:Observe - {self.provider} network error, retry {attempt+1}/{self.retries} after {backoff}s")
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"MOLT:Log - {self.provider} network error after retries: {e}")
                    return "Network error. Check connection?"

            except json.JSONDecodeError as e:
                molt_metrics.record_error(self.provider, "parse")
                logger.error(f"MOLT:Log - {self.provider} JSON parse error: {e}")
                return "Response parsing error. Try again?"

            except Exception as e:
                molt_metrics.record_error(self.provider, type(e).__name__)
                logger.error(f"MOLT:Log - {self.provider} unexpected error: {type(e).__name__}: {e}")
                if attempt < self.retries - 1:
                    backoff = self.backoff_base ** attempt
                    await asyncio.sleep(backoff)
                else:
                    return f"Error ({type(e).__name__}). Try again?"

        return "Max retries exceeded"

    async def _call_provider(self, msg):
        """Call the appropriate LLM provider."""
        if self.provider == "xai":
            return await self._call_xai(msg)
        elif self.provider == "anthropic":
            return await self._call_anthropic(msg)
        elif self.provider == "openai":
            return await self._call_openai(msg)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _call_xai(self, msg):
        """Call XAI Grok via API."""
        if not self.api_key:
            raise ValueError("XAI API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "messages": [{"role": "user", "content": msg}],
            "model": "grok-3-turbo",
            "max_tokens": 1024
        }

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"XAI API error {resp.status}: {text[:200]}")

                data = await resp.json()
                return data["choices"][0]["message"]["content"]

    async def _call_anthropic(self, msg):
        """Call Anthropic Claude via clawdbot CLI."""
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")

        import base64
        msg_b64 = base64.b64encode(msg.encode("utf-8")).decode("ascii")
        cmd = f'export ANTHROPIC_API_KEY={self.api_key} && MSG=$(echo {msg_b64} | base64 -d) && clawdbot agent --message "$MSG" --agent main --json --local'

        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "clawdbot-gateway", "bash", "-c", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=self.request_timeout
        )

        output = stdout.decode("utf-8", errors="replace").strip()

        if stderr:
            stderr_text = stderr.decode("utf-8", errors="replace")
            if stderr_text.strip():
                logger.warning(f"MOLT:Log - clawdbot stderr: {stderr_text[:200]}")

        if not output:
            raise Exception("Empty response from clawdbot")

        data = json.loads(output)
        if "payloads" in data and len(data["payloads"]) > 0:
            return data["payloads"][0]["text"]
        raise Exception("No response payload from Claude")

    async def _call_openai(self, msg):
        """Call OpenAI via codex CLI."""
        proc = await asyncio.create_subprocess_exec(
            "npx", "@openai/codex", "exec",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            msg,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=60
        )

        output = stdout.decode("utf-8", errors="replace").strip()

        if stderr:
            error_output = stderr.decode("utf-8", errors="replace")
            if any(phrase in error_output for phrase in [
                "refresh_token_reused",
                "token_expired",
                "Please try signing in again",
                "Please log out and sign in again"
            ]):
                raise Exception("OpenAI auth expired. Admin needs to run: npx @openai/codex login")
            if error_output.strip():
                logger.warning(f"MOLT:Log - codex stderr: {error_output[:300]}")

        if output:
            return output
        raise Exception("No response from OpenAI CLI")


# Convenience functions for each bot
def create_friday_client():
    """Create Friday client (Anthropic with SOUL)."""
    return LLMClient("anthropic", "CLAWDFRIDAY_SOUL.md")


def create_matt_client():
    """Create Matt client (OpenAI with SOUL)."""
    return LLMClient("openai", "CLAWDMATT_SOUL.md")


def create_jarvis_client():
    """Create Jarvis client (XAI with SOUL)."""
    return LLMClient("xai", "CLAWDJARVIS_SOUL.md")
