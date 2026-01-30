"""
Skills command handler for Jarvis Telegram bot.

Commands:
    /skills - List all available skills
    /skill <name> - Get details about a specific skill
    /skillsearch <query> - Search skills by keyword
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# Lazy load skills knowledge to avoid import issues
_skills_knowledge = None


def _get_skills_knowledge():
    """Lazy load skills knowledge module."""
    global _skills_knowledge
    if _skills_knowledge is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'skills_knowledge',
            '/root/clawd/Jarvis/core/skills_knowledge.py'
        )
        _skills_knowledge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_skills_knowledge)
    return _skills_knowledge


async def skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    List all available skills.
    
    Usage: /skills
    """
    try:
        sk = _get_skills_knowledge()
        skills_list = sk.list_available_skills()
        
        if not skills_list:
            await update.message.reply_text(
                "no skills loaded. circuits confused.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Group by category
        categories = {
            "🔗 Solana/Crypto": [],
            "📱 Telegram": [],
            "🌐 Browser/Web": [],
            "🏗 Architecture": [],
            "🎨 UI/Design": [],
            "📦 Other": []
        }
        
        for skill_name in skills_list:
            name_lower = skill_name.lower()
            if any(x in name_lower for x in ['solana', 'jito', 'jupiter', 'token', 'sniper', 'liquidity']):
                categories["🔗 Solana/Crypto"].append(skill_name)
            elif 'telegram' in name_lower:
                categories["📱 Telegram"].append(skill_name)
            elif any(x in name_lower for x in ['browser', 'web', 'frontend']):
                categories["🌐 Browser/Web"].append(skill_name)
            elif any(x in name_lower for x in ['architect', 'devops', 'senior']):
                categories["🏗 Architecture"].append(skill_name)
            elif any(x in name_lower for x in ['ui', 'ux', 'design']):
                categories["🎨 UI/Design"].append(skill_name)
            else:
                categories["📦 Other"].append(skill_name)
        
        lines = [f"*{len(skills_list)} skills loaded*\n"]
        
        for category, skills in categories.items():
            if skills:
                lines.append(f"\n{category}")
                for s in sorted(skills):
                    lines.append(f"  `{s}`")
        
        lines.append("\n_use `/skill <name>` for details_")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in skills_command: {e}")
        await update.message.reply_text(
            f"skill loader crashed: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )


async def skill_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Get details about a specific skill.
    
    Usage: /skill <name>
    """
    if not context.args:
        await update.message.reply_text(
            "need a skill name. try `/skills` to see what's available.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    skill_name = context.args[0].lower()
    
    try:
        sk = _get_skills_knowledge()
        skills = sk.get_skills_knowledge()
        
        # Find matching skill
        skill_info = skills.get_skill(skill_name)
        
        if not skill_info:
            # Try partial match
            matches = [s for s in skills.list_skills() if skill_name in s.lower()]
            if matches:
                await update.message.reply_text(
                    f"skill `{skill_name}` not found. maybe:\n" + 
                    "\n".join(f"  `{m}`" for m in matches[:5]),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"skill `{skill_name}` not found. `/skills` to see all.",
                    parse_mode=ParseMode.MARKDOWN
                )
            return
        
        # Format skill info
        desc = skill_info.description[:500] if skill_info.description else "no description"
        
        # Get content excerpt
        content_lines = skill_info.content.split('\n')
        content_excerpt = '\n'.join(content_lines[:20])
        if len(content_lines) > 20:
            content_excerpt += f"\n\n_...{len(content_lines) - 20} more lines_"
        
        response = f"""*{skill_info.name}*

{desc}

```
{content_excerpt[:1500]}
```"""
        
        await update.message.reply_text(
            response[:4000],
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in skill_command: {e}")
        await update.message.reply_text(
            f"failed to load skill: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )


async def skillsearch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Search skills by keyword.
    
    Usage: /skillsearch <query>
    """
    if not context.args:
        await update.message.reply_text(
            "need a search query. example: `/skillsearch solana trading`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    query = " ".join(context.args)
    
    try:
        sk = _get_skills_knowledge()
        results = sk.search_skill(query, limit=5)
        
        if not results:
            await update.message.reply_text(
                f"no skills match `{query}`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        lines = [f"*Skills matching `{query}`*\n"]
        
        for skill in results:
            desc = skill.description[:100] + "..." if len(skill.description) > 100 else skill.description
            lines.append(f"**{skill.name}**")
            lines.append(f"  {desc}\n")
        
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in skillsearch_command: {e}")
        await update.message.reply_text(
            f"search failed: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )
