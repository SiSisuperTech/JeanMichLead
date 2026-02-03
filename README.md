# JeanMichLead - Dental Lead Qualifier

AI-powered dental lead qualification system. Automatically qualifies leads from Slack webhooks using AI analysis and updates HubSpot CRM.

## How It Works

```
Slack Message → Extract Lead Data → AI Analysis (GLM-4.7) → HubSpot Update → Emoji Reaction
```

## Features

- **Slack Integration**: Receives lead notifications via webhook
- **AI Qualification**: Uses GLM-4.7 via z.ai API to qualify dentists
- **HubSpot CRM**: Updates lead status automatically
- **Smart Scoring**: 0-100 score based on verification
- **Duplicate Prevention**: Email-based deduplication (5 min window)
- **24/7 Operation**: Auto-restart on crashes

## Quick Start (Local)

### Windows
```batch
deploy.bat    # One-time setup
start.bat     # Run the app
```

The app will:
1. Start Flask server on `http://localhost:5678`
2. Open ngrok tunnel for public access
3. Show your public webhook URL

## Railway Deployment (Cloud 24/7)

### 1. Push to GitHub
Already done: https://github.com/SiSisuperTech/JeanMichLead

### 2. Deploy on Railway
1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Select **JeanMichLead**
4. Click **Deploy**

### 3. Set Environment Variables

In Railway dashboard, add these variables:

| Name | Value |
|------|-------|
| `SLACK_BOT_TOKEN` | Your Slack bot token (xoxb-...) |
| `HUBSPOT_TOKEN` | Your HubSpot token (pat-...) |
| `ANTHROPIC_AUTH_TOKEN` | Your z.ai API key |
| `ANTHROPIC_BASE_URL` | `https://api.z.ai/api/anthropic` |

### 4. Update Slack Webhook

Railway will give you a URL like:
`https://jeanmichlead.up.railway.app`

Update your Slack app webhook to:
`https://jeanmichlead.up.railway.app/webhook`

## Slack Configuration

Required bot scopes:
- `chat:write` - Send messages
- `reactions:write` - Add emoji reactions
- `channels:read` - Read channel info
- `im:write` - Send DMs
- `users:read` - Read user info

## HubSpot Integration

The app can:
- ✅ Search contacts by email
- ✅ Create new contacts
- ✅ Update `hs_lead_status`:
  - `Qualified` - Score 70+
  - `KO` - Low score
  - `To qualify` - New leads

## Files

| File | Purpose |
|------|---------|
| `lead_qualifier_full.py` | Main Flask application |
| `requirements.txt` | Python dependencies |
| `railway.json` | Railway deployment config |
| `start.bat` | Local launcher (Windows) |
| `deploy.bat` | One-time setup (Windows) |
| `start_service.bat` | 24/7 mode with auto-restart |
| `install_service.bat` | Install Windows auto-start |

## Dashboard

When running, access the dashboard at:
```
http://localhost:5678/
```

Shows:
- Recent activity
- Statistics (qualified, spam, total)
- System health

## License

MIT
