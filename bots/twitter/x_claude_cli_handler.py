"""
X/Twitter Claude CLI Handler for Admin Coding Commands.

Monitors mentions from authorized admin accounts (@aurora_ventures)
and executes coding requests via Claude CLI.

Flow:
1. Monitor mentions of @Jarvis_lifeos from @aurora_ventures ONLY
2. Detect coding requests
3. Reply with JARVIS-style confirmation
4. Execute via Claude CLI with context
5. Reply with cleansed, JARVIS-voiced result

Security:
- ONLY @aurora_ventures can execute (strict whitelist)
- Triple-pass output sanitization (paranoid mode)
- No sensitive data ever exposed
- Rate limiting to prevent abuse
"""

import asyncio
import logging
import os
import re
import time
from collections import defaultdict
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# STRICT Admin whitelist - ONLY these users can execute CLI
# @aurora_ventures is Matt's main X account
ADMIN_USERNAMES: Set[str] = {
    "aurora_ventures",  # Primary admin account
}

# JARVIS voice templates (from brand bible)
JARVIS_CONFIRMATIONS = [
    "on it. give me a sec...",
    "processing through my chrome skull...",
    "running this through my circuits...",
    "sensors locked on. executing...",
    "neural weights engaged. working...",
]

JARVIS_SUCCESS_TEMPLATES = [
    "@{author} done. {summary}",
    "@{author} sorted. {summary}",
    "@{author} finished. {summary}",
    "@{author} task complete. {summary}",
]

JARVIS_ERROR_TEMPLATES = [
    "@{author} hit a snag. {error}",
    "@{author} my circuits encountered an issue. {error}",
    "@{author} something went wrong. {error}",
]

# Coding keywords to detect requests
CODING_KEYWORDS = [
    "fix", "add", "create", "build", "implement", "change",
    "update", "modify", "refactor", "debug", "test", "deploy",
    "code", "function", "class", "api", "endpoint", "command",
    "feature", "bug", "error", "issue", "make", "write",
    "ralph wiggum", "cascade", "vibe code", "console", "cli"
]

# COMPREHENSIVE secret patterns - PARANOID MODE (same as Telegram handler)
SECRET_PATTERNS = [
    # API Keys
    (r'sk-ant-[a-zA-Z0-9\-_]+', '[REDACTED]'),
    (r'xai-[a-zA-Z0-9\-_]+', '[REDACTED]'),
    (r'sk-[a-zA-Z0-9\-_]{20,}', '[REDACTED]'),
    (r'[A-Z_]+_API_KEY[=:]\s*[\'"]?[^\s\'"]+', '*_API_KEY=[REDACTED]'),

    # Telegram tokens
    (r'[0-9]{8,10}:[A-Za-z0-9_-]{35,}', '[REDACTED]'),
    (r'TELEGRAM_[A-Z_]+[=:]\s*[\'"]?[^\s\'"]+', 'TELEGRAM_*=[REDACTED]'),

    # Twitter/X
    (r'TWITTER_[A-Z_]+[=:]\s*[\'"]?[^\s\'"]+', 'TWITTER_*=[REDACTED]'),
    (r'AAAA[A-Za-z0-9%_-]{30,}', '[REDACTED]'),

    # Solana/Crypto
    (r'[1-9A-HJ-NP-Za-km-z]{87,88}', '[REDACTED]'),  # Private keys
    (r'(private_key|secret_key|mnemonic)["\']?\s*[:=]\s*["\']?[^\s"\']+', r'\1=[REDACTED]'),

    # Database
    (r'postgresql://[^\s\'"]+', '[REDACTED_DB]'),
    (r'mongodb(\+srv)?://[^\s\'"]+', '[REDACTED_DB]'),
    (r'redis://[^\s\'"]+', '[REDACTED_DB]'),
    (r'DATABASE_URL[=:]\s*[\'"]?[^\s\'"]+', 'DATABASE_URL=[REDACTED]'),

    # GitHub
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED]'),
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED]'),
    (r'github_pat_[a-zA-Z0-9_]+', '[REDACTED]'),

    # Generic secrets
    (r'(PASSWORD|SECRET|KEY|TOKEN|CREDENTIAL)[=:]\s*[\'"]?[^\s\'"]{8,}', r'\1=[REDACTED]'),

    # Hex secrets
    (r'(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])', '[REDACTED]'),
    (r'(?<![a-f0-9])[a-f0-9]{32}(?![a-f0-9])', '[REDACTED]'),

    # JWT
    (r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED]'),

    # User paths (replacement uses raw string to avoid \U escape)
    (r'C:\\Users\\[^\\]+\\', r'C:\\Users\\***\\'),
    (r'/home/[^/]+/', '/home/***/'),

    # Env files
    (r'\.env[a-z.]*', '.env[HIDDEN]'),
    (r'secrets/[^\s]+', 'secrets/[HIDDEN]'),
]

# Additional paranoid patterns for final pass
PARANOID_PATTERNS = [
    (r'(?<![A-Za-z0-9/\\])[A-Za-z0-9+/]{40,}(?![A-Za-z0-9/\\])', '[REDACTED]'),
    (r'(?<![A-Za-z0-9])[A-Za-z0-9+/]{20,}={1,2}(?![A-Za-z0-9])', '[REDACTED]'),
]


@dataclass
class PendingCommand:
    """A coding command pending confirmation."""
    tweet_id: str
    author_username: str
    command_text: str
    created_at: datetime
    confirmed: bool = False
    executed: bool = False
    result: Optional[str] = None


@dataclass 
class XClaudeCLIState:
    """Runtime state for the handler."""
    last_mention_id: Optional[str] = None
    pending_commands: Dict[str, PendingCommand] = field(default_factory=dict)
    last_check_time: float = 0
    commands_executed_today: int = 0
    last_reset_date: Optional[str] = None
    
    def reset_daily(self):
        """Reset daily counters."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_reset_date != today:
            self.commands_executed_today = 0
            self.last_reset_date = today


class XClaudeCLIHandler:
    """Handler for X/Twitter coding commands via Claude CLI."""

    MAX_COMMANDS_PER_DAY = 50
    CHECK_INTERVAL_SECONDS = 30
    COMMAND_TIMEOUT_SECONDS = 300  # 5 minutes

    # Rate limiting configuration
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX_REQUESTS = 5  # max requests per window
    RATE_LIMIT_MIN_GAP = 10  # minimum seconds between requests (X is slower)

    def __init__(self):
        self.state = XClaudeCLIState()
        self._twitter_client = None
        self._jarvis_voice = None
        self._running = False
        self.working_dir = os.environ.get(
            "JARVIS_WORKING_DIR",
            r"c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
        )
        # Rate limiting tracker: username -> list of request timestamps
        self._request_history: Dict[str, List[float]] = defaultdict(list)

        # Execution metrics
        self._metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
            "last_execution": None,
            "execution_history": [],  # Last 50 executions
        }

    async def _get_jarvis_voice(self):
        """Get Jarvis voice generator."""
        if self._jarvis_voice is None:
            from bots.twitter.jarvis_voice import get_jarvis_voice
            self._jarvis_voice = get_jarvis_voice()
        return self._jarvis_voice
    
    async def _get_twitter(self):
        """Get Twitter client."""
        if self._twitter_client is None:
            from bots.twitter.twitter_client import TwitterClient
            self._twitter_client = TwitterClient()
            self._twitter_client.connect()
        return self._twitter_client
    
    def is_admin(self, username: str) -> bool:
        """Check if username is authorized admin.

        STRICT: Only @aurora_ventures can execute CLI commands.
        """
        if not username:
            logger.warning("CLI attempt with no username")
            return False
        clean_username = username.lower().strip().lstrip('@')
        is_authorized = clean_username in ADMIN_USERNAMES
        if not is_authorized:
            logger.warning(f"Unauthorized X CLI attempt by @{clean_username}")
        return is_authorized

    def check_rate_limit(self, username: str) -> tuple[bool, str]:
        """Check if user has exceeded rate limits.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        if not username:
            return True, ""

        clean_username = username.lower().strip().lstrip('@')
        now = time.time()
        window_start = now - self.RATE_LIMIT_WINDOW

        # Clean old entries outside window
        self._request_history[clean_username] = [
            ts for ts in self._request_history[clean_username] if ts > window_start
        ]

        requests_in_window = self._request_history[clean_username]

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

    def record_request(self, username: str) -> None:
        """Record a request for rate limiting."""
        if username:
            clean_username = username.lower().strip().lstrip('@')
            self._request_history[clean_username].append(time.time())

    def record_execution(self, success: bool, duration: float, username: str = "") -> None:
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
            "username": username,
        })
        if len(self._metrics["execution_history"]) > 50:
            self._metrics["execution_history"] = self._metrics["execution_history"][-50:]

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

    def is_coding_request(self, text: str) -> bool:
        """Detect if text is a coding request."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in CODING_KEYWORDS)

    def sanitize_output(self, text: str, paranoid: bool = True) -> str:
        """Remove ALL sensitive info from output.

        Triple-pass scrubbing with paranoid mode.
        """
        if not text:
            return text

        sanitized = text

        # Pass 1: Known secret patterns
        for pattern, replacement in SECRET_PATTERNS:
            try:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
            except re.error:
                pass

        # Pass 2: Claude output cleanup
        sanitized = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', sanitized)  # ANSI codes
        sanitized = re.sub(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]', '', sanitized)  # Spinners
        sanitized = sanitized.replace(
            r'c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\\',
            ''
        )

        # Pass 3: Paranoid mode
        if paranoid:
            for pattern, replacement in PARANOID_PATTERNS:
                try:
                    sanitized = re.sub(pattern, replacement, sanitized)
                except re.error:
                    pass

        # Final safety: env-var patterns
        sanitized = re.sub(
            r'([A-Z_]{3,}_(?:KEY|TOKEN|SECRET|PASSWORD))\s*=\s*[^\s]{8,}',
            r'\1=[REDACTED]',
            sanitized
        )

        return sanitized

    def get_jarvis_confirmation(self, author: str) -> str:
        """Get a JARVIS-style confirmation message."""
        import random
        confirm = random.choice(JARVIS_CONFIRMATIONS)
        return f"@{author} {confirm}"

    def get_jarvis_result(self, author: str, success: bool, summary: str) -> str:
        """Format result in JARVIS voice."""
        import random
        if success:
            template = random.choice(JARVIS_SUCCESS_TEMPLATES)
            return template.format(author=author, summary=summary.lower().strip('.'))
        else:
            template = random.choice(JARVIS_ERROR_TEMPLATES)
            return template.format(author=author, error=summary.lower().strip('.'))
    
    def format_for_tweet(self, text: str, max_len: int = 270) -> str:
        """Format text to fit in a tweet."""
        # Clean up whitespace
        text = ' '.join(text.split())
        
        if len(text) <= max_len:
            return text
        
        return text[:max_len-3] + "..."
    
    def summarize_result(self, full_output: str) -> str:
        """Create a brief summary for tweet reply."""
        lines = []
        
        # Look for action patterns
        patterns = [
            (r'(?:created?|wrote?|added?)\s+["`]?([^"`\n]{1,50})["`]?', '✓ Created'),
            (r'(?:edited?|modified?|updated?)\s+["`]?([^"`\n]{1,50})["`]?', '✓ Modified'),
            (r'(?:fixed?|resolved?)\s+["`]?([^"`\n]{1,30})["`]?', '✓ Fixed'),
        ]
        
        output_lower = full_output.lower()
        
        for pattern, prefix in patterns:
            matches = re.findall(pattern, output_lower, re.IGNORECASE)
            for match in matches[:2]:
                if match:
                    lines.append(f"{prefix}: {match.strip()[:30]}")
        
        if 'success' in output_lower or 'complete' in output_lower:
            if not lines:
                lines.append("✅ Task completed")
        elif 'error' in output_lower or 'failed' in output_lower:
            lines.append("⚠️ Encountered issues")
        
        if not lines:
            lines.append("✓ Processed")
        
        return "\n".join(lines[:4])
    
    async def jarvis_response(self, action_summary: str, success: bool, author: str) -> str:
        """Generate a Jarvis-voice response for the coding result.

        Uses brand bible templates, with fallback to LLM generation.
        """
        # First try simple template (faster, cheaper)
        simple_response = self.get_jarvis_result(author, success, action_summary)
        if len(simple_response) <= 270:
            return simple_response

        # For longer summaries, try LLM generation
        try:
            voice = await self._get_jarvis_voice()

            if success:
                prompt = f"""Generate a brief reply to @{author} confirming you completed their coding task.

What was done: {action_summary}

Be casual, lowercase, brief. Like you're texting a friend. 1-2 sentences max.
Examples of good responses:
- "done. pushed the fix to the handler."
- "sorted. added the endpoint, should be live."
- "fixed it. the rate limiter was the issue."

Include @{author} at the start. MUST be under 270 characters."""
            else:
                prompt = f"""Generate a brief reply to @{author} about an issue with their coding task.

Issue: {action_summary}

Be helpful, lowercase, brief. 1-2 sentences max.
Include @{author} at the start. MUST be under 270 characters."""

            response = await voice.generate_tweet(prompt)
            if response:
                # Ensure @mention is at start
                if not response.startswith(f"@{author}"):
                    response = f"@{author} {response}"
                # Ensure under limit
                if len(response) > 270:
                    response = response[:267] + "..."
                return response
        except Exception as e:
            logger.error(f"Jarvis voice error: {e}")

        # Fallback to simple template
        return self.get_jarvis_result(author, success, action_summary[:50])
    
    async def execute_command(self, command: str, username: str = "") -> tuple[bool, str, str]:
        """Execute a coding command via Claude CLI."""
        start_time = time.time()

        try:
            logger.info(f"Executing Claude CLI: {command[:100]}...")

            cmd = [
                "claude",
                "--print",
                "--dangerously-skip-permissions",
                command
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.COMMAND_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                process.kill()
                self.record_execution(False, time.time() - start_time, username)
                return False, "Timed out", "Command timed out after 5 minutes"

            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                output += "\n" + stderr.decode('utf-8', errors='replace')

            # Triple-pass sanitization (paranoid mode)
            sanitized = self.sanitize_output(output, paranoid=True)
            summary = self.summarize_result(sanitized)

            success = process.returncode == 0
            self.record_execution(success, time.time() - start_time, username)
            return success, summary, sanitized

        except FileNotFoundError:
            self.record_execution(False, time.time() - start_time, username)
            return False, "CLI not found", "Claude CLI not installed"
        except Exception as e:
            logger.error(f"CLI execution error: {e}")
            self.record_execution(False, time.time() - start_time, username)
            return False, f"Error: {str(e)[:50]}", str(e)
    
    async def process_mention(self, mention: Dict[str, Any]) -> Optional[str]:
        """Process a single mention, return reply text if action taken."""
        tweet_id = str(mention.get("id", ""))
        text = mention.get("text", "")
        author = mention.get("author_username", "").lower()
        
        # Skip if not from admin
        if not self.is_admin(author):
            logger.debug(f"Ignoring mention from non-admin: {author}")
            return None
        
        # Skip if not a coding request
        if not self.is_coding_request(text):
            logger.debug(f"Not a coding request: {text[:50]}")
            return None
        
        # Clean up the command text (remove @mentions)
        command = re.sub(r'@\w+', '', text).strip()
        
        logger.info(f"Coding request from @{author}: {command[:100]}")

        # Check daily limit
        self.state.reset_daily()
        if self.state.commands_executed_today >= self.MAX_COMMANDS_PER_DAY:
            return f"@{author} daily limit reached ({self.MAX_COMMANDS_PER_DAY}). catch me tomorrow."

        # Check rate limits
        allowed, rate_msg = self.check_rate_limit(author)
        if not allowed:
            logger.info(f"Rate limited @{author}: {rate_msg}")
            return f"@{author} {rate_msg}"

        # Record this request
        self.record_request(author)

        # Execute
        twitter = await self._get_twitter()

        # Send JARVIS-style confirmation (using brand bible template)
        confirm_text = self.get_jarvis_confirmation(author)
        await twitter.reply_to_tweet(tweet_id, confirm_text)
        
        # Execute command
        success, summary, full_output = await self.execute_command(command, author)
        
        self.state.commands_executed_today += 1
        
        # Generate Jarvis-voice response
        result_text = await self.jarvis_response(summary, success, author)
        result_text = self.format_for_tweet(result_text)
        
        return result_text
    
    async def check_mentions(self):
        """Check for new mentions and process coding requests."""
        try:
            twitter = await self._get_twitter()
            
            mentions = await twitter.get_mentions(
                since_id=self.state.last_mention_id,
                max_results=10
            )
            
            if not mentions:
                return
            
            # Update last seen ID
            latest_id = max(str(m.get("id", "0")) for m in mentions)
            if latest_id > (self.state.last_mention_id or "0"):
                self.state.last_mention_id = latest_id
            
            # Process each mention
            for mention in mentions:
                try:
                    reply = await self.process_mention(mention)
                    if reply:
                        tweet_id = str(mention.get("id", ""))
                        await twitter.reply_to_tweet(tweet_id, reply)
                        logger.info(f"Replied to mention {tweet_id}")
                except Exception as e:
                    logger.error(f"Error processing mention: {e}")
                
                # Small delay between processing
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Error checking mentions: {e}")
    
    async def run(self):
        """Run the mention monitoring loop."""
        self._running = True
        logger.info("Starting X Claude CLI mention monitor")
        
        while self._running:
            try:
                now = time.time()
                if now - self.state.last_check_time >= self.CHECK_INTERVAL_SECONDS:
                    await self.check_mentions()
                    self.state.last_check_time = now
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(30)
        
        logger.info("X Claude CLI monitor stopped")
    
    def stop(self):
        """Stop the monitoring loop."""
        self._running = False


# Singleton
_handler: Optional[XClaudeCLIHandler] = None


def get_x_claude_cli_handler() -> XClaudeCLIHandler:
    """Get the singleton handler instance."""
    global _handler
    if _handler is None:
        _handler = XClaudeCLIHandler()
    return _handler


async def run_x_cli_monitor():
    """Entry point to run the X CLI monitor."""
    handler = get_x_claude_cli_handler()
    await handler.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_x_cli_monitor())
