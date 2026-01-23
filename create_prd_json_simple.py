import re
import json
from datetime import datetime, timezone

# Read the PRD
with open('prd-demo-bot-enhancement.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all user story IDs and titles (simpler pattern)
us_pattern = r'### (US-\d+): (.+)'
matches = re.findall(us_pattern, content)

print(f"Found {len(matches)} user stories")

user_stories = []
for idx, (us_id, title) in enumerate(matches, 1):
    # For now, use title as description (ralph-tui will refine during execution)
    user_story = {
        "id": us_id.strip(),
        "title": title.strip(),
        "description": title.strip(),  # Simplified for now
        "acceptanceCriteria": [],
        "priority": 1 if idx <= 10 else (2 if idx <= 20 else 3),
        "passes": False,
        "labels": [],
        "dependsOn": []
    }
    user_stories.append(user_story)
    print(f"  {us_id}: {title.strip()}")

# Create PRD JSON
prd_json = {
    "name": "Telegram /demo Bot - Production-Ready AI Trading Assistant",
    "description": "Transform the Telegram /demo bot into an AI-powered trading assistant with real-time sentiment analysis, bags.fm API trading, treasury signals, self-learning AI, and advanced order management.",
    "branchName": "feature/demo-bot-fixes",
    "userStories": user_stories,
    "metadata": {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "sourcePrd": "prd-demo-bot-enhancement.md"
    }
}

# Write JSON
with open('prd-demo-bot.json', 'w', encoding='utf-8') as f:
    json.dump(prd_json, f, indent=2)

print(f"\nCreated prd-demo-bot.json with {len(user_stories)} user stories")
