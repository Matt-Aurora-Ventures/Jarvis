"""
Claude CLI Handler for Telegram Coding Commands.

Executes coding requests via the Claude CLI and returns cleansed responses.

Flow:
1. Receive coding command from Telegram
2. Send confirmation back to Telegram (JARVIS voice)
3. Execute via `claude` CLI with conversation context
4. Cleanse output of sensitive info
5. Send response back to Telegram (JARVIS voice, brand bible)

Security:
- Only admin users can execute (@matthaynes88)
- All output is sanitized before returning
- No secrets/keys/passwords exposed
- Multi-layer scrubbing with paranoid mode
"""

import asyncio
import logging
import os
import re
import time
from typing import Optional, Tuple, List, Dict
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

# JARVIS voice templates (from brand bible)
JARVIS_CONFIRMATIONS = [
    "on it. give me a sec...",
    "processing through my chrome skull...",
    "running this through my circuits...",
    "sensors locked on. executing...",
    "neural weights engaged. working on it...",
]

JARVIS_SUCCESS_RESPONSES = [
    "done. {summary}",
    "sorted. {summary}",
    "finished. {summary}",
    "task complete. {summary}",
    "executed successfully. {summary}",
]

JARVIS_ERROR_RESPONSES = [
    "hit a snag. {error}",
    "my circuits encountered an issue. {error}",
    "something went wrong. {error}",
    "task failed. {error}",
]

# COMPREHENSIVE secret patterns - PARANOID MODE
SECRET_PATTERNS = [
    # ============== API Keys ==============
    (r'sk-ant-[a-zA-Z0-9\-_]+', '[REDACTED]'),
    (r'xai-[a-zA-Z0-9\-_]+', '[REDACTED]'),
    (r'sk-[a-zA-Z0-9\-_]{20,}', '[REDACTED]'),
    (r'ANTHROPIC_API_KEY[=:]\s*[\'"]?[^\s\'"]+', 'ANTHROPIC_API_KEY=[REDACTED]'),
    (r'XAI_API_KEY[=:]\s*[\'"]?[^\s\'"]+', 'XAI_API_KEY=[REDACTED]'),
    (r'OPENAI_API_KEY[=:]\s*[\'"]?[^\s\'"]+', 'OPENAI_API_KEY=[REDACTED]'),
    (r'GROQ_API_KEY[=:]\s*[\'"]?[^\s\'"]+', 'GROQ_API_KEY=[REDACTED]'),

    # ============== Telegram ==============
    (r'[0-9]{8,10}:[A-Za-z0-9_-]{35,}', '[REDACTED_BOT_TOKEN]'),
    (r'TELEGRAM_BOT_TOKEN[=:]\s*[\'"]?[^\s\'"]+', 'TELEGRAM_BOT_TOKEN=[REDACTED]'),
    (r'TELEGRAM_ADMIN_ID[S]?[=:]\s*[\'"]?[^\s\'"]+', 'TELEGRAM_ADMIN_IDS=[REDACTED]'),

    # ============== Twitter/X ==============
    (r'TWITTER_[A-Z_]+[=:]\s*[\'"]?[^\s\'"]+', r'TWITTER_*=[REDACTED]'),
    (r'AAAA[A-Za-z0-9%_-]{30,}', '[REDACTED]'),

    # ============== Solana/Crypto ==============
    (r'[1-9A-HJ-NP-Za-km-z]{87,88}', '[REDACTED_PRIVATE_KEY]'),  # Base58 private key
    (r'[1-9A-HJ-NP-Za-km-z]{43,44}', '[POSSIBLE_WALLET]'),  # Base58 public key (flag but don't redact)
    (r'-----BEGIN[^-]+-----[\s\S]+?-----END[^-]+-----', '[REDACTED_PEM]'),
    (r'(private_key|secret_key|mnemonic|seed_phrase)["\']?\s*[:=]\s*["\']?[^\s"\']+', r'\1=[REDACTED]'),
    (r'SOLANA_PRIVATE_KEY[=:]\s*[\'"]?[^\s\'"]+', 'SOLANA_PRIVATE_KEY=[REDACTED]'),
    (r'WALLET_SECRET[=:]\s*[\'"]?[^\s\'"]+', 'WALLET_SECRET=[REDACTED]'),

    # ============== Database ==============
    (r'postgresql://[^\s\'"]+', '[REDACTED_DB_URL]'),
    (r'mongodb(\+srv)?://[^\s\'"]+', '[REDACTED_DB_URL]'),
    (r'redis://[^\s\'"]+', '[REDACTED_DB_URL]'),
    (r'DATABASE_URL[=:]\s*[\'"]?[^\s\'"]+', 'DATABASE_URL=[REDACTED]'),

    # ============== GitHub ==============
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED]'),
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED]'),
    (r'ghr_[a-zA-Z0-9]{36}', '[REDACTED]'),
    (r'github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}', '[REDACTED]'),
    (r'GITHUB_TOKEN[=:]\s*[\'"]?[^\s\'"]+', 'GITHUB_TOKEN=[REDACTED]'),

    # ============== Generic Secrets ==============
    (r'(PASSWORD|SECRET|KEY|TOKEN|CREDENTIAL|AUTH)[=:]\s*[\'"]?[^\s\'"]{8,}[\'"]?', r'\1=[REDACTED]'),
    (r'(password|secret|key|token|credential|auth)["\']?\s*[:=]\s*["\']?[^\s"\']{8,}', r'\1=[REDACTED]'),

    # ============== Hex Secrets ==============
    (r'(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])', '[REDACTED_HEX]'),  # 256-bit hex
    (r'(?<![a-f0-9])[a-f0-9]{32}(?![a-f0-9])', '[REDACTED_HEX]'),  # 128-bit hex (UUIDs are ok)

    # ============== JWT Tokens ==============
    (r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED_JWT]'),

    # ============== AWS ==============
    (r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]'),
    (r'aws_secret_access_key[=:]\s*[\'"]?[^\s\'"]+', 'aws_secret_access_key=[REDACTED]'),

    # ============== Environment Files ==============
    (r'\.env[a-z.]*', '.env[HIDDEN]'),
    (r'secrets/[^\s]+', 'secrets/[HIDDEN]'),
    (r'credentials[^\s]*\.json', 'credentials[HIDDEN].json'),

    # ============== IP Addresses (Optional - might be useful) ==============
    # (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP_HIDDEN]'),

    # ============== User Paths (raw strings for Windows escapes) ==============
    (r'C:\\Users\\[^\\]+\\', r'C:\\Users\\***\\'),
    (r'/home/[^/]+/', '/home/***/')
]

# Additional paranoid patterns for final pass
PARANOID_PATTERNS = [
    # Long alphanumeric strings that look like secrets
    (r'(?<![A-Za-z0-9/\\])[A-Za-z0-9+/]{40,}(?![A-Za-z0-9/\\])', '[REDACTED_LONG_SECRET]'),
    # Base64 encoded data
    (r'(?<![A-Za-z0-9])[A-Za-z0-9+/]{20,}={1,2}(?![A-Za-z0-9])', '[REDACTED_BASE64]'),
]

# Additional patterns specific to Claude CLI output
CLAUDE_OUTPUT_PATTERNS = [
    # Remove ANSI escape codes
    (r'\x1b\[[0-9;]*[mGKHF]', ''),
    # Remove progress spinners
    (r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]', ''),
    # Simplify file paths
    (r'c:\\Users\\lucid\\OneDrive\\Desktop\\Projects\\Jarvis\\', ''),
    (r'/home/[^/]+/', '~/'),
]


class ClaudeCLIHandler:
    """Handler for executing coding commands via Claude CLI.

    Security: Only authorized admin (@matthaynes88) can execute.
    All output is triple-scrubbed before returning.
    """

    # Known Claude CLI locations
    CLAUDE_PATHS = [
        r"C:\Users\lucid\AppData\Roaming\npm\claude.cmd",
        r"C:\Users\lucid\AppData\Roaming\npm\claude",
        "claude",  # fallback to PATH
    ]

    # Strict admin whitelist - ONLY these users can execute CLI
    ADMIN_WHITELIST = {
        8527130908,  # Matt (@matthaynes88)
    }

    # Telegram usernames allowed (as backup check)
    ADMIN_USERNAMES = {
        "matthaynes88",
    }

    # Rate limiting configuration
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX_REQUESTS = 5  # max requests per window
    RATE_LIMIT_MIN_GAP = 5  # minimum seconds between requests

    # Auto-retry configuration
    MAX_RETRIES = 2
    RETRY_BASE_DELAY = 2  # seconds
    TRANSIENT_ERROR_PATTERNS = [
        "connection",
        "timeout",
        "network",
        "temporarily unavailable",
        "retry",
        "eagain",  # lowercase for case-insensitive match
        "econnrefused",
        "econnreset",
    ]

    def __init__(self, admin_user_ids: list[int] = None):
        # Use strict whitelist, ignore env var for CLI execution
        self.admin_ids = set(self.ADMIN_WHITELIST)
        if admin_user_ids:
            # Allow additional admins only if explicitly passed
            self.admin_ids.update(admin_user_ids)

        self.working_dir = os.environ.get(
            "JARVIS_WORKING_DIR",
            r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
        )
        self._active_process: Optional[asyncio.subprocess.Process] = None
        self._claude_path = self._find_claude()
        self._conversation_context: List[Dict] = []

        # Import memory bridge for context
        try:
            from core.telegram_console_bridge import get_console_bridge
            self._bridge = get_console_bridge()
        except ImportError:
            self._bridge = None
            logger.warning("Console bridge not available - no conversation context")

        # Rate limiting tracker: user_id -> list of request timestamps
        self._request_history: Dict[int, List[float]] = defaultdict(list)

        # Execution metrics
        self._metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
            "last_execution": None,
            "execution_history": [],  # Last 50 executions
        }

        # Command queue for serialized execution
        self._execution_lock = asyncio.Lock()
        self._queue_depth = 0
        self._max_queue_depth = 3  # Max commands waiting
        self._pending_commands: List[Dict[str, Any]] = []  # Track pending commands

    def _find_claude(self) -> str:
        """Find the Claude CLI executable."""
        import shutil
        for path in self.CLAUDE_PATHS:
            if os.path.exists(path):
                return path
        # Try shutil.which as last resort
        found = shutil.which("claude")
        return found or "claude"
    
    def is_admin(self, user_id: int, username: str = None) -> bool:
        """Check if user is authorized for CLI execution.

        Uses strict whitelist - only @matthaynes88.
        """
        if user_id in self.admin_ids:
            return True
        if username and username.lower().lstrip('@') in self.ADMIN_USERNAMES:
            logger.info(f"Admin authorized by username: {username}")
            return True
        logger.warning(f"Unauthorized CLI attempt: user_id={user_id}, username={username}")
        return False

    def check_rate_limit(self, user_id: int) -> Tuple[bool, str]:
        """Check if user has exceeded rate limits.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        now = time.time()
        window_start = now - self.RATE_LIMIT_WINDOW

        # Clean old entries outside window
        self._request_history[user_id] = [
            ts for ts in self._request_history[user_id] if ts > window_start
        ]

        requests_in_window = self._request_history[user_id]

        # Check minimum gap between requests
        if requests_in_window:
            time_since_last = now - requests_in_window[-1]
            if time_since_last < self.RATE_LIMIT_MIN_GAP:
                wait_time = self.RATE_LIMIT_MIN_GAP - time_since_last
                return False, f"slow down. wait {wait_time:.0f}s between requests."

        # Check max requests per window
        if len(requests_in_window) >= self.RATE_LIMIT_MAX_REQUESTS:
            return False, f"rate limit hit. max {self.RATE_LIMIT_MAX_REQUESTS} requests per minute."

        return True, ""

    def record_request(self, user_id: int) -> None:
        """Record a request for rate limiting."""
        self._request_history[user_id].append(time.time())

    def is_transient_error(self, error_msg: str) -> bool:
        """Check if error is likely transient and worth retrying."""
        error_lower = error_msg.lower()
        return any(pattern in error_lower for pattern in self.TRANSIENT_ERROR_PATTERNS)

    def record_execution(self, success: bool, duration: float, user_id: int = 0) -> None:
        """Record execution metrics."""
        self._metrics["total_executions"] += 1
        if success:
            self._metrics["successful_executions"] += 1
        else:
            self._metrics["failed_executions"] += 1
        self._metrics["total_execution_time"] += duration
        self._metrics["last_execution"] = time.time()

        # Keep last 50 executions
        self._metrics["execution_history"].append({
            "timestamp": time.time(),
            "success": success,
            "duration": duration,
            "user_id": user_id,
        })
        if len(self._metrics["execution_history"]) > 50:
            self._metrics["execution_history"] = self._metrics["execution_history"][-50:]

    async def _run_cli_with_retry(
        self,
        cmd: List[str],
        timeout: float = 180.0
    ) -> Tuple[bool, str, str]:
        """Run CLI command with retry for transient failures.

        Returns:
            Tuple of (success, stdout, stderr)
        """
        last_error = ""

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                if attempt > 0:
                    # Exponential backoff
                    delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.info(f"Retry attempt {attempt} after {delay}s delay...")
                    await asyncio.sleep(delay)

                self._active_process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.working_dir,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        self._active_process.communicate(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    self._active_process.kill()
                    last_error = "timeout"
                    if attempt < self.MAX_RETRIES:
                        continue
                    return False, "", "Command execution timed out."
                finally:
                    self._active_process = None

                stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
                stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""

                # Check for transient errors in output
                combined = stdout_str + stderr_str
                if self.is_transient_error(combined) and attempt < self.MAX_RETRIES:
                    last_error = combined[:100]
                    continue

                return True, stdout_str, stderr_str

            except Exception as e:
                error_str = str(e)
                if self.is_transient_error(error_str) and attempt < self.MAX_RETRIES:
                    last_error = error_str[:100]
                    continue
                raise

        # All retries exhausted
        return False, "", f"Failed after {self.MAX_RETRIES} retries. Last error: {last_error}"

    def get_metrics(self) -> Dict:
        """Get execution metrics summary."""
        total = self._metrics["total_executions"]
        if total == 0:
            return {
                "total": 0,
                "success_rate": "N/A",
                "avg_duration": "N/A",
                "last_execution": "Never",
            }

        success_rate = (self._metrics["successful_executions"] / total) * 100
        avg_duration = self._metrics["total_execution_time"] / total

        last_exec = self._metrics["last_execution"]
        if last_exec:
            last_exec_str = datetime.fromtimestamp(last_exec).strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_exec_str = "Never"

        return {
            "total": total,
            "successful": self._metrics["successful_executions"],
            "failed": self._metrics["failed_executions"],
            "success_rate": f"{success_rate:.1f}%",
            "avg_duration": f"{avg_duration:.1f}s",
            "last_execution": last_exec_str,
        }

    def get_queue_status(self) -> Dict:
        """Get current queue status."""
        return {
            "depth": self._queue_depth,
            "max_depth": self._max_queue_depth,
            "pending": list(self._pending_commands),  # Copy to avoid mutation
            "is_locked": self._execution_lock.locked(),
        }

    def sanitize_output(self, text: str, paranoid: bool = True) -> str:
        """Remove ALL sensitive information from output.

        Triple-pass scrubbing:
        1. Known secret patterns
        2. Claude output cleanup
        3. Paranoid mode (catch anything that looks secret-ish)
        """
        if not text:
            return text

        sanitized = text

        # Pass 1: Apply known secret patterns
        for pattern, replacement in SECRET_PATTERNS:
            try:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
            except re.error as e:
                logger.warning(f"Regex error in pattern: {e}")

        # Pass 2: Claude output cleanup
        for pattern, replacement in CLAUDE_OUTPUT_PATTERNS:
            try:
                sanitized = re.sub(pattern, replacement, sanitized)
            except re.error:
                pass

        # Pass 3: Paranoid mode - catch anything that looks like a secret
        if paranoid:
            for pattern, replacement in PARANOID_PATTERNS:
                try:
                    sanitized = re.sub(pattern, replacement, sanitized)
                except re.error:
                    pass

        # Final safety: scan for any remaining env-var-like patterns
        sanitized = re.sub(
            r'([A-Z_]{3,}_(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL))\s*=\s*[^\s]{8,}',
            r'\1=[REDACTED]',
            sanitized
        )

        return sanitized

    def get_jarvis_confirmation(self) -> str:
        """Get a random JARVIS-style confirmation message."""
        import random
        return random.choice(JARVIS_CONFIRMATIONS)

    def get_jarvis_response(self, success: bool, summary: str) -> str:
        """Format response in JARVIS voice."""
        import random
        if success:
            template = random.choice(JARVIS_SUCCESS_RESPONSES)
            return template.format(summary=summary.lower().strip('.'))
        else:
            template = random.choice(JARVIS_ERROR_RESPONSES)
            return template.format(error=summary.lower().strip('.'))

    def get_conversation_context(self, user_id: int, current_request: str = "", limit: int = 10) -> str:
        """Get enhanced conversation context for better CLI execution.

        Uses the bridge's enhanced context builder which includes:
        - Recent conversation
        - Relevant learnings from past sessions
        - User preferences
        - Standing instructions
        """
        if not self._bridge:
            return ""

        try:
            # Use enhanced context builder if available
            if hasattr(self._bridge.memory, 'build_enhanced_context'):
                return self._bridge.memory.build_enhanced_context(user_id, current_request)

            # Fallback to basic context
            context = self._bridge.memory.get_recent_context(user_id, limit=limit)
            if not context:
                return ""

            # Format context for Claude CLI
            context_lines = []
            for msg in context[-limit:]:
                role = msg.get('role', 'user')
                content = msg.get('content', '')[:300]
                context_lines.append(f"[{role}]: {content}")

            return "\n".join(context_lines)
        except Exception as e:
            logger.warning(f"Failed to get context: {e}")
            return ""
    
    def format_for_telegram(self, text: str) -> str:
        """Format output for Telegram display."""
        # Truncate if too long
        max_len = 3800  # Leave room for formatting
        if len(text) > max_len:
            text = text[:max_len] + "\n\n[... truncated ...]"
        
        # Escape HTML entities
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        return text
    
    def summarize_action(self, full_output: str) -> str:
        """Create a human-readable summary of what was done."""
        summary_lines = []
        
        # Look for common action patterns in output
        patterns = [
            (r'(?:created?|wrote?|added?)\s+(?:file\s+)?["`]?([^"`\n]+)["`]?', 'Created'),
            (r'(?:edited?|modified?|updated?|changed?)\s+["`]?([^"`\n]+)["`]?', 'Modified'),
            (r'(?:deleted?|removed?)\s+["`]?([^"`\n]+)["`]?', 'Deleted'),
            (r'(?:installed?|added? dependency)\s+["`]?([^"`\n]+)["`]?', 'Installed'),
            (r'(?:ran|executed?|running)\s+["`]?([^"`\n]+)["`]?', 'Ran'),
            (r'(?:fixed?|resolved?)\s+(?:bug|issue|error)?\s*["`]?([^"`\n]*)["`]?', 'Fixed'),
        ]
        
        output_lower = full_output.lower()
        
        for pattern, action in patterns:
            matches = re.findall(pattern, output_lower, re.IGNORECASE)
            for match in matches[:3]:  # Limit to 3 per action type
                if match and len(match) < 100:
                    summary_lines.append(f"• {action}: {match.strip()}")
        
        # Look for success/completion indicators
        if 'success' in output_lower or 'complete' in output_lower or 'done' in output_lower:
            summary_lines.append("✅ Completed successfully")
        elif 'error' in output_lower or 'failed' in output_lower:
            summary_lines.append("⚠️ Encountered errors - check details")
        
        if not summary_lines:
            summary_lines.append("• Task processed")
        
        return "\n".join(summary_lines[:10])  # Max 10 lines
    
    async def execute(
        self,
        prompt: str,
        user_id: int,
        username: str = None,
        send_update: callable = None,
        include_context: bool = True
    ) -> Tuple[bool, str, str]:
        """
        Execute a coding command via Claude CLI.

        Args:
            prompt: The coding request
            user_id: Telegram user ID
            username: Telegram username for backup auth check
            send_update: Async callback to send updates to Telegram
            include_context: Whether to include conversation history

        Returns:
            Tuple of (success, jarvis_summary, full_output)
        """
        if not self.is_admin(user_id, username):
            logger.warning(f"Unauthorized Claude CLI attempt by user {user_id} ({username})")
            return False, "access denied. admin only.", "Unauthorized."

        # Check rate limits
        allowed, rate_msg = self.check_rate_limit(user_id)
        if not allowed:
            logger.info(f"Rate limited user {user_id}: {rate_msg}")
            return False, rate_msg, "Rate limited."

        # Check queue depth
        if self._queue_depth >= self._max_queue_depth:
            logger.info(f"Queue full ({self._queue_depth}/{self._max_queue_depth})")
            return False, "queue full. try again in a moment.", "Command queue full."

        # Record this request
        self.record_request(user_id)

        # Track execution time
        start_time = time.time()

        # Add to pending queue
        pending_entry = {
            "user_id": user_id,
            "prompt_preview": prompt[:50] + "..." if len(prompt) > 50 else prompt,
            "queued_at": datetime.now().isoformat(),
        }
        self._pending_commands.append(pending_entry)
        self._queue_depth += 1

        # Acquire execution lock (serialize CLI calls)
        async with self._execution_lock:
            try:
                logger.info(f"Executing Claude CLI for admin {user_id}: {prompt[:100]}...")

                # Send JARVIS-style confirmation
                if send_update:
                    jarvis_confirm = self.get_jarvis_confirmation()
                    await send_update(f"🤖 {jarvis_confirm}")

                # Build enhanced prompt with context (includes learnings & preferences)
                enhanced_prompt = prompt

                if include_context and self._bridge:
                    context = self.get_conversation_context(user_id, current_request=prompt, limit=5)
                    if context:
                        enhanced_prompt = f"""## Context
{context}

## Current Request
{prompt}

Execute this request. Be concise in your response. Follow any standing instructions."""

                # Build the claude command
                logger.info(f"Using Claude CLI at: {self._claude_path}")
                cmd = [
                    self._claude_path,
                    "--print",  # Non-interactive, print output
                    "--dangerously-skip-permissions",  # Allow file operations
                    enhanced_prompt
                ]

                # Execute with retry for transient failures
                cli_success, stdout_str, stderr_str = await self._run_cli_with_retry(cmd, timeout=180.0)

                if not cli_success:
                    self.record_execution(False, time.time() - start_time, user_id)
                    jarvis_error = self.get_jarvis_response(False, stderr_str or "execution failed")
                    return False, jarvis_error, stderr_str or "Command execution failed."

                # Combine output
                output = stdout_str
                if stderr_str:
                    if output:
                        output += "\n"
                    output += stderr_str

                # Triple-sanitize (paranoid mode)
                sanitized = self.sanitize_output(output, paranoid=True)

                # Generate summary
                summary = self.summarize_action(sanitized)

                # Format for Telegram
                formatted = self.format_for_telegram(sanitized)

                # Determine success
                success = self._active_process is None

                # Store in memory for context and extract learnings
                if self._bridge:
                    try:
                        # Store the result
                        self._bridge.memory.add_message(
                            user_id,
                            username or "admin",
                            "assistant",
                            f"[CLI Result] {summary}"
                        )

                        # Extract learnings from successful results
                        if success and hasattr(self._bridge.memory, 'extract_learnings_from_result'):
                            self._bridge.memory.extract_learnings_from_result(
                                sanitized,
                                topic="coding"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to store in memory: {e}")

                # Format JARVIS response
                jarvis_summary = self.get_jarvis_response(success, summary)

                # Record execution metrics
                self.record_execution(success, time.time() - start_time, user_id)

                return success, jarvis_summary, formatted

            except FileNotFoundError:
                logger.error(f"Claude CLI not found at: {self._claude_path}")
                self.record_execution(False, time.time() - start_time, user_id)
                return False, "Claude CLI not found", f"Tried: {self._claude_path}. Install via: npm install -g @anthropic-ai/claude-code"
            except Exception as e:
                logger.error(f"Claude CLI execution error: {e}")
                self.record_execution(False, time.time() - start_time, user_id)
                return False, f"Error: {str(e)[:100]}", str(e)
            finally:
                # Clean up queue tracking
                self._queue_depth = max(0, self._queue_depth - 1)
                if pending_entry in self._pending_commands:
                    self._pending_commands.remove(pending_entry)

    def cancel(self):
        """Cancel any active execution."""
        if self._active_process:
            self._active_process.kill()
            logger.info("Cancelled active Claude CLI process")


# Singleton instance
_handler: Optional[ClaudeCLIHandler] = None


def get_claude_cli_handler() -> ClaudeCLIHandler:
    """Get the singleton ClaudeCLIHandler instance."""
    global _handler
    if _handler is None:
        _handler = ClaudeCLIHandler()
    return _handler
