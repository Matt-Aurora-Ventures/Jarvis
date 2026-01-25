# WSL Development Environment - Complete Installation Guide

**All-in-one setup for Claude CLI, Clawd Bot, Windsurf IDE, and GSD on Windows Subsystem for Linux**

---

## 📋 Table of Contents

1. [What Gets Installed](#what-gets-installed)
2. [Quick Start (30 seconds)](#quick-start)
3. [Detailed Installation](#detailed-installation)
4. [Configuration](#configuration)
5. [Verification & Testing](#verification--testing)
6. [Daily Usage](#daily-usage)
7. [Troubleshooting](#troubleshooting)
8. [Updating](#updating)
9. [Uninstalling](#uninstalling)

---

## 🎯 What Gets Installed

### Core Tools
- ✅ **Claude CLI** - Anthropic's official command-line tool for Claude AI
- ✅ **Clawd Bot** - Discord bot framework powered by Claude
- ✅ **GSD (Get Shit Done)** - Productivity framework from glittercowboy
- ✅ **VS Code** - Microsoft's code editor with WSL integration
- ✅ **Windsurf IDE** - Modern development environment

### Runtime Environments
- ✅ **Node.js 20.x** - JavaScript runtime
- ✅ **Python 3** - Latest Python with pip
- ✅ **uv** - Fast Python package installer

### Development Tools
- ✅ git, curl, wget, build-essential
- ✅ Systemd services (auto-start bots)
- ✅ Optimized WSL configuration
- ✅ Helper scripts and aliases

---

## 🚀 Quick Start

### From Windows (Easiest Method)

1. **Open PowerShell** (as regular user, no admin needed)

2. **Navigate to scripts directory:**
   ```powershell
   cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts
   ```

3. **Run the installer:**
   ```powershell
   .\Setup-WSL-DevEnvironment.ps1
   ```

4. **Wait 5-10 minutes for installation**

5. **Configure API keys** (see [Configuration](#configuration))

6. **Verify installation** (see [Verification](#verification--testing))

That's it! ✨

---

## 📖 Detailed Installation

### Method 1: PowerShell Launcher (Recommended)

**Windows PowerShell:**
```powershell
# 1. Navigate to scripts directory
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts

# 2. Run installer
.\Setup-WSL-DevEnvironment.ps1

# Optional: Check WSL status first
.\Setup-WSL-DevEnvironment.ps1 -CheckOnly

# Get help
.\Setup-WSL-DevEnvironment.ps1 -Help
```

The PowerShell script:
- ✅ Checks WSL installation
- ✅ Copies scripts to WSL
- ✅ Runs Linux setup automatically
- ✅ Creates desktop shortcuts (optional)

### Method 2: Manual WSL Execution

**From WSL terminal:**

1. **Copy the script to WSL:**
   ```bash
   cp /mnt/c/Users/lucid/OneDrive/Desktop/Projects/Jarvis/scripts/setup_wsl_complete.sh ~/
   chmod +x ~/setup_wsl_complete.sh
   ```

2. **Run the installer:**
   ```bash
   bash ~/setup_wsl_complete.sh
   ```

3. **Follow on-screen prompts**

### What Happens During Installation

```
Step 1:  Update system packages
Step 2:  Install prerequisites (git, curl, build tools)
Step 3:  Install Node.js 20.x
Step 4:  Install Claude CLI
Step 5:  Install Python 3 and pip
Step 6:  Install uv (fast package manager)
Step 7:  Clone and setup Clawd Bot
Step 8:  Clone and setup GSD framework
Step 9:  Install VS Code
Step 10: Create environment configuration
Step 11: Create systemd services (if available)
Step 12: Create verification script
Step 13: Create quick start guide
```

---

## ⚙️ Configuration

### 1. API Keys (Required)

After installation, you **must** configure API keys:

**Edit the config file:**
```bash
nano ~/.wsl_dev_config
```

**Add your keys:**
```bash
# Claude AI (get from https://console.anthropic.com)
export CLAUDE_API_KEY="sk-ant-your-key-here"

# Discord Bot (get from https://discord.com/developers)
export DISCORD_BOT_TOKEN="your-discord-token-here"

# Optional: OpenAI
export OPENAI_API_KEY="sk-your-openai-key"
```

**Reload configuration:**
```bash
source ~/.bashrc
```

### 2. Claude CLI Authentication

```bash
# Authenticate with Anthropic
claude auth login

# Test it works
claude "Say hello!"
```

### 3. Clawd Bot Configuration

**Option A: Using .env file (recommended)**
```bash
cd ~/clawd
cp .env.example .env  # if exists
nano .env
```

Add to `.env`:
```
DISCORD_BOT_TOKEN=your_token_here
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-3-sonnet-20240229
```

**Option B: Using environment variables**

Already configured in `~/.wsl_dev_config` if you set them above.

### 4. GSD Configuration

```bash
cd ~/get-shit-done
# Follow GSD-specific setup instructions in their README
```

### 5. Windsurf IDE

- **Option 1:** Install Windsurf on Windows and access WSL files via `\\wsl$\Ubuntu\home\username`
- **Option 2:** Install Windsurf in WSL (requires WSLg for GUI support)

---

## ✅ Verification & Testing

### Run Verification Script

```bash
bash ~/verify_wsl_setup.sh
```

Expected output:
```
╔══════════════════════════════════════════════════════════════╗
║          WSL Development Environment Verification            ║
╚══════════════════════════════════════════════════════════════╝

1. System Tools:
✓ curl: /usr/bin/curl
✓ git: /usr/bin/git
✓ node: /usr/bin/node
  Version: v20.x.x
✓ npm: /usr/bin/npm
✓ python3: /usr/bin/python3
✓ pip3: /usr/bin/pip3
✓ uv: /home/user/.cargo/bin/uv

2. Development Tools:
✓ claude: /usr/local/bin/claude
  Version: x.x.x
✓ code: /usr/bin/code

3. Projects:
✓ Clawd Bot: /home/user/clawd
  ✓ Python virtual environment found
✓ GSD Framework: /home/user/get-shit-done

4. Configuration:
✓ WSL dev config found
  ✓ CLAUDE_API_KEY set
  ✓ DISCORD_BOT_TOKEN set

5. Systemd Status:
✓ Systemd enabled
```

### Test Individual Tools

**Claude CLI:**
```bash
claude --version
claude "Write a haiku about WSL"
```

**Clawd Bot:**
```bash
cd ~/clawd
# For Python version:
source venv/bin/activate
python main.py

# For Node.js version:
npm start
```

**GSD:**
```bash
cd ~/get-shit-done
# Follow GSD instructions for testing
```

**VS Code:**
```bash
code .
```

---

## 💻 Daily Usage

### Quick Commands (Aliases)

After installation, you have these aliases available:

```bash
# Navigate to projects
clawd              # cd ~/clawd
gsd                # cd ~/get-shit-done

# Activate environments
activate-clawd     # Activate Clawd Python venv
activate-gsd       # Activate GSD environment

# Updates
update-dev         # Update system packages
update-node        # Update Node.js packages
update-claude      # Update Claude CLI
update-all         # Update EVERYTHING (recommended once a week)

# Status checks
dev-status         # Check environment status
claude-version     # Show Claude CLI version
```

### Starting Services

**Claude CLI:**
```bash
# Interactive mode
claude

# One-off query
claude "Your question here"

# With specific model
claude -m opus "Complex question"
```

**Clawd Discord Bot:**
```bash
# Manual start
clawd
activate-clawd
python main.py

# Or use the desktop shortcut (if created)
# Or set up systemd auto-start (see below)
```

**GSD Framework:**
```bash
gsd
activate-gsd
# Follow GSD usage instructions
```

### Auto-Start Services (Systemd)

If your WSL has systemd enabled:

**Install Clawd service:**
```bash
# Copy the service file from /tmp (created during setup)
sudo cp /tmp/clawd.service /etc/systemd/system/

# Enable auto-start
sudo systemctl enable clawd

# Start now
sudo systemctl start clawd

# Check status
sudo systemctl status clawd

# View logs
journalctl -u clawd -f
```

---

## 🔧 Troubleshooting

### Run Troubleshooting Script

```bash
bash ~/troubleshoot_wsl.sh
```

This script checks for common issues and suggests fixes.

### Common Issues

#### 1. "claude: command not found"

**Fix:**
```bash
sudo npm install -g @anthropic-ai/claude-code
source ~/.bashrc
```

#### 2. Clawd bot won't start - "Module not found"

**For Python:**
```bash
cd ~/clawd
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

**For Node.js:**
```bash
cd ~/clawd
npm install
```

#### 3. Discord bot authentication fails

- Verify token in `~/.wsl_dev_config` or `~/clawd/.env`
- Check token is valid at https://discord.com/developers
- Ensure bot has correct permissions
- Check bot is invited to your Discord server

#### 4. No internet in WSL

```bash
# Check connectivity
ping 8.8.8.8

# If DNS fails, update resolv.conf
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

# From Windows PowerShell (as admin):
wsl --shutdown
wsl
```

#### 5. Memory issues / OOM errors

Edit `C:\Users\lucid\.wslconfig`:
```ini
[wsl2]
memory=12GB  # Increase from 8GB
```

Then restart WSL:
```powershell
wsl --shutdown
wsl
```

#### 6. Systemd not working

Enable systemd in `/etc/wsl.conf`:
```bash
sudo nano /etc/wsl.conf
```

Add:
```ini
[boot]
systemd=true
```

Restart WSL:
```powershell
wsl --shutdown
wsl
```

---

## 🔄 Updating

### Update Everything (Recommended Weekly)

```bash
bash ~/update_all_wsl.sh
```

This updates:
- System packages (apt)
- Node.js global packages
- Claude CLI
- Python global packages
- Clawd Bot
- GSD Framework

### Update Individual Components

**System:**
```bash
update-dev
# Or: sudo apt-get update && sudo apt-get upgrade -y
```

**Claude CLI:**
```bash
update-claude
# Or: sudo npm update -g @anthropic-ai/claude-code
```

**Clawd:**
```bash
cd ~/clawd
git pull
npm install  # or pip install -r requirements.txt
```

**GSD:**
```bash
cd ~/get-shit-done
git pull
npm install  # or pip install -r requirements.txt
```

---

## 🗑️ Uninstalling

### Remove Everything

**1. Remove installed tools:**
```bash
# Remove Claude CLI
sudo npm uninstall -g @anthropic-ai/claude-code

# Remove VS Code
sudo apt-get remove code

# Remove Node.js (if you want to)
sudo apt-get remove nodejs npm

# Remove Python packages
pip3 uninstall -y $(pip3 list --user --format=freeze | cut -d= -f1)
```

**2. Remove project directories:**
```bash
rm -rf ~/clawd
rm -rf ~/get-shit-done
```

**3. Remove configuration:**
```bash
rm ~/.wsl_dev_config
# Edit ~/.bashrc and remove the line that sources .wsl_dev_config
nano ~/.bashrc
```

**4. Remove systemd services:**
```bash
sudo systemctl stop clawd
sudo systemctl disable clawd
sudo rm /etc/systemd/system/clawd.service
sudo systemctl daemon-reload
```

### Clean Install (Fresh Start)

If you want to start over:

**From Windows PowerShell:**
```powershell
# 1. Shutdown WSL
wsl --shutdown

# 2. Unregister the distribution (⚠️ THIS DELETES ALL WSL DATA!)
wsl --unregister Ubuntu

# 3. Reinstall
wsl --install -d Ubuntu

# 4. Run setup script again
.\Setup-WSL-DevEnvironment.ps1
```

---

## 📚 Resources

### Documentation
- **Claude CLI:** https://github.com/anthropics/claude-code
- **Clawd Bot:** https://clawd.bot / https://github.com/chand1012/clawd
- **GSD:** https://github.com/glittercowboy/get-shit-done
- **Windsurf:** https://windsurf.com
- **WSL:** https://learn.microsoft.com/en-us/windows/wsl/

### Getting API Keys
- **Anthropic (Claude):** https://console.anthropic.com
- **Discord Bot:** https://discord.com/developers/applications
- **OpenAI (optional):** https://platform.openai.com

### Support
- File issues on respective GitHub repos
- Check troubleshooting script: `bash ~/troubleshoot_wsl.sh`
- Review verification: `bash ~/verify_wsl_setup.sh`

---

## 🎓 Tips & Best Practices

### 1. Regular Updates
```bash
# Run this weekly
update-all
```

### 2. Backup Configuration
```bash
# Backup your .env files and API keys
cp ~/.wsl_dev_config ~/backup_config_$(date +%Y%m%d).sh
cp ~/clawd/.env ~/clawd_env_backup_$(date +%Y%m%d).txt
```

### 3. Monitor Resources
```bash
# Check memory and CPU
htop

# Check disk usage
df -h

# Check running processes
dev-status
```

### 4. Use VS Code Remote - WSL
- Install "Remote - WSL" extension in VS Code
- Open WSL projects directly from Windows VS Code
- Better than running `code` from WSL terminal

### 5. Keep Logs
- Clawd logs: `~/clawd/logs/`
- Systemd logs: `journalctl -u clawd -f`
- Claude CLI: Check `~/.config/claude/`

---

## 🎉 You're All Set!

Your WSL development environment is now ready with:
- ✅ Claude CLI for AI assistance
- ✅ Clawd Bot for Discord integration
- ✅ GSD for productivity
- ✅ Full development stack (Node.js, Python, VS Code)

**Next Steps:**
1. Configure your API keys (see [Configuration](#configuration))
2. Test each tool (see [Verification](#verification--testing))
3. Start building! 🚀

**Quick Reference:**
- Quick Start Guide: `cat ~/WSL_QUICK_START.md`
- Verify Setup: `bash ~/verify_wsl_setup.sh`
- Troubleshoot: `bash ~/troubleshoot_wsl.sh`
- Update All: `bash ~/update_all_wsl.sh`
- Environment Status: `dev-status`

Happy coding! 💻
