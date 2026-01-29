#!/usr/bin/env python3
"""Deploy Jarvis to VPS via Hostinger Docker API"""

import requests
import json

# API configuration
API_TOKEN = "TWJQsjRBOIGxb2uY8TqsPiT5x7ghmnooEQ5xVAo593cbd563"
VPS_ID = "1277677"
API_BASE = "https://developers.hostinger.com/api/vps/v1"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Read docker-compose content
with open("docker-compose.vps.yml", "r") as f:
    compose_content = f.read()

# Create deployment payload
payload = {
    "name": "jarvis-prod",
    "source": {
        "type": "file",
        "content": compose_content
    }
}

print("🚀 Deploying Jarvis to VPS via Docker API...")
print(f"📡 VPS ID: {VPS_ID}")
print(f"📦 Project: jarvis-prod")
print()

# Deploy via API
url = f"{API_BASE}/virtual-machines/{VPS_ID}/docker/projects"
try:
    response = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)

    print(f"📊 Response Status: {response.status_code}")
    print()

    if response.status_code == 201:
        print("✅ Deployment successful!")
        data = response.json()
        print(json.dumps(data, indent=2))
    elif response.status_code == 200:
        print("✅ Request accepted!")
        data = response.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"❌ Deployment failed:")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

except requests.exceptions.RequestException as e:
    print(f"❌ Error: {e}")
    print(f"\n💡 This might mean:")
    print("1. API endpoint doesn't exist or requires different authentication")
    print("2. Docker Manager feature not enabled on this VPS")
    print("3. API token doesn't have Docker management permissions")
