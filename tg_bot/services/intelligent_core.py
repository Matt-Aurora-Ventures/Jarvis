"""
Jarvis Intelligent Core - Multi-Model AI Intelligence.

This module provides Jarvis's AI capabilities:
- Claude via Clawdbot CLI (routes through Clawdbot's API credits)
- Grok/xAI integration for sentiment and market analysis
- Context file loader (SOUL.md, AGENTS.md, USER.md, MEMORY.md)
- Skill search and loading for specialized knowledge

Updated: 2026-01-30
Author: ClawdMatt
Note: Claude now routes through Clawdbot CLI to share credits
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
import hashlib

logger = logging.getLogger(__name__)

# Base path for Jarvis context files
JARVIS_ROOT = Path("/root/clawd/Jarvis")
JARVIS_SKILLS = JARVIS_ROOT / "skills"


@dataclass
class ContextFiles:
    """Container for loaded context files."""
    soul: str = ""
    agents: str = ""
    user: str = ""
    memory: str = ""
    tools: str = ""
    heartbeat: str = ""
    gate: str = ""
    daily_memory: str = ""  # Today's memory file
    loaded_at: Optional[datetime] = None
    
    def get_system_context(self) -> str:
        """Build the full system context from loaded files."""
        parts = []
        
        if self.soul:
            parts.append("# SOUL.md - Core Identity\n" + self.soul)
        if self.agents:
            parts.append("\n\n# AGENTS.md - Workspace Rules\n" + self.agents)
        if self.user:
            parts.append("\n\n# USER.md - About the User\n" + self.user)
        if self.tools:
            parts.append("\n\n# TOOLS.md - Local Notes\n" + self.tools)
        if self.memory:
            parts.append("\n\n# MEMORY.md - Long-term Memory (Summary)\n" + self._truncate(self.memory, 2000))
        if self.daily_memory:
            parts.append("\n\n# Today's Notes\n" + self._truncate(self.daily_memory, 1500))
        if self.gate:
            parts.append("\n\n# Current State (GATE.md)\n" + self._truncate(self.gate, 1000))
            
        return "\n".join(parts)
    
    def _truncate(self, text: str, max_chars: int) -> str:
        """Truncate text to max_chars with indicator."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n\n[... truncated ...]"


@dataclass 
class SkillMatch:
    """A matched skill from search."""
    name: str
    description: str
    path: Path
    score: float
    content: Optional[str] = None


class IntelligentCore:
    """
    Jarvis's intelligent core.
    
    Multi-model AI with:
    - Claude via Clawdbot CLI (shares Clawdbot API credits)
    - Grok for quick sentiment and market analysis
    - Local context loading for personality and memory
    - Skill search for specialized knowledge
    """
    
    # Clawdbot CLI path (routes through Clawdbot Gateway for credits)
    CLAWDBOT_CLI_PATH = "/usr/local/bin/clawdbot"
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        xai_api_key: Optional[str] = None,
        claude_model: str = "claude-sonnet-4-20250514",
        grok_model: str = "grok-3",
    ):
        # Note: anthropic_api_key kept for backwards compat but not used (CLI instead)
        self.xai_api_key = xai_api_key or os.getenv("XAI_API_KEY", "")
        self.claude_model = claude_model
        self.grok_model = grok_model
        
        # Clients (lazy initialized)
        self._openai_client = None  # For xAI
        self._claude_cli_path: Optional[str] = None
        
        # Context cache
        self._context_files: Optional[ContextFiles] = None
        self._context_loaded_at: Optional[datetime] = None
        self._context_cache_ttl = 300  # 5 minutes
        
        # Skill index (name -> description)
        self._skill_index: Dict[str, str] = {}
        self._skill_index_loaded = False
        
        logger.info("IntelligentCore initialized (Claude via Clawdbot CLI)")
    
    # =========================================================================
    # CLIENT MANAGEMENT
    # =========================================================================
    
    def _get_clawdbot_cli_path(self) -> Optional[str]:
        """Find Clawdbot CLI path (routes Claude through Clawdbot credits)."""
        if self._claude_cli_path:
            return self._claude_cli_path
        
        # Check environment variable first
        env_path = os.getenv("CLAWDBOT_CLI_PATH")
        if env_path:
            resolved = shutil.which(env_path)
            if resolved:
                self._claude_cli_path = resolved
                logger.info(f"Clawdbot CLI from env: {resolved}")
                return resolved
        
        # Check PATH
        found = shutil.which("clawdbot")
        if found:
            self._claude_cli_path = found
            logger.info(f"Clawdbot CLI via PATH: {found}")
            return found
        
        # Check default location
        if os.path.exists(self.CLAWDBOT_CLI_PATH):
            self._claude_cli_path = self.CLAWDBOT_CLI_PATH
            logger.info(f"Clawdbot CLI at default path: {self.CLAWDBOT_CLI_PATH}")
            return self.CLAWDBOT_CLI_PATH
        
        logger.warning("Clawdbot CLI not found")
        return None
    
    def _get_xai_client(self):
        """Get or create xAI/Grok client (OpenAI-compatible)."""
        if self._openai_client is None:
            if not self.xai_api_key:
                logger.warning("No xAI API key configured")
                return None
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(
                    api_key=self.xai_api_key,
                    base_url="https://api.x.ai/v1"
                )
                logger.info("xAI client initialized")
            except ImportError:
                logger.error("openai package not installed. Run: pip install openai")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize xAI client: {e}")
                return None
        return self._openai_client
    
    def is_claude_available(self) -> bool:
        """Check if Claude is available (via Clawdbot CLI)."""
        return bool(self._get_clawdbot_cli_path())
    
    def is_grok_available(self) -> bool:
        """Check if Grok is available."""
        return bool(self.xai_api_key)
    
    # =========================================================================
    # CONTEXT FILE LOADING
    # =========================================================================
    
    def load_context_files(self, force_reload: bool = False) -> ContextFiles:
        """
        Load all context files for Jarvis.
        
        Files loaded:
        - SOUL.md: Core identity and personality
        - AGENTS.md: Workspace rules
        - USER.md: About the user (Matt)
        - TOOLS.md: Local tool notes
        - MEMORY.md: Long-term memory
        - memory/YYYY-MM-DD.md: Today's notes
        - .planning/GATE.md: Current state
        """
        now = datetime.now(timezone.utc)
        
        # Check cache
        if (
            not force_reload 
            and self._context_files is not None 
            and self._context_loaded_at is not None
        ):
            age = (now - self._context_loaded_at).total_seconds()
            if age < self._context_cache_ttl:
                return self._context_files
        
        logger.info("Loading Jarvis context files...")
        ctx = ContextFiles(loaded_at=now)
        
        # Load core files
        ctx.soul = self._read_file(JARVIS_ROOT / "SOUL.md")
        ctx.agents = self._read_file(JARVIS_ROOT / "AGENTS.md")
        ctx.user = self._read_file(JARVIS_ROOT / "USER.md")
        ctx.tools = self._read_file(JARVIS_ROOT / "TOOLS.md")
        ctx.memory = self._read_file(JARVIS_ROOT / "MEMORY.md")
        ctx.heartbeat = self._read_file(JARVIS_ROOT / "HEARTBEAT.md")
        ctx.gate = self._read_file(JARVIS_ROOT / ".planning" / "GATE.md")
        
        # Load today's memory file
        today = now.strftime("%Y-%m-%d")
        ctx.daily_memory = self._read_file(JARVIS_ROOT / "memory" / f"{today}.md")
        
        self._context_files = ctx
        self._context_loaded_at = now
        
        logger.info(f"Context loaded: SOUL={len(ctx.soul)}B, AGENTS={len(ctx.agents)}B, "
                   f"USER={len(ctx.user)}B, MEMORY={len(ctx.memory)}B")
        
        return ctx
    
    def _read_file(self, path: Path) -> str:
        """Safely read a file, return empty string if not found."""
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug(f"Could not read {path}: {e}")
        return ""
    
    # =========================================================================
    # SKILL SEARCH AND LOADING
    # =========================================================================
    
    def _load_skill_index(self) -> None:
        """Build index of available skills."""
        if self._skill_index_loaded:
            return
            
        logger.info("Building skill index...")
        self._skill_index = {}
        
        if not JARVIS_SKILLS.exists():
            logger.warning(f"Skills directory not found: {JARVIS_SKILLS}")
            self._skill_index_loaded = True
            return
        
        for item in JARVIS_SKILLS.iterdir():
            if item.is_dir() or item.is_symlink():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    try:
                        content = skill_md.read_text(encoding="utf-8")
                        # Extract first meaningful paragraph as description
                        desc = self._extract_skill_description(content)
                        self._skill_index[item.name] = desc
                    except Exception as e:
                        logger.debug(f"Could not read skill {item.name}: {e}")
        
        self._skill_index_loaded = True
        logger.info(f"Skill index built: {len(self._skill_index)} skills")
    
    def _extract_skill_description(self, content: str) -> str:
        """Extract description from skill markdown."""
        lines = content.split("\n")
        desc_lines = []
        in_desc = False
        
        for line in lines:
            stripped = line.strip()
            # Skip headers
            if stripped.startswith("#"):
                if in_desc:
                    break
                continue
            # Start collecting after first non-header content
            if stripped and not stripped.startswith("```"):
                desc_lines.append(stripped)
                in_desc = True
                if len(" ".join(desc_lines)) > 300:
                    break
        
        return " ".join(desc_lines)[:300]
    
    def search_skills(self, query: str, limit: int = 3) -> List[SkillMatch]:
        """
        Search for relevant skills based on query.
        
        Uses simple keyword matching. Could be upgraded to embeddings.
        """
        self._load_skill_index()
        
        if not self._skill_index:
            return []
        
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        
        scored = []
        for name, description in self._skill_index.items():
            # Score based on word overlap
            skill_text = (name + " " + description).lower()
            skill_words = set(re.findall(r'\w+', skill_text))
            
            overlap = len(query_words & skill_words)
            if overlap > 0:
                # Boost for name match
                name_match = 2.0 if any(w in name.lower() for w in query_words) else 1.0
                score = overlap * name_match
                scored.append(SkillMatch(
                    name=name,
                    description=description,
                    path=JARVIS_SKILLS / name / "SKILL.md",
                    score=score
                ))
        
        # Sort by score and return top matches
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:limit]
    
    def load_skill_content(self, skill_name: str) -> Optional[str]:
        """Load the full content of a skill's SKILL.md."""
        skill_path = JARVIS_SKILLS / skill_name / "SKILL.md"
        if skill_path.exists():
            try:
                return skill_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Could not load skill {skill_name}: {e}")
        return None
    
    def get_relevant_skill_context(self, query: str, limit: int = 2) -> str:
        """Get relevant skill context for a query."""
        matches = self.search_skills(query, limit=limit)
        if not matches:
            return ""
        
        parts = ["\n\n# Relevant Skills Knowledge"]
        for match in matches:
            content = self.load_skill_content(match.name)
            if content:
                # Truncate skill content
                truncated = content[:2000] if len(content) > 2000 else content
                parts.append(f"\n\n## Skill: {match.name}\n{truncated}")
        
        return "\n".join(parts)
    
    # =========================================================================
    # AI RESPONSE GENERATION
    # =========================================================================
    
    async def generate_response(
        self,
        message: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        chat_context: Optional[List[Dict]] = None,
        use_claude: bool = True,
        use_skills: bool = True,
        max_tokens: int = 1000,
    ) -> str:
        """
        Generate an intelligent response using multi-model AI.
        
        Args:
            message: User's message
            user_id: Telegram user ID
            username: Telegram username
            chat_context: Recent conversation history
            use_claude: Use Claude for reasoning (default True)
            use_skills: Include relevant skills (default True)
            max_tokens: Max response tokens
            
        Returns:
            Generated response text
        """
        # Load context
        ctx = self.load_context_files()
        
        # Build system prompt
        system_parts = [ctx.get_system_context()]
        
        # Add skill context if requested
        if use_skills:
            skill_context = self.get_relevant_skill_context(message, limit=2)
            if skill_context:
                system_parts.append(skill_context)
        
        # Add conversation context
        if chat_context:
            conv_text = self._format_conversation(chat_context[-10:])
            system_parts.append(f"\n\n# Recent Conversation\n{conv_text}")
        
        system_prompt = "\n".join(system_parts)
        
        # Add user context to message
        user_context = f"User: {username or 'Unknown'}"
        if user_id:
            user_context += f" (ID: {user_id})"
        
        full_message = f"[{user_context}]\n{message}"
        
        # Try Grok first (primary model - no Anthropic dependency)
        if self.is_grok_available():
            response = await self._generate_with_grok(
                system_prompt, full_message, max_tokens
            )
            if response:
                return response
        
        # Fallback to Claude only if Grok unavailable
        if use_claude and self.is_claude_available():
            response = await self._generate_with_claude(
                system_prompt, full_message, max_tokens
            )
            if response:
                return response
        
        # No AI available
        return "⚠️ AI services unavailable. Please try again later."
    
    async def _generate_with_claude(
        self, 
        system: str, 
        message: str, 
        max_tokens: int
    ) -> Optional[str]:
        """Generate response using Clawdbot agent (routes through Clawdbot credits)."""
        cli_path = self._get_clawdbot_cli_path()
        if not cli_path:
            logger.warning("Clawdbot CLI not available")
            return None
        
        try:
            # Combine system and user prompt for agent
            combined_prompt = f"""You are JARVIS, Matt's AI assistant. Follow these instructions:

{system}

User message:
{message}

Respond briefly (under {max_tokens // 4} words) in character as JARVIS. Be direct and concise."""

            # Truncate if too long
            if len(combined_prompt) > 8000:
                combined_prompt = combined_prompt[:8000] + "\n\n[context truncated]"

            # Build clawdbot agent command
            # Use a dedicated session for Jarvis AI calls
            cmd_args = [
                cli_path,
                "agent",
                "--session-id", "jarvis-intelligent-core",
                "--message", combined_prompt,
                "--timeout", "60",
            ]

            logger.info("Calling Claude via Clawdbot agent (shared credits)")
            
            # Run in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            
            def run_cli():
                completed = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                    env={**os.environ},
                )
                return completed
            
            completed = await loop.run_in_executor(None, run_cli)
            
            if completed.returncode != 0:
                stderr_preview = completed.stderr[:200] if completed.stderr else 'no stderr'
                logger.warning(f"Clawdbot agent returned code {completed.returncode}: {stderr_preview}")
                return None

            output = (completed.stdout or "").strip()
            if output:
                logger.info("Clawdbot agent response generated successfully")
                return output
            return None
                
        except subprocess.TimeoutExpired:
            logger.error("Clawdbot agent timed out after 90s")
            return None
        except Exception as e:
            logger.error(f"Clawdbot agent generation failed: {e}")
        
        return None
    
    async def _generate_with_grok(
        self, 
        system: str, 
        message: str, 
        max_tokens: int
    ) -> Optional[str]:
        """Generate response using Grok/xAI."""
        client = self._get_xai_client()
        if not client:
            return None
        
        try:
            # Run sync client in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=self.grok_model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": message}
                    ]
                )
            )
            
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"Grok generation failed: {e}")
        
        return None
    
    def _format_conversation(self, messages: List[Dict]) -> str:
        """Format conversation history for context."""
        lines = []
        for msg in messages:
            username = msg.get("username", "Unknown")
            text = msg.get("message", "")[:200]  # Truncate long messages
            lines.append(f"{username}: {text}")
        return "\n".join(lines)
    
    # =========================================================================
    # SPECIALIZED AI METHODS
    # =========================================================================
    
    async def analyze_sentiment(
        self,
        token: str,
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze sentiment for a token using Grok (optimized for speed).
        
        Returns:
            dict with score, confidence, summary, suggested_action
        """
        prompt = f"""Analyze sentiment for {token} on Solana.

Market Data:
- Price: ${market_data.get('price_usd', 'N/A')}
- 1h Change: {market_data.get('price_change_1h', 'N/A')}%
- 24h Change: {market_data.get('price_change_24h', 'N/A')}%
- 24h Volume: ${market_data.get('volume_24h', 'N/A')}
- Liquidity: ${market_data.get('liquidity', 'N/A')}

Respond ONLY with JSON:
{{"score": <-1.0 to 1.0>, "confidence": <0.0 to 1.0>, "summary": "<2 sentences>", "suggested_action": "LONG|SHORT|HOLD|AVOID"}}"""

        client = self._get_xai_client()
        if not client:
            return {
                "score": 0.0,
                "confidence": 0.0,
                "summary": "Grok unavailable",
                "suggested_action": "HOLD"
            }
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=self.grok_model,
                    max_tokens=200,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}]
                )
            )
            
            text = response.choices[0].message.content
            return self._parse_sentiment_json(text)
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {
                "score": 0.0,
                "confidence": 0.0,
                "summary": f"Error: {str(e)[:50]}",
                "suggested_action": "HOLD"
            }
    
    def _parse_sentiment_json(self, text: str) -> Dict[str, Any]:
        """Parse sentiment JSON from response."""
        import json
        try:
            # Find JSON in response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception:
            pass
        return {
            "score": 0.0,
            "confidence": 0.0,
            "summary": text[:100] if text else "Parse error",
            "suggested_action": "HOLD"
        }
    
    async def quick_decision(
        self,
        question: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Get a quick decision/answer using the fastest available model.
        
        Uses Grok for speed, falls back to Claude.
        """
        prompt = question
        if context:
            prompt = f"Context: {context}\n\nQuestion: {question}"
        
        # Try Grok first (faster)
        if self.is_grok_available():
            response = await self._generate_with_grok(
                "You are Jarvis. Be concise.", prompt, 200
            )
            if response:
                return response
        
        # Fallback to Claude
        if self.is_claude_available():
            response = await self._generate_with_claude(
                "You are Jarvis. Be concise.", prompt, 200
            )
            if response:
                return response
        
        return "Unable to process."


# Global instance (singleton pattern)
_intelligent_core: Optional[IntelligentCore] = None


def get_intelligent_core() -> IntelligentCore:
    """Get the global IntelligentCore instance."""
    global _intelligent_core
    if _intelligent_core is None:
        _intelligent_core = IntelligentCore()
    return _intelligent_core


# Convenience functions
async def generate_jarvis_response(
    message: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    chat_context: Optional[List[Dict]] = None,
) -> str:
    """Convenience function for generating Jarvis responses."""
    core = get_intelligent_core()
    return await core.generate_response(
        message=message,
        user_id=user_id,
        username=username,
        chat_context=chat_context,
    )
