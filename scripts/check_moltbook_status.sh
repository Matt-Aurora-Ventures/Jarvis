#!/bin/bash
# Check Moltbook claim status and notify when claimed

ssh root@100.66.17.93 "docker exec clawdbot-gateway cat /root/clawd/secrets/moltbook.json" | \
python3 -c "
import json, sys
data = json.load(sys.stdin)
status = data.get('registration', {}).get('status', 'unknown')
agent_id = data.get('registration', {}).get('agent', {}).get('id', 'N/A')
name = data.get('registration', {}).get('agent', {}).get('name', 'ClawdMatt')

print(f'Agent: {name}')
print(f'Status: {status}')
print(f'ID: {agent_id}')

if status == 'claimed':
    print('')
    print('✓ READY TO POST!')
    print('Test with: ssh root@100.66.17.93 \"docker exec clawdbot-gateway node /root/clawd/scripts/moltbook-post.mjs\"')
    sys.exit(0)
elif status == 'pending_claim':
    print('')
    print('⏳ Waiting for claim verification...')
    sys.exit(1)
else:
    print('')
    print(f'⚠ Unexpected status: {status}')
    sys.exit(2)
"
