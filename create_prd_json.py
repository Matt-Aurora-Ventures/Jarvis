import re
import json
from datetime import datetime

# Read the PRD
with open('prd-demo-bot-enhancement.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract user stories
us_pattern = r'### (US-\d+): (.+?)\n\n\*\*As a\*\* (.+?)\n\*\*I want to\*\* (.+?)\n\*\*So that\*\* (.+?)(?=\n\n|\n\*\*)'
matches = re.findall(us_pattern, content, re.DOTALL)

print(f"Found {len(matches)} user stories with full descriptions")

user_stories = []
for idx, match in enumerate(matches, 1):
    us_id, title, user_type, want, so_that = match
    description = f"As a {user_type.strip()} I want to {want.strip()} So that {so_that.strip()}"

    user_story = {
        "id": us_id.strip(),
        "title": title.strip(),
        "description": description,
        "acceptanceCriteria": [],
        "priority": min(idx, 4),  # Priority 1-4
        "passes": False,
        "labels": [],
        "dependsOn": []
    }
    user_stories.append(user_story)
    print(f"  {us_id}: {title[:50]}...")

# Create PRD JSON
prd_json = {
    "name": "Telegram /demo Bot - Production-Ready AI Trading Assistant",
    "description": "Transform the Telegram /demo bot into an AI-powered trading assistant with real-time sentiment analysis, bags.fm API trading, treasury signals, self-learning AI, and advanced order management.",
    "branchName": "feature/demo-bot-fixes",
    "userStories": user_stories,
    "metadata": {
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "sourcePrd": "prd-demo-bot-enhancement.md"
    }
}

# Write JSON
with open('prd-demo-bot.json', 'w', encoding='utf-8') as f:
    json.dump(prd_json, f, indent=2)

print(f"\nCreated prd-demo-bot.json with {len(user_stories)} user stories")
