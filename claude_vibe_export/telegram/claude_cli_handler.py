"""
Claude CLI Handler for Telegram Coding Commands.

Executes coding requests via the Claude CLI and returns cleansed responses.

Flow:
1. Receive coding command from Telegram
2. Send confirmation back to Telegram
3. Execute via `claude` CLI
4. Cleanse output of sensitive info
5. Send response back to Telegram

Security:
- Only admin users can execute
- All output is sanitized before returning
- No secrets/keys/passwords exposed
"""

import asyncio
import logging
import os
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Patterns to detect and redact secrets
SECRET_PATTERNS = [
    # API Keys
    (r'sk-ant-[a-zA-Z0-9\-_]+', '[REDACTED_ANTHROPIC_KEY]'),
    (r'xai-[a-zA-Z0-9\-_]+', '[REDACTED_XAI_KEY]'),
    (r'sk-[a-zA-Z0-9\-_]{20,}', '[REDACTED_API_KEY]'),
    
    # Tokens
    (r'[0-9]+:[A-Za-z0-9_-]{35,}', '[REDACTED_BOT_TOKEN]'),
    (r'AAAA[A-Za-z0-9%_-]{30,}', '[REDACTED_BEARER_TOKEN]'),
    
    # Private keys / Keypairs (base58/base64)
    (r'[1-9A-HJ-NP-Za-km-z]{87,88}', '[REDACTED_PRIVATE_KEY]'),
    (r'-----BEGIN[^-]+-----[^-]+-----END[^-]+-----', '[REDACTED_PEM_KEY]'),
    
    # Passwords in env files
    (r'(PASSWORD|SECRET|KEY|TOKEN)=\S+', r'\1=[REDACTED]'),
    (r'(password|secret|key|token)["\']?\s*[:=]\s*["\']?[^\s"\']+', r'\1=[REDACTED]'),
    
    # Wallet secrets
    (r'(private_key|secret_key|mnemonic)["\']?\s*[:=]\s*["\']?[^\s"\']+', r'\1=[REDACTED]'),
    
    # GitHub tokens
    (r'ghp_[a-zA-Z0-9]{30,}', '[REDACTED_GITHUB_TOKEN]'),
    (r'gho_[a-zA-Z0-9]{30,}', '[REDACTED_GITHUB_TOKEN]'),
    
    # Hex secrets (64 char = 256 bit)
    (r'[a-f0-9]{64}', '[REDACTED_HEX_SECRET]'),
    
    # Connection strings
    (r'postgresql://[^\s]+', '[REDACTED_DB_URL]'),
    (r'mongodb(\+srv)?://[^\s]+', '[REDACTED_DB_URL]'),
    (r'redis://[^\s]+', '[REDACTED_DB_URL]'),
    
    # File paths that might contain sensitive info
    (r'\.env[^\s]*', '.env[HIDDEN]'),
]

# Additional patterns specific to Claude CLI output
CLAUDE_OUTPUT_PATTERNS = [
    # Remove ANSI escape codes
    (r'\x1b\[[0-9;]*[mGKHF]', ''),
    # Remove progress spinners
    (r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]', ''),
]


class ClaudeCLIHandler:
    """Handler for executing coding commands via Claude CLI."""
    
    def __init__(self, admin_user_ids: list[int] = None):
        admin_str = os.environ.get("TELEGRAM_ADMIN_IDS", "")
        self.admin_ids = admin_user_ids or [
            int(x.strip()) for x in admin_str.split(",") if x.strip().isdigit()
        ]
        self.working_dir = os.environ.get(
            "WORKING_DIR",
            os.getcwd()
        )
        self._active_process: Optional[asyncio.subprocess.Process] = None
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is authorized."""
        return user_id in self.admin_ids
    
    def sanitize_output(self, text: str) -> str:
        """Remove ALL sensitive information from output."""
        if not text:
            return text
        
        sanitized = text
        
        # Apply secret redaction patterns
        for pattern, replacement in SECRET_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # Apply Claude output cleanup patterns
        for pattern, replacement in CLAUDE_OUTPUT_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized)
        
        # Extra safety: redact long alphanumeric strings that look like keys
        sanitized = re.sub(
            r'(?<![/\\])[A-Za-z0-9+/]{40,}(?![/\\])',
            '[REDACTED_LONG_SECRET]',
            sanitized
        )
        
        return sanitized
    
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
        send_update: callable = None
    ) -> Tuple[bool, str, str]:
        """
        Execute a coding command via Claude CLI.
        
        Args:
            prompt: The coding request
            user_id: Telegram user ID
            send_update: Async callback to send updates to Telegram
            
        Returns:
            Tuple of (success, summary, full_output)
        """
        if not self.is_admin(user_id):
            logger.warning(f"Unauthorized Claude CLI attempt by user {user_id}")
            return False, "Access denied", "Admin only."
        
        try:
            logger.info(f"Executing Claude CLI for admin {user_id}: {prompt[:100]}...")
            
            # Send processing confirmation
            if send_update:
                await send_update("🔄 Processing your request...")
            
            # Build the claude command
            cmd = [
                "claude",
                "--print",  # Non-interactive, print output
                "--dangerously-skip-permissions",  # Allow file operations
                prompt
            ]
            
            # Execute with timeout
            self._active_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    self._active_process.communicate(),
                    timeout=300.0  # 5 minute timeout for complex tasks
                )
            except asyncio.TimeoutError:
                self._active_process.kill()
                return False, "Timed out (5 min limit)", "Command execution timed out."
            finally:
                self._active_process = None
            
            # Combine output
            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                if output:
                    output += "\n"
                output += stderr.decode('utf-8', errors='replace')
            
            # Sanitize
            sanitized = self.sanitize_output(output)
            
            # Generate summary
            summary = self.summarize_action(sanitized)
            
            # Format for Telegram
            formatted = self.format_for_telegram(sanitized)
            
            success = True  # If we got here without exception
            
            return success, summary, formatted
            
        except FileNotFoundError:
            logger.error("Claude CLI not found - is it installed?")
            return False, "Claude CLI not found", "Please ensure `claude` CLI is installed and in PATH."
        except Exception as e:
            logger.error(f"Claude CLI execution error: {e}")
            return False, f"Error: {str(e)[:100]}", str(e)
    
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
