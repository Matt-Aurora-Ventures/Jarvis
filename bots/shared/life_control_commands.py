"""
Life Control Commands for ClawdBots.

Provides full autonomous control via Telegram:
- /do <anything> - Natural language control
- /email - Gmail operations
- /calendar - Calendar management
- /drive - Google Drive/Docs
- /deploy - Website deployment
- /firebase - Firebase/Google Cloud
- /phone - Android phone control
- /wallet - Solana wallet operations
- /pay - Payment operations

Import this into ClawdJarvis to add all commands.
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

# Add paths
sys.path.insert(0, '/root/clawdbots')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import capabilities
try:
    from shared.computer_capabilities import (
        browse_web,
        control_computer,
        check_remote_status,
    )
    HAS_REMOTE = True
except ImportError:
    HAS_REMOTE = False
    logger.warning("Remote control not available")


# ============================================
# COMMAND HANDLERS
# ============================================

def register_life_commands(bot):
    """Register all life control commands on the bot."""

    @bot.message_handler(commands=['do', 'jarvis'])
    async def handle_do(message):
        """
        Execute ANY natural language request.

        Usage: /do <what you want>

        Examples:
        /do Send John an email about the meeting
        /do Check my calendar for tomorrow
        /do Deploy the website changes
        /do Create a new Firebase project
        """
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        request = message.text.split(' ', 1)[1] if ' ' in message.text else ''
        if not request:
            await bot.reply_to(message, """
🤖 **Jarvis Life Control**

Just tell me what you want:

`/do Send an email to John about the project`
`/do Check my calendar for next week`
`/do Deploy website to hostinger`
`/do Create a Firebase project called MyApp`
`/do Check Google Cloud billing`

I can control:
- 📧 Gmail, Calendar, Drive, Docs
- ☁️ Google Cloud, Firebase, AI Studio
- 🌐 Hostinger, Vercel, servers
- 📱 Your Android phone
- 💻 Your Windows PC
- 💰 Solana wallet
""", parse_mode='Markdown')
            return

        await bot.reply_to(message, f"🤖 Processing: {request[:50]}...")

        try:
            # Route to computer control which handles everything
            result = await control_computer(f"""
Execute this request: {request}

You have access to:
- Browser (logged into Google, Hostinger, etc.)
- SSH to servers
- Full computer control
- File system access

Do whatever is needed to complete this request and report the result.
""")
            response = f"✅ **Result:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['email', 'gmail', 'mail'])
    async def handle_email(message):
        """Gmail operations."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        request = message.text.split(' ', 1)[1] if ' ' in message.text else 'check inbox'

        await bot.reply_to(message, f"📧 Email: {request[:50]}...")

        try:
            result = await browse_web(f"""
Go to Gmail (https://mail.google.com).
{request}

If sending email: Click Compose, fill in details, send.
If reading: Show recent emails with subjects and senders.
Report what you did.
""")
            response = f"📧 **Gmail:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['calendar', 'cal', 'schedule'])
    async def handle_calendar(message):
        """Google Calendar operations."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        request = message.text.split(' ', 1)[1] if ' ' in message.text else 'show today'

        await bot.reply_to(message, f"📅 Calendar: {request[:50]}...")

        try:
            result = await browse_web(f"""
Go to Google Calendar (https://calendar.google.com).
{request}

Show events with time, title, and location.
""")
            response = f"📅 **Calendar:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['drive', 'docs', 'sheets'])
    async def handle_drive(message):
        """Google Drive/Docs operations."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        request = message.text.split(' ', 1)[1] if ' ' in message.text else 'show recent'

        await bot.reply_to(message, f"📁 Drive: {request[:50]}...")

        try:
            result = await browse_web(f"""
Go to Google Drive (https://drive.google.com).
{request}
""")
            response = f"📁 **Drive:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['deploy', 'host', 'hostinger'])
    async def handle_deploy(message):
        """Website deployment."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        request = message.text.split(' ', 1)[1] if ' ' in message.text else 'check status'

        await bot.reply_to(message, f"🚀 Deploy: {request[:50]}...")

        try:
            if 'deploy' in request.lower():
                result = await control_computer(f"""
Deploy website: {request}

Steps:
1. SSH to the server
2. cd to website directory
3. git pull origin main
4. npm install (if needed)
5. npm run build (if needed)
6. Restart services

Report deployment status.
""")
            else:
                result = await browse_web(f"""
Go to Hostinger panel (https://hpanel.hostinger.com).
{request}
""")
            response = f"🚀 **Deploy:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['firebase', 'gcloud', 'cloud'])
    async def handle_firebase(message):
        """Firebase/Google Cloud operations."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        request = message.text.split(' ', 1)[1] if ' ' in message.text else 'show projects'

        await bot.reply_to(message, f"☁️ Cloud: {request[:50]}...")

        try:
            url = 'https://console.firebase.google.com' if 'firebase' in message.text.lower() else 'https://console.cloud.google.com'
            result = await browse_web(f"""
Go to {url}.
{request}
""")
            response = f"☁️ **Cloud:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['billing'])
    async def handle_billing(message):
        """Google Cloud billing."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        await bot.reply_to(message, "💳 Checking billing...")

        try:
            result = await browse_web("""
Go to Google Cloud Billing (https://console.cloud.google.com/billing).
Show:
- Current month charges
- Active projects
- Payment method on file
""")
            response = f"💳 **Billing:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['wallet', 'sol', 'solana'])
    async def handle_wallet(message):
        """Solana wallet operations."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        request = message.text.split(' ', 1)[1] if ' ' in message.text else 'check balance'

        await bot.reply_to(message, f"💰 Wallet: {request[:50]}...")

        try:
            result = await control_computer(f"""
Solana wallet operation: {request}

Access the treasury wallet and:
- If checking balance: Show SOL and token balances
- If sending: Prepare transaction (DO NOT execute without confirmation)
- If swapping: Use Jupiter aggregator

Report the result.
""")
            response = f"💰 **Wallet:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['phone', 'android'])
    async def handle_phone(message):
        """Android phone control."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        request = message.text.split(' ', 1)[1] if ' ' in message.text else 'battery'

        await bot.reply_to(message, f"📱 Phone: {request[:50]}...")

        try:
            result = await control_computer(f"""
Android phone control via ADB over Tailscale:

First connect: adb connect 100.88.183.6:5555

Then: {request}

Report the result.
""")
            response = f"📱 **Phone:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['screenshot', 'screen'])
    async def handle_screenshot(message):
        """Take screenshot."""
        if not HAS_REMOTE:
            await bot.reply_to(message, "❌ Remote control not available")
            return

        await bot.reply_to(message, "📸 Taking screenshot...")

        try:
            result = await control_computer("""
Take a screenshot of the entire desktop.
Save it to the Desktop folder.
Report the file path.
""")
            response = f"📸 **Screenshot:**\n\n{result[:3500]}"
        except Exception as e:
            response = f"❌ Error: {str(e)}"

        await bot.reply_to(message, response, parse_mode='Markdown')

    @bot.message_handler(commands=['help', 'commands'])
    async def handle_help_extended(message):
        """Show all available commands."""
        help_text = """
🤖 **Jarvis Full Life Control**

**Universal:**
`/do <anything>` - Just say what you want

**Google Suite:**
`/email [request]` - Gmail operations
`/calendar [request]` - Calendar management
`/drive [request]` - Drive/Docs/Sheets
`/firebase [request]` - Firebase projects
`/cloud [request]` - Google Cloud Console
`/billing` - Check GCP billing

**Servers & Websites:**
`/deploy [request]` - Deploy websites
`/host [request]` - Hostinger panel

**Devices:**
`/computer [task]` - PC control
`/browse [task]` - Browser automation
`/phone [command]` - Android control
`/screenshot` - Take screenshot

**Finance:**
`/wallet [request]` - Solana wallet
`/billing` - GCP billing

**Examples:**
`/do Send John an email about tomorrow's meeting`
`/calendar add meeting with Bob on Friday at 3pm`
`/deploy latest changes to hostinger`
`/wallet check balance`
"""
        await bot.reply_to(message, help_text, parse_mode='Markdown')

    return bot
