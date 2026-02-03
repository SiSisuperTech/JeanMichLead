# Slack Setup Guide for Dental Lead Qualifier

## Step 1: Get Your Public URL

Run `start.bat` and wait for the Cloudflare tunnel to start. You'll see a URL like:
```
https://chronicles-pulse-while-serving.trycloudflare.com
```

**Your webhook URL will be:**
```
https://chronicles-pulse-while-serving.trycloudflare.com/webhook
```

---

## Step 2: Create a Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter:
   - **App Name**: `Dental Lead Qualifier`
   - **Pick a workspace**: Select your workspace
5. Click **"Create App"**

---

## Step 3: Configure Permissions

1. In the left sidebar, click **"OAuth & Permissions"**
2. Scroll to **"Scopes"** → **"Bot Token Scopes"**
3. Add these scopes:
   - `chat:write` - Send messages
   - `channels:history` - Read messages
   - `groups:history` - Read private channel messages
   - `im:history` - Read DMs
   - `mpim:history` - Read group DMs

---

## Step 4: Install App to Workspace

1. Scroll to top of **"OAuth & Permissions"** page
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. **Copy the Bot User OAuth Token** (starts with `xoxb-`)
   - Save this token!

---

## Step 5: Enable Events

1. In left sidebar, click **"Event Subscriptions"**
2. Turn **"Enable Events"** to **ON**
3. In **"Request URL"**, paste your webhook URL:
   ```
   https://chronicles-pulse-while-serving.trycloudflare.com/webhook
   ```
4. Wait for **"Verified"** green checkmark
5. Scroll to **"Subscribe to bot events"**
6. Add these events:
   - `message.channels` - Messages in public channels
   - `message.groups` - Messages in private channels
   - `message.im` - Direct messages
   - `message.mpim` - Group DMs
7. Click **"Save Changes"**

---

## Step 6: Add Bot to Channel

1. Go to your Slack workspace
2. Open the channel where leads will be posted
3. Type: `/invite @Dental Lead Qualifier`
4. Or go to channel settings → **"Add apps"** → Select your bot

---

## Step 7: Update Your Token (Optional)

If you want to use your own token instead of the hardcoded one:

1. Open `lead_qualifier_full.py`
2. Find line 32:
   ```python
   SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "xoxb-...")
   ```
3. Replace the hardcoded token with yours, OR
4. Set environment variable:
   ```cmd
   set SLACK_BOT_TOKEN=xoxb-your-token-here
   start.bat
   ```

---

## Step 8: Test It

1. Make sure `start.bat` is running with Cloudflare tunnel active
2. Post a test message in your Slack channel with lead info
3. The bot should:
   - Extract lead data
   - Check HubSpot
   - Verify with AI
   - Reply with qualification status

---

## Troubleshooting

### "Request URL not verified"
- Make sure `start.bat` is running
- Check the URL is correct (ends with `/webhook`)
- Wait a few seconds and try again

### Bot not responding
- Check bot is added to the channel
- Verify bot has `chat:write` permission
- Check server logs in the terminal

### "URL verification failed"
- The server must be running before you add the URL
- Cloudflare tunnel must be active
- Try refreshing the page and re-adding the URL

---

## Quick Reference

**Webhook URL format:**
```
https://[your-tunnel-url].trycloudflare.com/webhook
```

**Required Slack Scopes:**
- `chat:write`
- `channels:history`
- `groups:history`
- `im:history`
- `mpim:history`

**Required Events:**
- `message.channels`
- `message.groups`
- `message.im`
- `message.mpim`
