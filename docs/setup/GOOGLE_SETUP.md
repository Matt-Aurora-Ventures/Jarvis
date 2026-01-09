# Google API Integration Setup

This guide helps you set up Jarvis to autonomously use your Google services.

## 🚀 What Jarvis Can Do With Google

- **Drive Sync**: Automatically sync files to local storage
- **Gmail Monitoring**: Scan for important emails
- **Calendar Sync**: Keep track of upcoming events
- **Content Analysis**: Understand your work patterns
- **Auto-Organization**: Organize files into folders
- **Document Creation**: Create Google Docs from research

## 📋 One-Time Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "Jarvis Integration")
3. Note your Project ID

### 2. Enable APIs

Enable these APIs in your project:
- Google Drive API
- Gmail API
- Google Calendar API
- Google Sheets API
- Google Docs API

### 3. Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Select "Desktop application"
4. Name it "Jarvis Desktop"
5. Click "Create"
6. Download the JSON file or note:
   - Client ID
   - Client Secret

### 4. Configure Jarvis

Option A: Via API
```bash
curl -X POST http://localhost:8765/api/google/setup \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "project_id": "YOUR_PROJECT_ID"
  }'
```

Option B: Via Python
```python
from core import google_integration

integration = google_integration.get_google_integration()
integration.setup_credentials(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    project_id="YOUR_PROJECT_ID"
)
```

### 5. Authenticate

Option A: Via API
```bash
curl -X POST http://localhost:8765/api/google/authenticate \
  -H "Content-Type: application/json" \
  -d '{
    "services": ["drive", "gmail", "calendar", "sheets"]
  }'
```

Option B: Via Python
```python
from core import google_integration

integration = google_integration.get_google_integration()
result = integration.authenticate(["drive", "gmail", "calendar", "sheets"])
print(result)
```

This will open your browser for one-time consent.

## 🔧 Usage

### Check Status
```bash
curl http://localhost:8765/api/google/status
```

### Manual Sync
```bash
curl -X POST http://localhost:8765/api/google/sync \
  -H "Content-Type: application/json" \
  -d '{"service": "all"}'
```

### Sync Specific Service
```bash
curl -X POST http://localhost:8765/api/google/sync \
  -H "Content-Type: application/json" \
  -d '{"service": "drive"}'
```

## 📊 Autonomous Features

Once authenticated, Jarvis will automatically:

1. **Every 15 minutes**:
   - Sync new Drive files
   - Check for important emails
   - Update calendar events
   - Analyze content patterns

2. **Smart Organization**:
   - Auto-organize files into folders
   - Detect work patterns
   - Create insights from your data

3. **Context Integration**:
   - Add calendar events to context
   - Include important emails
   - Reference Drive documents

## 🔒 Security

- Credentials stored in `secrets/google_credentials.json`
- OAuth tokens in `secrets/google_token.pickle`
- Only requested permissions are used
- No data shared with third parties

## 🛠 Troubleshooting

### "Invalid Credentials"
- Check Client ID and Secret are correct
- Ensure OAuth redirect URI is `http://localhost:8080`

### "API Not Enabled"
- Enable all required APIs in Google Cloud Console
- Wait a few minutes for changes to propagate

### "Insufficient Permissions"
- Re-authenticate with additional scopes
- Check account has access to services

## 📈 API Quotas

Google APIs have daily quotas:
- Drive: 1 billion requests
- Gmail: 1 billion requests
- Calendar: 1 million requests

Jarvis uses minimal requests and stays well within limits.

## 🔄 Data Sync Locations

- Drive files: `data/google_data/drive/`
- Email summaries: Stored in context
- Calendar events: Stored in context
- Analysis results: `data/google_config.json`

## 🎯 Next Steps

Once set up, Jarvis will:
1. Learn from your Google services
2. Improve organization
3. Provide intelligent assistance
4. Sync important information automatically

The system is designed to be autonomous after initial setup!
