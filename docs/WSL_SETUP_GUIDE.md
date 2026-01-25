# WSL Development Environment Setup Guide

Complete guide for setting up Claude CLI, Clawd Bot, and Windsurf on Windows Subsystem for Linux.

## Quick Start

### 1. Transfer Setup Script to WSL

From Windows PowerShell or CMD:
```powershell
# Copy the setup script to your WSL home directory
wsl cp /mnt/c/Users/lucid/OneDrive/Desktop/Projects/Jarvis/scripts/setup_wsl_dev_environment.sh ~/setup_wsl.sh
```

Or from within WSL:
```bash
cp /mnt/c/Users/lucid/OneDrive/Desktop/Projects/Jarvis/scripts/setup_wsl_dev_environment.sh ~/setup_wsl.sh
chmod +x ~/setup_wsl.sh
```

### 2. Run the Setup Script

```bash
cd ~
bash setup_wsl.sh
```

The script will:
- ✓ Update system packages
- ✓ Install Node.js 20.x
- ✓ Install Claude CLI globally
- ✓ Install Python 3 and pip
- ✓ Clone and setup Clawd bot
- ✓ Install VS Code
- ✓ Configure environment variables
- ✓ Create helpful aliases
- ✓ Generate verification script

### 3. Configure API Keys

Edit `~/.wsl_dev_config`:
```bash
nano ~/.wsl_dev_config
```

Add your keys:
```bash
export CLAUDE_API_KEY="sk-ant-..."  # Get from https://console.anthropic.com
export DISCORD_BOT_TOKEN="..."      # Get from Discord Developer Portal
```

### 4. Reload Environment

```bash
source ~/.bashrc
```

### 5. Verify Installation

```bash
bash ~/verify_wsl_setup.sh
```

Expected output:
```
=== WSL Development Environment Verification ===

1. System Tools:
✓ curl: /usr/bin/curl
✓ git: /usr/bin/git
✓ node: /usr/bin/node
✓ npm: /usr/bin/npm
✓ python3: /usr/bin/python3

2. Development Tools:
✓ claude: /usr/local/bin/claude
✓ code: /usr/bin/code

3. Clawd Bot:
✓ Clawd directory: /home/user/clawd
  ✓ Python virtual environment found

4. Configuration:
✓ WSL dev config: /home/user/.wsl_dev_config
```

## Tool-Specific Setup

### Claude CLI

#### First-Time Authentication
```bash
claude auth login
```

Follow the prompts to authenticate with your Anthropic API key.

#### Test Claude CLI
```bash
# Check version
claude --version

# Start interactive session
claude

# Run a quick test
claude "Write a hello world in Python"
```

#### Configuration
Edit `~/.config/claude/config.json` to customize:
- Default model
- API settings
- Output preferences

### Clawd Bot (Discord Bot Framework)

#### Navigate to Clawd Directory
```bash
cd ~/clawd
# Or use the alias
clawd
```

#### Configuration

1. **Create Discord Bot**:
   - Go to https://discord.com/developers/applications
   - Create new application
   - Go to "Bot" section
   - Copy bot token
   - Enable necessary intents (Message Content, Server Members, etc.)

2. **Configure Clawd**:
   ```bash
   # If Clawd uses .env file
   cp .env.example .env
   nano .env
   ```

   Add:
   ```
   DISCORD_BOT_TOKEN=your_token_here
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **For Python-based Clawd**:
   ```bash
   # Activate virtual environment
   source venv/bin/activate

   # Or use alias
   activate-clawd

   # Install additional dependencies if needed
   pip install discord.py anthropic
   ```

4. **For Node.js-based Clawd**:
   ```bash
   # Dependencies should already be installed
   # Check package.json for scripts
   npm run start
   ```

#### Running Clawd
```bash
cd ~/clawd

# Python version
source venv/bin/activate
python main.py  # or python bot.py, check README

# Node.js version
npm start  # or node index.js
```

#### Invite Bot to Discord Server
1. Go to Discord Developer Portal
2. OAuth2 → URL Generator
3. Select scopes: `bot`, `applications.commands`
4. Select bot permissions needed
5. Copy generated URL and open in browser
6. Select server and authorize

### Windsurf IDE

#### Installation Options

**Option 1: VS Code Extension**
```bash
# If Windsurf is a VS Code extension
code --install-extension windsurf.windsurf-vscode
```

**Option 2: Standalone Application**
Visit https://windsurf.com and download the Linux installer:
```bash
# Download .deb package
wget https://windsurf.com/download/linux -O windsurf.deb

# Install
sudo dpkg -i windsurf.deb
sudo apt-get install -f  # Fix dependencies

# Run
windsurf
```

**Option 3: WSL + Windows GUI**
- Install Windsurf on Windows
- Access WSL files from Windows: `\\wsl$\Ubuntu\home\username`
- Open WSL projects directly in Windows Windsurf

## Useful Commands

### Aliases (automatically added)
```bash
clawd              # Navigate to Clawd directory
activate-clawd     # Activate Clawd Python venv
update-dev         # Update all system packages
claude-version     # Check Claude CLI version
```

### Manual Commands
```bash
# Update Claude CLI
sudo npm update -g @anthropic-ai/claude-code

# Update Clawd
cd ~/clawd
git pull
npm install  # or pip install -r requirements.txt

# Check WSL version
wsl --version

# Check WSL status from Windows
wsl --status
```

## Troubleshooting

### Claude CLI Issues

**Problem**: `claude: command not found`
```bash
# Reinstall globally
sudo npm install -g @anthropic-ai/claude-code

# Check npm global bin path
npm config get prefix

# Add to PATH if needed
echo 'export PATH="$(npm config get prefix)/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Problem**: Authentication fails
```bash
# Re-authenticate
claude auth logout
claude auth login

# Check API key format (should start with sk-ant-)
echo $CLAUDE_API_KEY
```

### Clawd Bot Issues

**Problem**: Module not found errors
```bash
cd ~/clawd
# For Python
source venv/bin/activate
pip install --upgrade -r requirements.txt

# For Node.js
npm install
```

**Problem**: Discord connection fails
- Verify bot token in `.env` or `~/.wsl_dev_config`
- Check bot is invited to server
- Ensure required intents are enabled in Discord Developer Portal
- Check firewall/network settings

### WSL General Issues

**Problem**: Cannot access internet
```bash
# Check DNS
cat /etc/resolv.conf

# Reset WSL networking (from Windows PowerShell as admin)
wsl --shutdown
```

**Problem**: Slow performance
```bash
# Check .wslconfig in Windows user directory
# C:\Users\lucid\.wslconfig

[wsl2]
memory=8GB
processors=4
swap=2GB
```

**Problem**: File permissions issues
```bash
# Windows files in WSL have different permissions
# Copy files to WSL filesystem for better performance
cp /mnt/c/path/to/file ~/

# Or use WSL home directory for development
```

## Advanced Configuration

### Auto-start Clawd on WSL Boot

Create systemd service (if WSL supports systemd):
```bash
sudo nano /etc/systemd/system/clawd.service
```

```ini
[Unit]
Description=Clawd Discord Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/clawd
ExecStart=/home/your_username/clawd/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable clawd
sudo systemctl start clawd
sudo systemctl status clawd
```

### WSL Performance Optimization

Edit `C:\Users\lucid\.wslconfig`:
```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
```

### Integration with Windows

**Access WSL from Windows Explorer**:
- Address bar: `\\wsl$\Ubuntu\home\username`

**Run WSL commands from Windows**:
```powershell
wsl ls -la
wsl cd ~/clawd && npm start
```

**Access Windows files from WSL**:
```bash
cd /mnt/c/Users/lucid/
```

## Updating Everything

Create an update script or run:
```bash
# System packages
sudo apt-get update && sudo apt-get upgrade -y

# Node.js global packages
sudo npm update -g

# Claude CLI specifically
sudo npm update -g @anthropic-ai/claude-code

# Clawd bot
cd ~/clawd
git pull
npm install  # or pip install -r requirements.txt
```

## Resources

- **Claude CLI**: https://github.com/anthropics/claude-code
- **Clawd Bot**: https://clawd.bot / https://github.com/chand1012/clawd
- **Windsurf**: https://windsurf.com
- **Anthropic Console**: https://console.anthropic.com
- **Discord Developer Portal**: https://discord.com/developers
- **WSL Documentation**: https://learn.microsoft.com/en-us/windows/wsl/

## Next Steps

1. Configure your API keys in `~/.wsl_dev_config`
2. Test Claude CLI with a simple query
3. Set up your Clawd Discord bot
4. Install Windsurf IDE
5. Create your first Discord bot command
6. Integrate all three tools in your workflow

Happy coding! 🚀
