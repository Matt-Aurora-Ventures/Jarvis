# WSL Development Environment - Scripts Index

This directory contains all scripts for setting up, managing, and troubleshooting your WSL development environment.

---

## 🚀 Installation Scripts

### `Setup-WSL-DevEnvironment.ps1` (Windows PowerShell)
**Purpose:** Main Windows launcher for WSL setup
**Platform:** Windows (PowerShell)
**Usage:**
```powershell
.\Setup-WSL-DevEnvironment.ps1
```
**What it does:**
- Checks if WSL is installed
- Copies setup scripts to WSL
- Launches Linux setup automatically
- Creates desktop shortcuts (optional)
- Handles the entire installation process

**Options:**
```powershell
-CheckOnly    # Check WSL status without installing
-Help         # Show help message
```

---

### `setup_wsl_complete.sh` (Linux Bash)
**Purpose:** Complete WSL environment setup
**Platform:** WSL/Linux
**Usage:**
```bash
bash setup_wsl_complete.sh
```
**What it does:**
- Installs Node.js 20.x
- Installs Claude CLI (@anthropic-ai/claude-code)
- Installs Python 3, pip, and uv
- Clones and configures Clawd Discord Bot
- Clones and configures GSD (Get Shit Done)
- Installs VS Code
- Creates environment configuration (~/.wsl_dev_config)
- Sets up helpful aliases
- Creates verification and helper scripts

**Duration:** 5-10 minutes
**Internet Required:** Yes

---

### `setup_wsl_dev_environment.sh` (Legacy)
**Purpose:** Original setup script (deprecated, use `setup_wsl_complete.sh`)
**Platform:** WSL/Linux
**Status:** ⚠️ Deprecated - use setup_wsl_complete.sh instead

---

## 🔍 Detection & Verification Scripts

### `detect_wsl_distro.sh`
**Purpose:** Detect WSL distribution and capabilities
**Platform:** WSL/Linux
**Usage:**
```bash
bash detect_wsl_distro.sh
```
**Output:**
- Distribution name and version
- WSL version (1 or 2)
- Systemd status
- Package manager
- System resources (CPU, memory)

---

### `verify_wsl_setup.sh`
**Purpose:** Verify installation was successful
**Platform:** WSL/Linux
**Usage:**
```bash
bash ~/verify_wsl_setup.sh
```
**Created by:** setup_wsl_complete.sh (during installation)
**Checks:**
- ✓ All system tools installed
- ✓ Claude CLI working
- ✓ Clawd and GSD directories exist
- ✓ Configuration files present
- ✓ API keys configured
- ✓ Systemd status

**Run this after installation to ensure everything works!**

---

### `troubleshoot_wsl.sh`
**Purpose:** Comprehensive troubleshooting and diagnostics
**Platform:** WSL/Linux
**Usage:**
```bash
bash troubleshoot_wsl.sh
```
**Diagnoses:**
1. System & WSL status
2. Distribution information
3. Network connectivity
4. Node.js & npm
5. Python & pip
6. Claude CLI
7. Clawd Bot
8. GSD Framework
9. Configuration files
10. Resources & performance
11. Common issues

**Output:** Detailed report with fixes for any issues found

**Use this when:**
- Something isn't working
- After major updates
- Before asking for help

---

## 🔄 Update & Maintenance Scripts

### `update_all_wsl.sh`
**Purpose:** One-click update for everything
**Platform:** WSL/Linux
**Usage:**
```bash
bash update_all_wsl.sh
```
**Updates:**
1. System packages (apt)
2. Node.js global packages
3. Claude CLI
4. Python global packages + uv
5. Clawd Discord Bot
6. GSD Framework
7. VS Code extensions (manual)

**Recommended:** Run weekly
**Duration:** 3-5 minutes
**Internet Required:** Yes

---

## ⚙️ Configuration Templates

### `clawd_config_template.env`
**Purpose:** Environment variable template for Clawd
**Platform:** Any
**Usage:**
```bash
# Copy to Clawd directory
cp clawd_config_template.env ~/clawd/.env
# Edit with your values
nano ~/clawd/.env
```
**Contains:**
- Discord bot token
- Anthropic API key
- Bot behavior settings
- Rate limiting
- Logging configuration
- Database settings (if needed)
- Security settings

---

### `clawd-python.service`
**Purpose:** Systemd service for auto-starting Clawd (Python version)
**Platform:** WSL/Linux (with systemd)
**Usage:**
```bash
# 1. Edit the file and replace %USERNAME% and %HOME%
nano clawd-python.service

# 2. Copy to systemd directory
sudo cp clawd-python.service /etc/systemd/system/

# 3. Enable and start
sudo systemctl enable clawd-python
sudo systemctl start clawd-python

# 4. Check status
sudo systemctl status clawd-python
```

---

## 📁 Configuration Files

### `C:\Users\lucid\.wslconfig` (Windows)
**Purpose:** WSL2 performance optimization
**Platform:** Windows
**Location:** Windows user directory
**Edit with:** Windows Notepad or any text editor

**Key settings:**
```ini
[wsl2]
memory=8GB          # Memory for WSL
processors=4        # CPU cores
swap=2GB            # Swap memory
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
```

**After editing:** Run `wsl --shutdown` and restart WSL

---

### `~/.wsl_dev_config` (Linux)
**Purpose:** Environment variables and aliases
**Platform:** WSL/Linux
**Location:** Linux home directory
**Created by:** setup_wsl_complete.sh

**Contains:**
- API keys (CLAUDE_API_KEY, DISCORD_BOT_TOKEN)
- Path additions
- Helpful aliases (clawd, gsd, update-all, etc.)
- Environment functions (dev-status, update-all)

**Edit:**
```bash
nano ~/.wsl_dev_config
# Then reload:
source ~/.bashrc
```

---

## 📚 Documentation

### `docs/WSL_INSTALLATION_README.md`
**Purpose:** Complete installation and usage guide
**Sections:**
- What gets installed
- Quick start
- Detailed installation
- Configuration
- Verification & testing
- Daily usage
- Troubleshooting
- Updating
- Uninstalling
- Resources

### `docs/WSL_SETUP_GUIDE.md`
**Purpose:** Tool-specific setup guide
**Covers:**
- Claude CLI setup
- Clawd Bot configuration
- Windsurf IDE installation
- Troubleshooting per tool
- Advanced configuration

### `~/WSL_QUICK_START.md`
**Purpose:** Quick reference guide
**Created by:** setup_wsl_complete.sh (installed in WSL home)
**View:**
```bash
cat ~/WSL_QUICK_START.md
```

---

## 🎯 Quick Reference

### For First-Time Setup

**From Windows:**
```powershell
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts
.\Setup-WSL-DevEnvironment.ps1
```

**From WSL:**
```bash
bash ~/setup_wsl_complete.sh
```

---

### After Installation

**Verify:**
```bash
bash ~/verify_wsl_setup.sh
```

**Configure API keys:**
```bash
nano ~/.wsl_dev_config
source ~/.bashrc
```

**Test tools:**
```bash
claude --version
dev-status
```

---

### Daily/Weekly Maintenance

**Update everything:**
```bash
bash ~/update_all_wsl.sh
```

Or use alias:
```bash
update-all
```

---

### When Something Breaks

**Diagnose:**
```bash
bash ~/troubleshoot_wsl.sh
```

**Check status:**
```bash
dev-status
```

**View logs:**
```bash
# Clawd logs
tail -f ~/clawd/logs/clawd.log

# Systemd logs
journalctl -u clawd -f
```

---

## 📞 Getting Help

### Built-in Help

```bash
# Environment status
dev-status

# Verification
bash ~/verify_wsl_setup.sh

# Diagnostics
bash ~/troubleshoot_wsl.sh

# Quick start guide
cat ~/WSL_QUICK_START.md

# Full documentation
cat docs/WSL_INSTALLATION_README.md
```

### External Resources

- **Claude CLI:** https://github.com/anthropics/claude-code
- **Clawd Bot:** https://clawd.bot
- **GSD:** https://github.com/glittercowboy/get-shit-done
- **WSL Docs:** https://learn.microsoft.com/en-us/windows/wsl/

---

## 🗂️ File Structure

```
scripts/
├── Setup-WSL-DevEnvironment.ps1    # Windows PowerShell launcher
├── setup_wsl_complete.sh           # Main Linux setup script
├── setup_wsl_dev_environment.sh    # Legacy setup (deprecated)
├── detect_wsl_distro.sh            # Distribution detection
├── troubleshoot_wsl.sh             # Troubleshooting & diagnostics
├── update_all_wsl.sh               # Update everything
├── clawd_config_template.env       # Clawd configuration template
├── clawd-python.service            # Systemd service for Clawd
└── README.md                       # This file

docs/
├── WSL_INSTALLATION_README.md      # Complete installation guide
└── WSL_SETUP_GUIDE.md              # Tool-specific setup guide

C:\Users\lucid\
└── .wslconfig                      # WSL2 performance settings (Windows)

~/ (in WSL)
├── .wsl_dev_config                 # Environment variables & aliases
├── WSL_QUICK_START.md              # Quick reference
├── verify_wsl_setup.sh             # Verification script
├── clawd/                          # Clawd Discord Bot
└── get-shit-done/                  # GSD Framework
```

---

## 🎓 Tips

### Script Permissions

All scripts are executable. If you get "permission denied":
```bash
chmod +x script_name.sh
```

### Running from Anywhere

Add scripts directory to PATH (optional):
```bash
echo 'export PATH="$PATH:/path/to/scripts"' >> ~/.bashrc
source ~/.bashrc
```

### Backing Up Scripts

These scripts are in your Jarvis project. They're safe!

But if you want personal backups:
```bash
cp -r scripts/ ~/wsl_scripts_backup_$(date +%Y%m%d)
```

---

**Ready to get started?**

Run the installation and follow the docs! 🚀
