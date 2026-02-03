# 🦷 Dental Lead Qualifier - Production

> **Production-ready** lead qualification system with Slack, HubSpot & AI

**📖 See the workflow schema:** [WORKFLOW.md](WORKFLOW.md) - Visual diagram of all nodes

## 🚀 How to Run

### Option 1: Local Testing (no webhook)
```bash
# Just the server (for testing)
start.bat
```
Then open: http://localhost:5678

---

### Option 2: With Cloudflare Tunnel (to receive Slack webhooks) ✅

**Step 1: Install Cloudflare Tunnel**
```bash
npm install -g cloudflare
```

**Step 2: Run with tunnel**
```bash
start-with-tunnel.bat
```

**Step 3: Copy the URL**
Cloudflare will show:
```
your-tunnel-url.trycloudflare.com
```

**Step 4: Add to Slack**
1. Go to https://api.slack.com/apps
2. Open your app → "Event Subscriptions"
3. Add webhook URL: `https://your-tunnel-url.trycloudflare.com/webhook`

---

## ⚙️ Environment Variables (Optional)

The script has built-in defaults, but you can override:

```bash
set SLACK_BOT_TOKEN=xoxb-your-token
set HUBSPOT_TOKEN=pat-your-token
set PORT=5678
```

---

## 📊 Dashboard

Open **http://localhost:5678** to see:
- Total leads processed
- Qualified / Not Qualified / SPAM counts
- Recent activity log
- Auto-refreshes every 30s

---

## 🔌 Production Features

- **HubSpot Integration**: Checks existing contacts, updates qualification status
- **Slack Webhook**: Real-time lead processing from Slack channels
- **Built-in Web Search**: Claude Code CLI searches Google to verify dentists
- **AI Qualification**: GLM-4 model with web access for accurate verification
- **Activity Logging**: Full audit trail with timestamps

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| "Python not found" | Install Python from https://python.org |
| "Flask not found" | Run: `pip install -r requirements.txt` |
| "Cloudflare command not found" | Run: `npm install -g cloudflare` |
| Port 5678 in use | Change PORT in `lead_qualifier.py` or stop n8n |

---

## 📁 Files

| File | Purpose |
|------|---------|
| [start.bat](start.bat) | Start server locally |
| [start-with-tunnel.bat](start-with-tunnel.bat) | Start + Cloudflare Tunnel |
| [lead_qualifier.py](lead_qualifier.py) | Main server |
| [.claude/config.json](.claude/config.json) | GLM API config |
| [requirements.txt](requirements.txt) | Python deps |

---

## 🔧 How It Works

```
Slack → Cloudflare Tunnel → Python Script → Qualification
                                    ↓
                              1. Extract lead data
                              2. Search Google (SerpAPI)
                              3. Call Claude Code (GLM-4)
                              4. Reply to Slack
```
