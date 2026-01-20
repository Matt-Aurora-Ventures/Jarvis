# VPS SSH Key Setup Instructions

SSH password authentication is failing. Here's how to set up key-based auth manually.

## Your Public Key (copy this)

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILDBPOlpfaWIOMW3ZsCdeII4WovyUe0hshbUAlk00bI4 jarvis-deployment
```

## Option 1: Via Hostinger Control Panel (Recommended)

1. Log into Hostinger: https://hpanel.hostinger.com/
2. Go to VPS → Your VPS → Settings → SSH Keys
3. Click "Add SSH Key"
4. Paste the public key above
5. Save

## Option 2: Via Web Console

1. Log into Hostinger control panel
2. Go to VPS → Your VPS → Overview → "Access VPS" (web console)
3. Log in as root
4. Run these commands:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILDBPOlpfaWIOMW3ZsCdeII4WovyUe0hshbUAlk00bI4 jarvis-deployment" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

## Option 3: Reset VPS Password

1. Log into Hostinger control panel
2. Go to VPS → Your VPS → Settings → Reset Root Password
3. Update the password in your `.env` file:
   ```
   VPS_PASSWORD=new_password_here
   ```
4. Run: `python scripts/setup_ssh_key.py`

## After Setup - Test Connection

```bash
ssh jarvis-vps
# Or
ssh root@72.61.7.126
```

If successful, you'll connect without being prompted for a password.

## Deploy to VPS

Once SSH key is set up:

```bash
ssh jarvis-vps "cd ~/Jarvis && git pull origin main && pkill -f supervisor.py; nohup python bots/supervisor.py > /tmp/supervisor.log 2>&1 &"
```

Or use the deploy script:
```bash
python scripts/deploy.py production
```
