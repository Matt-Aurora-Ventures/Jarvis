#!/usr/bin/env python3
import re
import subprocess

# Get the actual Linktree content with social media links
result = subprocess.run([
    'curl', '-s', '-L',
    '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'https://linktr.ee/auroraventures'
], capture_output=True, text=True)

html = result.stdout

# Extract actual social media links (not assets)
social_links = []
all_links = re.findall(r'href=[\\\"\'](.*?)[\\\"\']', html)

for link in all_links:
    if any(social in link.lower() for social in ['twitter.com', 'x.com', 'instagram.com', 'linkedin.com', 'facebook.com', 'tiktok.com', 'youtube.com', 'github.com']):
        social_links.append(link)
    elif any(contact in link.lower() for contact in ['wa.me', 'whatsapp.com', 'mailto:', 'tel:']):
        social_links.append(link)
    elif any(site in link.lower() for site in ['kr8tiv.io', 'aurah2o.net', 'aurabnb.gitbook.io']):
        social_links.append(link)

print('Found relevant links:')
for link in social_links:
    print(f'  - {link}')
