# 🚀 START HERE - WSL Development Environment Installation

**Complete setup for Claude CLI, Clawd Bot, Windsurf IDE, and GSD (Get Shit Done) on Windows Subsystem for Linux**

---

## ⚡ Quick Start (3 Steps)

### Step 1: Run the Installer (5-10 minutes)

Open **Windows PowerShell** and run:

```powershell
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts
.\Setup-WSL-DevEnvironment.ps1
```

The installer will:
- ✅ Check your WSL installation
- ✅ Install Claude CLI, Clawd Bot, GSD, and all dependencies
- ✅ Set up your development environment
- ✅ Create helper scripts and configuration

### Step 2: Configure API Keys (2 minutes)

After installation completes, open WSL:

```bash
wsl
```

Then edit your configuration:

```bash
nano ~/.wsl_dev_config
```

Add your API keys:

```bash
# Get from https://console.anthropic.com
export CLAUDE_API_KEY="sk-ant-your-key-here"

# Get from https://discord.com/developers
export DISCORD_BOT_TOKEN="your-discord-token-here"
```

Save (Ctrl+O, Enter, Ctrl+X) and reload:

```bash
source ~/.bashrc
```

### Step 3: Verify Everything Works (1 minute)

```bash
bash ~/verify_wsl_setup.sh
```

You should see all green checkmarks! ✅

---

## 🎯 What You Just Installed

### AI & Bot Frameworks
- **Claude CLI** - Command-line AI assistant
- **Clawd Bot** - Discord bot powered by Claude AI
- **GSD** - Get Shit Done productivity framework

### Development Tools
- **Node.js 20** - JavaScript runtime
- **Python 3** - With pip and uv package managers
- **VS Code** - Code editor with WSL support
- **Git, curl, wget** - Essential development tools

### Helper Scripts
- **Health check** - Daily environment status
- **Update script** - Update everything with one command
- **Troubleshoot** - Diagnose and fix issues
- **Verification** - Confirm installation success

---

## 📖 Using Your New Tools

### Claude CLI - AI Assistant

```bash
# Interactive mode
claude

# Ask a question
claude "Explain async/await in JavaScript"

# Help with code
claude "Write a Python function to calculate Fibonacci"
```

### Clawd Bot - Discord Integration

**Setup:**
1. Create a Discord bot at https://discord.com/developers
2. Copy your bot token
3. Add token to `~/.wsl_dev_config` or `~/clawd/.env`
4. Invite bot to your server

**Start the bot:**
```bash
# Manual start
cd ~/clawd
source venv/bin/activate  # if Python version
python main.py

# Or use convenience script
bash ~/start_all_services.sh
```

**Auto-start on boot (optional):**
```bash
sudo cp /tmp/clawd.service /etc/systemd/system/
sudo systemctl enable clawd
sudo systemctl start clawd
```

### GSD Framework

```bash
# Navigate to GSD
cd ~/get-shit-done

# Follow GSD-specific instructions in their repo
```

---

## 🛠️ Daily Commands

### Quick Status Check
```bash
# Full health check
bash ~/health_check_wsl.sh

# Or use alias
dev-status
```

### Start All Services
```bash
bash ~/start_all_services.sh
```

### Update Everything
```bash
# Update all packages and tools
bash ~/update_all_wsl.sh

# Or use alias
update-all
```

### View Logs
```bash
# Clawd bot logs
tail -f ~/clawd/logs/clawd.log

# System logs (if using systemd)
journalctl -u clawd -f
```

---

## 🔧 Troubleshooting

### Something Not Working?

Run the troubleshooting script:
```bash
bash ~/troubleshoot_wsl.sh
```

It will check everything and suggest fixes.

### Common Issues

**1. "claude: command not found"**
```bash
sudo npm install -g @anthropic-ai/claude-code
source ~/.bashrc
```

**2. Clawd bot won't start**
```bash
cd ~/clawd
source venv/bin/activate
pip install -r requirements.txt
```

**3. No internet in WSL**
```bash
# From Windows PowerShell:
wsl --shutdown
wsl
```

**4. Out of memory**

Edit `C:\Users\lucid\.wslconfig`:
```ini
[wsl2]
memory=12GB  # Increase this
```

Then restart: `wsl --shutdown`

---

## 📚 Documentation

All documentation is in the [docs/](../docs/) folder:

- **[WSL_INSTALLATION_README.md](WSL_INSTALLATION_README.md)** - Complete installation guide
- **[WSL_SETUP_GUIDE.md](WSL_SETUP_GUIDE.md)** - Tool-specific setup instructions
- **[scripts/README.md](../scripts/README.md)** - Script index and reference

In WSL:
- `~/WSL_QUICK_START.md` - Quick reference guide
- `~/verify_wsl_setup.sh` - Verification script
- `~/health_check_wsl.sh` - Health monitoring
- `~/troubleshoot_wsl.sh` - Troubleshooting
- `~/update_all_wsl.sh` - Update script
- `~/start_all_services.sh` - Start all services

---

## 🎓 Next Steps

### 1. Test Claude CLI
```bash
claude "Write a haiku about WSL"
```

### 2. Configure and Test Clawd
```bash
cd ~/clawd
nano .env  # Add your Discord token
bash ~/start_all_services.sh
```

### 3. Explore GSD
```bash
cd ~/get-shit-done
# Check their documentation
cat README.md
```

### 4. Set Up Windsurf IDE

**Option A:** Install on Windows, access WSL files via:
```
\\wsl$\Ubuntu\home\<username>
```

**Option B:** Install in WSL (requires WSLg):
```bash
# Download Windsurf installer
wget https://windsurf.com/download/linux -O windsurf.deb
sudo dpkg -i windsurf.deb
```

### 5. Create Your First Discord Bot Command

Follow Clawd documentation to add custom commands to your bot!

### 6. Integrate Everything

- Use Claude CLI for coding help
- Use Clawd to interact via Discord
- Use GSD for project management
- Code in VS Code or Windsurf

---

## 🔐 Security Best Practices

### 1. Protect Your API Keys

Never commit keys to git:
```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo ".wsl_dev_config" >> .gitignore
```

### 2. Backup Your Configuration
```bash
# Backup config (without committing to git)
cp ~/.wsl_dev_config ~/backup_config_$(date +%Y%m%d).sh
```

### 3. Limit Bot Permissions

In Discord Developer Portal:
- Only enable required permissions
- Use role-based access control
- Enable 2FA on your Discord account

---

## 🌟 Pro Tips

### 1. Use Aliases

These are automatically set up for you:
```bash
clawd              # cd ~/clawd
gsd                # cd ~/get-shit-done
update-all         # Update everything
dev-status         # Environment status
activate-clawd     # Activate Clawd venv
```

### 2. Monitor Resources
```bash
htop               # Interactive process viewer
free -h            # Memory usage
df -h              # Disk usage
```

### 3. Keep Things Updated
```bash
# Weekly routine:
update-all                    # Update all packages
bash ~/health_check_wsl.sh    # Check health
```

### 4. Use VS Code Remote - WSL

Install "Remote - WSL" extension in VS Code, then:
```bash
code .  # Opens current directory in VS Code
```

### 5. Access WSL from Windows

In Windows Explorer address bar:
```
\\wsl$\Ubuntu\home\<your-username>
```

---

## 🆘 Getting Help

### Built-in Help
```bash
dev-status                        # Environment status
bash ~/verify_wsl_setup.sh        # Verify installation
bash ~/troubleshoot_wsl.sh        # Diagnose issues
bash ~/health_check_wsl.sh        # Health check
```

### External Resources

- **Claude CLI:** https://github.com/anthropics/claude-code
- **Clawd Bot:** https://clawd.bot
- **GSD:** https://github.com/glittercowboy/get-shit-done
- **WSL Docs:** https://learn.microsoft.com/en-us/windows/wsl/

### API Keys & Accounts

- **Anthropic:** https://console.anthropic.com
- **Discord:** https://discord.com/developers

---

## 🎉 You're Ready!

Your complete WSL development environment is now set up with:

✅ **Claude CLI** - AI assistant at your fingertips
✅ **Clawd Bot** - Discord integration with Claude
✅ **GSD** - Productivity framework
✅ **Full dev stack** - Node.js, Python, VS Code
✅ **Helper scripts** - Health checks, updates, troubleshooting

**What's next?**

1. ✅ Configure your API keys (Step 2 above)
2. ✅ Run verification (Step 3 above)
3. ✅ Test Claude CLI
4. ✅ Start Clawd bot
5. ✅ Start building amazing things!

---

## 📋 Quick Reference Card

Save this for daily use:

```bash
# Status & Health
dev-status                        # Quick status
bash ~/health_check_wsl.sh        # Full health check
bash ~/verify_wsl_setup.sh        # Verify setup

# Services
bash ~/start_all_services.sh      # Start all services
pkill -f clawd                    # Stop Clawd bot
journalctl -u clawd -f            # View systemd logs

# Maintenance
update-all                        # Update everything
bash ~/troubleshoot_wsl.sh        # Troubleshoot issues

# Navigation
clawd                             # Go to Clawd
gsd                               # Go to GSD

# Configuration
nano ~/.wsl_dev_config            # Edit config
source ~/.bashrc                  # Reload config
```

---

**Ready to get started? Run Step 1 above!** 🚀

If you have any questions, check the troubleshooting guide or run:
```bash
bash ~/troubleshoot_wsl.sh
```

Happy coding! 💻✨
