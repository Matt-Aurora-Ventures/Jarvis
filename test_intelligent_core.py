#!/usr/bin/env python3
"""Quick test for Jarvis Intelligent Core."""

import asyncio
import sys
import os

# Add tg_bot to path
sys.path.insert(0, '/root/clawd/Jarvis')

# Load env manually
env_path = '/root/clawd/Jarvis/tg_bot/.env'
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ[key] = value

from tg_bot.services.intelligent_core import get_intelligent_core

async def test():
    print("Testing Jarvis Intelligent Core...")
    
    core = get_intelligent_core()
    
    # Check availability
    print(f"\n✓ Claude available: {core.is_claude_available()}")
    print(f"✓ Grok available: {core.is_grok_available()}")
    
    # Test context loading
    ctx = core.load_context_files()
    print(f"\n✓ Context files loaded:")
    print(f"  - SOUL.md: {len(ctx.soul)} bytes")
    print(f"  - AGENTS.md: {len(ctx.agents)} bytes")
    print(f"  - USER.md: {len(ctx.user)} bytes")
    print(f"  - MEMORY.md: {len(ctx.memory)} bytes")
    
    # Test skill search
    skills = core.search_skills("solana trading", limit=3)
    print(f"\n✓ Skill search 'solana trading': {len(skills)} matches")
    for s in skills:
        print(f"  - {s.name} (score: {s.score:.2f})")
    
    # Test response generation (with Claude)
    if core.is_claude_available():
        print("\n⏳ Testing Claude response generation...")
        response = await core.generate_response(
            message="What can you help me with?",
            user_id=8527130908,
            username="Matt",
            use_claude=True,
            use_skills=False,  # Skip skills for quick test
        )
        print(f"\n✓ Claude response ({len(response)} chars):")
        print(f"  {response[:200]}...")
    
    print("\n✅ Intelligent Core test complete!")

if __name__ == "__main__":
    asyncio.run(test())
