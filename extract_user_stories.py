import re

# Read the full PRD
with open('prd-demo-bot-enhancement.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all user story sections
us_sections = []
lines = content.split('\n')
current_us = []
in_us = False

for line in lines:
    if line.startswith('### US-'):
        if current_us:
            us_sections.append('\n'.join(current_us))
        current_us = [line]
        in_us = True
    elif in_us:
        if line.startswith('## ') and not line.startswith('### '):
            # Hit a new major section
            if current_us:
                us_sections.append('\n'.join(current_us))
            current_us = []
            in_us = False
        elif line.startswith('### US-'):
            # Next user story
            us_sections.append('\n'.join(current_us))
            current_us = [line]
        else:
            current_us.append(line)

# Add last user story
if current_us:
    us_sections.append('\n'.join(current_us))

print(f"Found {len(us_sections)} user stories")

# Create clean PRD
clean_prd = """# PRD: Telegram /demo Bot - Production-Ready AI Trading Assistant

## Executive Summary

Transform the Telegram /demo bot into an AI-powered trading assistant with real-time sentiment analysis, bags.fm API trading, treasury signals, self-learning AI, and advanced order management.

## User Stories

"""

for section in us_sections:
    clean_prd += section.strip() + "\n\n---\n\n"

# Write clean PRD
with open('prd-demo-bot-clean.md', 'w', encoding='utf-8') as f:
    f.write(clean_prd)

print(f"Clean PRD created with {len(us_sections)} user stories")
