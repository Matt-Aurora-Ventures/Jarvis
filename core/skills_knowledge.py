"""
Skills Knowledge Integration for Jarvis.

Loads ClawdMatt's skill reference materials (SKILL.md files) and makes them
queryable for context-aware responses.

This doesn't execute skills - it provides knowledge access so Jarvis can
use skill documentation when answering questions.
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Paths to skill directories (in priority order)
SKILL_PATHS = [
    Path("/root/.agents/skills"),
    Path("/root/.clawdbot/skills"),
    Path("/root/clawd/Jarvis/skills"),
]


@dataclass
class SkillInfo:
    """Metadata about a skill."""
    name: str
    description: str
    path: Path
    content: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class SkillsKnowledge:
    """
    Knowledge base for skill reference materials.
    
    Provides:
    - Skill discovery and loading
    - Semantic search for relevant skills
    - Full skill content retrieval
    """
    
    def __init__(self):
        self._skills: Dict[str, SkillInfo] = {}
        self._loaded = False
    
    def discover_skills(self) -> Dict[str, SkillInfo]:
        """
        Scan skill directories and discover all SKILL.md files.
        
        Returns:
            Dictionary mapping skill names to SkillInfo.
        """
        self._skills = {}
        
        for skill_path in SKILL_PATHS:
            if not skill_path.exists():
                continue
                
            for item in skill_path.iterdir():
                # Handle symlinks
                if item.is_symlink():
                    item = item.resolve()
                
                if not item.is_dir():
                    continue
                    
                skill_md = item / "SKILL.md"
                if not skill_md.exists():
                    continue
                
                try:
                    info = self._parse_skill_md(skill_md)
                    if info and info.name not in self._skills:
                        self._skills[info.name] = info
                        logger.debug(f"Discovered skill: {info.name}")
                except Exception as e:
                    logger.warning(f"Failed to parse {skill_md}: {e}")
        
        self._loaded = True
        logger.info(f"Discovered {len(self._skills)} skills")
        return self._skills
    
    def _parse_skill_md(self, path: Path) -> Optional[SkillInfo]:
        """Parse a SKILL.md file to extract metadata."""
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # Extract frontmatter if present
        name = path.parent.name
        description = ""
        tags = []
        
        # Try YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            # Extract name
            name_match = re.search(r'name:\s*(.+)', frontmatter)
            if name_match:
                name = name_match.group(1).strip()
            # Extract description
            desc_match = re.search(r'description:\s*(.+)', frontmatter)
            if desc_match:
                description = desc_match.group(1).strip()
            # Extract tags
            tags_match = re.search(r'tags:\s*\[([^\]]+)\]', frontmatter)
            if tags_match:
                tags = [t.strip().strip('"\'') for t in tags_match.group(1).split(',')]
        
        # If no frontmatter description, use first paragraph
        if not description:
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('---'):
                    description = line[:200]
                    break
        
        return SkillInfo(
            name=name,
            description=description,
            path=path.parent,
            content=content,
            tags=tags
        )
    
    def get_skill(self, name: str) -> Optional[SkillInfo]:
        """Get a specific skill by name."""
        if not self._loaded:
            self.discover_skills()
        return self._skills.get(name)
    
    def get_skill_content(self, name: str, include_related: bool = True) -> str:
        """
        Get full skill content, optionally including related files.
        
        Args:
            name: Skill name
            include_related: Include other .md files in the skill directory
            
        Returns:
            Full skill content as string
        """
        skill = self.get_skill(name)
        if not skill:
            return f"Skill '{name}' not found."
        
        content = [f"# {skill.name}\n", skill.content]
        
        if include_related:
            # Load other .md files in the skill directory
            for md_file in skill.path.glob("*.md"):
                if md_file.name == "SKILL.md":
                    continue
                try:
                    related_content = md_file.read_text(encoding="utf-8", errors="ignore")
                    content.append(f"\n\n## {md_file.stem}\n\n{related_content}")
                except Exception:
                    pass
        
        return "\n".join(content)
    
    def search_skills(self, query: str, limit: int = 5) -> List[SkillInfo]:
        """
        Search skills by keyword matching.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching SkillInfo objects
        """
        if not self._loaded:
            self.discover_skills()
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        for skill in self._skills.values():
            score = 0
            
            # Name match (highest weight)
            if query_lower in skill.name.lower():
                score += 10
            
            # Description match
            if skill.description and query_lower in skill.description.lower():
                score += 5
            
            # Tag match
            for tag in skill.tags:
                if query_lower in tag.lower():
                    score += 3
            
            # Word matches in content
            content_lower = skill.content.lower()
            for word in query_words:
                if word in content_lower:
                    score += 1
            
            if score > 0:
                scored.append((score, skill))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:limit]]
    
    def list_skills(self) -> List[str]:
        """List all available skill names."""
        if not self._loaded:
            self.discover_skills()
        return sorted(self._skills.keys())
    
    def get_skills_summary(self) -> str:
        """
        Get a summary of all available skills for context injection.
        
        Returns:
            Formatted string summarizing available skills
        """
        if not self._loaded:
            self.discover_skills()
        
        lines = ["# Available Skills\n"]
        
        # Group by category
        categories = {
            "Solana/Crypto": [],
            "Telegram": [],
            "Browser/Web": [],
            "Architecture/DevOps": [],
            "UI/Design": [],
            "Other": []
        }
        
        for skill in self._skills.values():
            name_lower = skill.name.lower()
            
            if any(x in name_lower for x in ['solana', 'jito', 'jupiter', 'token', 'sniper', 'liquidity']):
                categories["Solana/Crypto"].append(skill)
            elif 'telegram' in name_lower:
                categories["Telegram"].append(skill)
            elif any(x in name_lower for x in ['browser', 'web', 'frontend']):
                categories["Browser/Web"].append(skill)
            elif any(x in name_lower for x in ['architect', 'devops', 'senior']):
                categories["Architecture/DevOps"].append(skill)
            elif any(x in name_lower for x in ['ui', 'ux', 'design']):
                categories["UI/Design"].append(skill)
            else:
                categories["Other"].append(skill)
        
        for category, skills in categories.items():
            if skills:
                lines.append(f"\n## {category}")
                for skill in sorted(skills, key=lambda x: x.name):
                    desc = skill.description[:100] + "..." if len(skill.description) > 100 else skill.description
                    lines.append(f"- **{skill.name}**: {desc}")
        
        return "\n".join(lines)


# Singleton instance
_skills_knowledge: Optional[SkillsKnowledge] = None


def get_skills_knowledge() -> SkillsKnowledge:
    """Get the global SkillsKnowledge instance."""
    global _skills_knowledge
    if _skills_knowledge is None:
        _skills_knowledge = SkillsKnowledge()
        _skills_knowledge.discover_skills()
    return _skills_knowledge


# Convenience functions
def search_skill(query: str, limit: int = 5) -> List[SkillInfo]:
    """Search for skills matching query."""
    return get_skills_knowledge().search_skills(query, limit)


def get_skill_content(name: str) -> str:
    """Get full content of a skill."""
    return get_skills_knowledge().get_skill_content(name)


def list_available_skills() -> List[str]:
    """List all available skill names."""
    return get_skills_knowledge().list_skills()


def get_skills_summary() -> str:
    """Get summary of all skills for context."""
    return get_skills_knowledge().get_skills_summary()
