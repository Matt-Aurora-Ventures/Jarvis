#!/bin/bash
# CLAWDMATT BOOTSTRAP - Survives complete VPS wipe
# Last updated: 2026-01-29
# Store this in: supermemory, Windows desktop, VPS /opt/clawdmatt-init/

set -e
echo "=== CLAWDMATT BOOTSTRAP STARTING ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# SKILLS TO INSTALL
SKILLS=(
  "https://github.com/vercel-labs/agent-skills --skill web-design-guidelines"
  "https://github.com/vercel-labs/skills --skill find-skills"
  "https://github.com/vercel-labs/agent-browser --skill agent-browser"
  "https://github.com/anthropics/skills --skill frontend-design"
  "https://github.com/browser-use/browser-use --skill browser-use"
  "https://github.com/sickn33/antigravity-awesome-skills --skill browser-automation"
  "https://github.com/coreyhaines31/marketingskills --skill marketing-psychology"
  "https://github.com/expo/skills --skill expo-tailwind-setup"
  "https://github.com/omer-metin/skills-for-antigravity --skill telegram-mastery"
  "https://github.com/terrylica/cc-skills --skill telegram-bot-management"
  "https://github.com/2025emma/vibe-coding-cn --skill telegram-dev"
  "https://github.com/sickn33/antigravity-awesome-skills --skill telegram-bot-builder"
  "https://github.com/omer-metin/skills-for-antigravity --skill solana-development"
  "https://github.com/sanctifiedops/solana-skills --skill jito-bundles-and-priority-fees"
  "https://github.com/sanctifiedops/solana-skills --skill liquidity-and-price-dynamics-explainer"
  "https://github.com/sanctifiedops/solana-skills --skill sniper-dynamics-and-mitigation"
  "https://github.com/sanctifiedops/solana-skills --skill jupiter-swap-integration"
  "https://github.com/sanctifiedops/solana-skills --skill token-analysis-checklist"
  "https://github.com/guibibeau/solana-dev-skill --skill solana-dev"
  "https://github.com/trailofbits/skills --skill solana-vulnerability-scanner"
  "https://github.com/davila7/claude-code-templates --skill senior-devops"
  "https://github.com/sickn33/antigravity-awesome-skills --skill senior-architect"
  "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill --skill ui-ux-pro-max"
  "https://github.com/sanjay3290/postgres-skill --skill gmail"
  "https://github.com/VoltAgent/awesome-moltbot-skills"
  "https://github.com/GH05TCREW/pentestagent"
)

install_skills() {
  echo "=== Installing ${#SKILLS[@]} skills ==="
  for skill in "${SKILLS[@]}"; do
    echo "Installing: $skill"
    npx skills add $skill || echo "Warning: Failed to install $skill"
  done
}

restore_ssh() {
  echo "=== Restoring SSH keys ==="
  mkdir -p /root/.ssh
  chmod 700 /root/.ssh
  if [ ! -f /root/.ssh/id_ed25519 ]; then
    echo "Generating new SSH key..."
    ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N "" -C "clawd@server"
    echo "NEW KEY - Add to Windows: $(cat /root/.ssh/id_ed25519.pub)"
  fi
}

main() {
  restore_ssh
  install_skills
  echo "=== BOOTSTRAP COMPLETE ==="
}

main "$@"
