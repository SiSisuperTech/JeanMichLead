# Dental Lead Qualifier

AI-powered dental lead qualification using GLM-4.7 with web search.

## Deployment

Push to GitHub, then deploy on Koyeb using `koyeb.yaml`.

## Environment Variables (set in Koyeb)

| Variable | Description |
|----------|-------------|
| `ZAI_API_KEY` | z.ai GLM Coding Plan API key (enables web search) |
| `SLACK_BOT_TOKEN` | Slack bot token (xoxb-...) |
| `HUBSPOT_TOKEN` | HubSpot API token (pat-...) |

## How it works

1. Slack webhook receives lead notification
2. GLM-4.7 analyzes lead with web search
3. HubSpot CRM updated
4. Emoji reaction + DM if qualified

## n8n Workflow (recommended)

Import `n8n-workflows/lead_qualifier_glm47.json` into n8n and create 3 credentials:

- **Slack OAuth2** (for Slack Trigger + Slack actions)
- **HubSpot HTTP Header Auth** with `Authorization: Bearer <HUBSPOT_TOKEN>`
- **Z.ai HTTP Header Auth** with `Authorization: Bearer <ZAI_API_KEY>`

Optional env vars used by the workflow:

- `SLACK_ALLOWED_CHANNELS` (comma-separated channel IDs)
- `LEAD_QUALIFIER_DM_USER_ID` (defaults to `U08M425UAV8`)
