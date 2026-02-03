# Dental Lead Qualifier - Python + Claude Code CLI + GLM

Simple Python alternative to the complex n8n workflow.

## What it does
```
Slack Webhook → Extract Lead → SerpAPI Search → Claude Code (GLM) → Slack Reply
```

## Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Claude Code CLI with GLM

Edit `~/.config/claude-code/config.json` (or `C:\Users\YOURUSER\.claude\config.json` on Windows):

```json
{
  "apiProvider": "openai-compatible",
  "apiKey": "6024c744cdc4468b8b337ff4df5038be.mmQhTB8WHG1rSXOp",
  "baseUrl": "https://api.z.ai/api/coding/paas/v4",
  "modelId": "glm-4"
}
```

### 3. Set environment variables (optional)
```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SERPAPI_KEY="..."
export PORT=5678
```

Or edit the defaults in `lead_qualifier.py`.

### 4. Run the server
```bash
python lead_qualifier.py
```

### 5. Point Slack webhook to your server
Use Cloudflare Tunnel or ngrok to expose localhost:

```bash
cloudflare tunnel --url http://localhost:5678
```

Then add the webhook URL to your Slack app:
```
https://your-tunnel-url.cloudflare.net/webhook
```

## Files
- `lead_qualifier.py` - Main server (reuses all n8n logic)
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Features
- ✅ Lead extraction (same regex as n8n)
- ✅ SerpAPI dentist verification
- ✅ Claude Code CLI with GLM-4
- ✅ JSON response parsing
- ✅ Slack reply with emoji/status
- ✅ Error handling & logging
