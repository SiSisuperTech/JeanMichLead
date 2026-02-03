# Railway Deployment Guide

## Step 1: Push to GitHub

1. Create a new GitHub repo
2. Push these files:
   - `lead_qualifier_full.py`
   - `requirements.txt`
   - `railway.json`
   - `.claude/config.json` (contains API keys)

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin YOUR_REPO_URL
git push -u origin main
```

## Step 2: Deploy on Railway

1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Select your repo
4. Railway will auto-detect Python and deploy

## Step 3: Set Environment Variables

In Railway dashboard, add these variables:

| Name | Value |
|------|-------|
| `SLACK_BOT_TOKEN` | Your Slack bot token (xoxb-...) |
| `HUBSPOT_TOKEN` | Your HubSpot token (pat-...) |
| `ANTHROPIC_AUTH_TOKEN` | Your z.ai API key |
| `ANTHROPIC_BASE_URL` | `https://api.z.ai/api/anthropic` |

## Step 4: Get Your URL

Railway will give you a URL like:
`https://your-app.up.railway.app`

Update your Slack webhook to:
`https://your-app.up.railway.app/webhook`

## Done!

Your app runs 24/7 with:
- Automatic HTTPS
- Auto-restart on crashes
- Real public URL (no ngrok needed)
