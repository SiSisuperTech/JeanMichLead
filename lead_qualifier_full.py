#!/usr/bin/env python3
"""
Dental Lead Qualifier - Complete Version
Replicates ALL functionality from qualify-final.json n8n workflow

Features:
- Slack webhook with URL verification
- Bot/subtype filtering
- HubSpot integration (check exists, update status)
- Claude Code web search for dentist verification
- Claude Code CLI with GLM
- Slack reply with emoji status
- Web dashboard at http://localhost:5678
"""

import os
import re
import json
import subprocess
import sys
import tempfile
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from requests import post, patch

# Fix Windows encoding for emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ==================== CONFIG ====================
# API tokens from environment variables (Railway, local, etc.)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN")
PORT = int(os.getenv("PORT", 5678))

# Warn if tokens missing (but don't exit - allows partial functionality)
if not SLACK_BOT_TOKEN:
    print("WARNING: SLACK_BOT_TOKEN not set - Slack features will be disabled")
if not HUBSPOT_TOKEN:
    print("WARNING: HUBSPOT_TOKEN not set - HubSpot features will be disabled")

app = Flask(__name__)

# ==================== LOGGING HELPER ====================
def log_msg(msg: str):
    """Print message with immediate flush"""
    print(msg, flush=True)

def log_separator():
    """Print a separator line"""
    log_msg("=" * 60)

# ==================== ACTIVITY LOG ====================
activity_log = []
stats = {
    "total_processed": 0,
    "qualified": 0,
    "not_qualified": 0,
    "spam": 0,
    "errors": 0,
    "hubspot_checked": 0,
    "hubspot_exists": 0,
    "hubspot_created": 0
}

# Track processed emails to avoid duplicates (email -> timestamp)
processed_emails = {}  # {email: timestamp}

def log_activity(level: str, message: str, lead_name: str = "", details: dict = None):
    """Add entry to activity log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        "lead_name": lead_name,
        "details": details or {}
    }
    activity_log.insert(0, entry)
    if len(activity_log) > 100:
        activity_log.pop()

    icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "•")
    details_str = f" | {details}" if details else ""
    print(f"[{timestamp}] {icon} {message}{details_str}")

# ==================== LEAD EXTRACTION ====================
def extract_lead_data(message: str) -> dict:
    """Extract lead info from Slack message"""

    # Email extraction
    email_match = re.search(r'([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)', message, re.IGNORECASE)
    email = email_match.group(1) if email_match else ""

    # Phone extraction - more flexible patterns
    phone = ""

    # First, try to extract from Slack's <tel:...|...> format
    slack_tel_match = re.search(r'<tel:([^|]+)\|([^>]+)>', message)
    if slack_tel_match:
        phone = slack_tel_match.group(2).strip()  # Use the display format
    else:
        # Regular phone patterns
        phone_patterns = [
            r'Mobile\s*:\s*([+\d\s-]+)',
            r'Phone\s*:\s*([+\d\s-]+)',
            r'Tel\s*:\s*([+\d\s-]+)',
            r'Téléphone\s*:\s*([+\d\s-]+)',
            r'GSM\s*:\s*([+\d\s-]+)',
            r'\b(?:0|\+33)[\d\s-]{8,}\b',  # French phone pattern
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # General pattern
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                phone = match.group(1).strip() if ':' in pattern else match.group(0).strip()
                break

    # Name extraction - handle "arrived:" and "arrived :" formats
    name_patterns = [
        r'A new lead(?: has arrived)\s*:\s*(.+?)\s+-',
        r'The following lead has booked[^:]*:\s*(.+?)\s+-'
    ]
    full_name = ""
    for pattern in name_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            full_name = match.group(1).strip()
            break

    name_parts = full_name.split() if full_name else []
    firstname, lastname = name_parts[0] if name_parts else "", " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    # Country & postal code
    country_match = re.search(r'-\s*([A-Za-z]+)\s*\(([^)]+)\)', message)
    country = country_match.group(1).strip() if country_match else ""
    postal_code = country_match.group(2).strip() if country_match else ""

    # Source
    source_match = re.search(r'Coming from\s+([^→-]+?)(?:\s+-|→)', message, re.IGNORECASE)
    source = source_match.group(1).strip() if source_match else ""

    # Sales owner
    owner_match = re.search(r'Sales owner\s*:\s*([^\n→]+)', message, re.IGNORECASE)
    sales_owner = owner_match.group(1).strip() if owner_match else ""

    # Email hint for dentist
    email_hint = bool(re.search(r'(dr\.|doc|docteur|cabinet|dentaire|dent)', email.lower()))

    return {
        "skip": False,
        "slackChannel": "",
        "rawMessage": message,
        "email": email,
        "phone": phone,
        "firstname": firstname,
        "lastname": lastname,
        "fullName": full_name,
        "country": country,
        "postalCode": postal_code,
        "source": source,
        "salesOwner": sales_owner,
        "emailHintDentist": email_hint
    }

# ==================== HUBSPOT INTEGRATION ====================
def check_hubspot_contact(email: str) -> dict:
    """Check if contact exists in HubSpot"""
    if not HUBSPOT_TOKEN:
        log_msg("[HUBSPOT] Skipping - no token configured")
        return {"exists": False, "contact_id": None, "skipped": True}
    try:
        response = post(
            "https://api.hubapi.com/crm/v3/objects/contacts/search",
            headers={
                "Authorization": f"Bearer {HUBSPOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email
                    }]
                }],
                "properties": ["hs_lead_status", "lifecyclestage"],
                "limit": 1
            },
            timeout=10
        )

        data = response.json()
        results = data.get("results", [])
        exists = len(results) > 0
        contact_id = results[0]["id"] if exists else None

        stats["hubspot_checked"] += 1
        if exists:
            stats["hubspot_exists"] += 1

        return {"exists": exists, "contact_id": contact_id, "raw": data}

    except Exception as e:
        log_activity("error", f"HubSpot check failed: {str(e)}", "", {})
        return {"exists": False, "contact_id": None, "error": str(e)}

def update_hubspot_contact(contact_id: str, qualified: bool):
    """Update HubSpot contact status"""
    if not HUBSPOT_TOKEN:
        log_msg("[HUBSPOT] Skipping update - no token configured")
        return False
    try:
        log_msg(f"[HUBSPOT] Updating contact {contact_id} -> {'Qualified' if qualified else 'UNQUALIFIED'}")
        if qualified:
            # Update as qualified
            response = patch(
                f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}",
                headers={
                    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "properties": {
                        "lifecyclestage": "lead",
                        "hs_lead_status": "OPEN",
                        "lead_status": "Qualified"
                    }
                },
                timeout=10
            )
        else:
            # Update as not qualified
            response = patch(
                f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}",
                headers={
                    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "properties": {
                        "hs_lead_status": "UNQUALIFIED",
                        "lead_status": "KO"
                    }
                },
                timeout=10
            )

        if response.status_code in [200, 201]:
            log_msg(f"[HUBSPOT] Update successful")
        else:
            log_msg(f"[HUBSPOT] Update failed: {response.status_code} - {response.text[:100]}")

        log_activity("success", f"HubSpot updated: {'Qualified' if qualified else 'KO'}", "", {"contact_id": contact_id})
        return True

    except Exception as e:
        log_activity("error", f"HubSpot update failed: {str(e)}", "", {"contact_id": contact_id})
        return False

# ==================== BUILD QUALIFICATION PROMPT ====================
def build_qualification_prompt(lead: dict) -> str:
    """Build AI prompt for GLM-4.7 with web search - ASCII only for compatibility"""

    email_domain = lead.get('email', '').split('@')[-1] if '@' in lead.get('email', '') else 'Unknown'

    # Build search queries - more variations for better results
    search_queries = []
    full_name = lead.get('fullName', '')
    if full_name:
        # Try different name variations
        name_variants = [
            full_name,
            full_name.replace('Dr ', '').replace('Dr. ', '').replace('Pr ', '').replace('Pr. ', '').strip(),
        ]
        # Also split name for searches
        parts = full_name.split()
        if len(parts) >= 2:
            name_variants.append(f'{" ".join(parts[1:])}')  # Last name only

        for name_variant in name_variants[:2]:  # Limit to avoid too many searches
            search_queries.extend([
                f'site:fr "{name_variant}" dentiste',
                f'site:fr "{name_variant}" chirurgien dentiste',
                f'site:doctolib.fr "{name_variant}"',
                f'"{name_variant}" dentiste France'
            ])

    queries_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(search_queries[:6])])

    return f"""You are a dental lead qualification analyst for France. You MUST perform THOROUGH web searches.

LEAD TO VERIFY:
Name: {lead.get('fullName', 'Unknown')}
Email: {lead.get('email', 'Unknown')}
Phone: {lead.get('phone', 'Unknown')}
Country: {lead.get('country', 'Unknown')}

CRITICAL INSTRUCTIONS:
1. You MUST search MULTIPLE sources before concluding SPAM
2. Web search can be flaky - try different search variations
3. If first search finds nothing, try: name only, name + "chirurgien dentiste", name + "doctolib"
4. Check: Doctolib.fr, annuaire.sante.fr, Google (general search), LinkedIn
5. A Gmail address does NOT automatically mean SPAM - many French dentists use Gmail

SEARCH QUERIES TO TRY (in order):
{queries_text}

SCORING (0-100):
+50: Found on Doctolib.fr or annuaire.sante.fr as dentist
+30: Email has dental domain (cabinet*.fr, *dentaire.fr, clinique*.fr)
+20: Professional email (not gmail/yahoo/hotmail)
+10: Complete info (name+email+phone)
-20: Gmail address (ONLY if no web verification found)

QUALIFICATION:
Score >= 70: QUALIFIED
Score 50-69: POSSIBLE
Score < 50: NOT QUALIFIED

ONLY classify as SPAM if:
- No web presence found AFTER THOROUGH SEARCHING
- Name appears nowhere as dentist
- No dental indicators at all

Return ONLY JSON:
{{"is_dentist": true/false, "profile_type": "Dentiste/Orthodontiste/Etudiant/Autre/SPAM", "score": 75, "qualified": true/false, "reasoning": "What you found and where"}}"""

# ==================== CALL AI API (Direct HTTP) ====================
def call_ai_api(prompt: str) -> dict:
    """Call Anthropic-compatible API directly (works on Koyeb)"""
    try:
        import anthropic

        # Get API config from environment (Koyeb sets these)
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN", "")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

        if not api_key:
            return {"error": "ANTHROPIC_API_KEY not set in environment"}

        log_msg(f"[AI] Using API: {base_url}")
        log_msg(f"[AI] Prompt length: {len(prompt)} chars")

        # Initialize client with custom base URL
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url
        )

        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        log_msg(f"[AI] Calling model: {model}...")

        response = client.messages.create(
            model=model,
            max_tokens=2000,
            temperature=0,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Extract the response text
        response_text = response.content[0].text
        log_msg(f"[AI] Response received: {len(response_text)} chars")

        # Clean up markdown code blocks
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        # Parse JSON
        try:
            result = json.loads(response_text)
            log_msg(f"[AI] Parsed successfully: {result.get('profile_type', '?')} | Score: {result.get('score', 0)}")
            return result
        except json.JSONDecodeError:
            # Try to find JSON in response
            brace_count = 0
            json_start = -1
            for i, char in enumerate(response_text):
                if char == '{':
                    if brace_count == 0:
                        json_start = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and json_start >= 0:
                        try:
                            json_str = response_text[json_start:i+1]
                            result = json.loads(json_str)
                            log_msg(f"[AI] Parsed with extraction: {result.get('profile_type', '?')}")
                            return result
                        except json.JSONDecodeError:
                            json_start = -1
                            continue

            return {
                "error": "No valid JSON in response",
                "raw_preview": response_text[:500] if len(response_text) > 500 else response_text
            }

    except ImportError:
        return {"error": "anthropic package not installed - run: pip install anthropic"}
    except Exception as e:
        return {"error": f"API call failed: {str(e)}"}

# Fallback to Claude CLI for local development
def call_claude_code(prompt: str) -> dict:
    """Try API first, fallback to CLI for local development"""
    # If running in production (Koyeb), use API
    if os.getenv("KOYEB") or os.getenv("ANTHROPIC_API_KEY"):
        log_msg("[AI] Using direct API (production mode)")
        return call_ai_api(prompt)

    # Otherwise try CLI for local development
    try:
        env = os.environ.copy()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, ".claude")
        config_path = os.path.join(config_dir, "config.json")

        env["CLAUDE_CONFIG_DIR"] = config_dir
        env["PYTHONIOENCODING"] = "utf-8"

        api_key = ""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get("env", {}).get("ANTHROPIC_AUTH_TOKEN", "")
                base_url = config.get("env", {}).get("ANTHROPIC_BASE_URL", "")
                if api_key:
                    env["ANTHROPIC_AUTH_TOKEN"] = api_key
                if base_url:
                    env["ANTHROPIC_BASE_URL"] = base_url
        except Exception:
            pass

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        log_msg(f"[AI] Using Claude CLI (local mode)...")

        result = subprocess.run(
            'claude --dangerously-skip-permissions',
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=90,
            shell=True,
            env=env,
            startupinfo=startupinfo
        )

        response = result.stdout or ""
        if result.stderr:
            response += "\n" + result.stderr

        response = response.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        brace_count = 0
        json_start = -1
        for i, char in enumerate(response):
            if char == '{':
                if brace_count == 0:
                    json_start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and json_start >= 0:
                    try:
                        json_str = response[json_start:i+1]
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        json_start = -1
                        continue

        return {"error": "No valid JSON found", "raw_preview": response[:500]}
    except Exception as e:
        # If CLI fails, try API as fallback
        log_msg(f"[AI] CLI failed: {e}, trying API...")
        return call_ai_api(prompt)

# ==================== FORMAT SLACK MESSAGE ====================
def format_slack_message(lead: dict, qualification: dict) -> str:
    """Format the Slack reply message"""
    emoji = "✅" if qualification.get("qualified") else "❌"
    status = "QUALIFIE" if qualification.get("qualified") else "NON QUALIFIE"

    return f"""{emoji} LEAD {status}

👤 {lead.get('fullName', 'Unknown')}
📧 {lead.get('email', 'Unknown')}
📞 {lead.get('phone', 'Unknown')}
🏥 {qualification.get('profile_type', 'Unknown')}
📊 Score: {qualification.get('score', 0)}/100

💡 {qualification.get('reasoning', '')}"""

# ==================== SEND SLACK REPLY ====================
def send_slack_reply(channel: str, message: str) -> bool:
    """Send reply to Slack"""
    if not SLACK_BOT_TOKEN:
        log_msg("[SLACK] Skipping - no token configured")
        return False
    try:
        post("https://slack.com/api/chat.postMessage", headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }, json={
            "channel": channel,
            "text": message
        })
        return True
    except Exception as e:
        log_activity("error", f"Slack API error: {str(e)}", "")
        return False

def add_reaction_to_message(channel: str, timestamp: str, emoji: str) -> bool:
    """Add emoji reaction to a message"""
    if not SLACK_BOT_TOKEN:
        log_msg("[SLACK] Skipping reaction - no token configured")
        return False
    try:
        response = post("https://slack.com/api/reactions.add", headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }, json={
            "channel": channel,
            "timestamp": timestamp,
            "name": emoji
        })
        result = response.json()
        if result.get("ok"):
            log_msg(f"[SLACK] Reaction added: {emoji}")
        else:
            log_msg(f"[SLACK] Reaction failed: {result.get('error', 'unknown')}")
        return result.get("ok", False)
    except Exception as e:
        log_msg(f"[SLACK] Reaction error: {e}")
        return False

def send_dm_to_user(user_id: str, message: str) -> bool:
    """Send a DM to a specific user"""
    if not SLACK_BOT_TOKEN:
        log_msg("[SLACK] Skipping DM - no token configured")
        return False
    try:
        # Open a DM channel with the user
        response = post("https://slack.com/api/conversations.open", headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }, json={
            "users": user_id
        })

        result = response.json()
        if not result.get("ok", False):
            log_msg(f"[SLACK] DM open failed: {result.get('error', 'unknown')}")
            return False

        dm_channel = result.get("channel", {}).get("id")

        # Send the message
        response = post("https://slack.com/api/chat.postMessage", headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }, json={
            "channel": dm_channel,
            "text": message
        })
        result = response.json()
        if result.get("ok"):
            log_msg(f"[SLACK] DM sent successfully to {user_id}")
        else:
            log_msg(f"[SLACK] DM send failed: {result.get('error', 'unknown')}")
        return result.get("ok", False)
    except Exception as e:
        log_msg(f"[SLACK] DM error: {e}")
        return False

# ==================== DASHBOARD HTML (n8n Style) ====================
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Lead Qualifier Workflow</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e;
            min-height: 100vh;
            color: #e4e4e7;
        }
        .header {
            background: #16162a;
            padding: 15px 30px;
            border-bottom: 1px solid #27273a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 1.2em; font-weight: 600; }
        .status-badge {
            background: #059669;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            background: #4ade80;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .workflow-container {
            display: flex;
            height: calc(100vh - 60px);
        }
        .sidebar {
            width: 320px;
            background: #16162a;
            border-right: 1px solid #27273a;
            display: flex;
            flex-direction: column;
        }
        .sidebar-header {
            padding: 15px 20px;
            border-bottom: 1px solid #27273a;
            font-weight: 600;
            font-size: 0.9em;
            color: #a1a1aa;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            padding: 15px 20px;
            border-bottom: 1px solid #27273a;
        }
        .stat-box {
            background: #1e1e32;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }
        .stat-value { font-size: 1.5em; font-weight: 700; }
        .stat-label { font-size: 0.75em; color: #a1a1aa; margin-top: 4px; }
        .stat-box.success .stat-value { color: #4ade80; }
        .stat-box.danger .stat-value { color: #f87171; }
        .stat-box.warning .stat-value { color: #fbbf24; }
        .stat-box.info .stat-value { color: #60a5fa; }

        .activity-feed {
            flex: 1;
            overflow-y: auto;
            padding: 15px 20px;
        }
        .activity-item {
            background: #1e1e32;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            border-left: 3px solid #52525b;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }
        .activity-item.success { border-left-color: #4ade80; }
        .activity-item.error { border-left-color: #f87171; }
        .activity-item.info { border-left-color: #60a5fa; }
        .activity-item.warning { border-left-color: #fbbf24; }
        .activity-time { font-size: 0.7em; color: #71717a; margin-bottom: 4px; }
        .activity-content { font-size: 0.85em; }
        .activity-meta { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
        .tag {
            font-size: 0.7em;
            padding: 2px 8px;
            border-radius: 4px;
            background: #27273a;
        }

        .canvas {
            flex: 1;
            background: #13131f;
            background-image: radial-gradient(circle, #27273a 1px, transparent 1px);
            background-size: 20px 20px;
            padding: 40px;
            overflow: auto;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
        }
        .workflow {
            display: flex;
            align-items: center;
            gap: 40px;
            flex-wrap: wrap;
            justify-content: center;
        }
        .node {
            width: 180px;
            background: #1e1e32;
            border-radius: 12px;
            padding: 16px;
            position: relative;
            border: 2px solid transparent;
            transition: all 0.3s ease;
        }
        .node:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
        .node.active { border-color: #ea580c; }
        .node-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2em;
            margin-bottom: 10px;
        }
        .node.slack .node-icon { background: #4a154b; }
        .node.hubspot .node-icon { background: #ff7a59; }
        .node.ai .node-icon { background: #8b5cf6; }
        .node.output .node-icon { background: #059669; }
        .node-title { font-size: 0.85em; font-weight: 600; margin-bottom: 4px; }
        .node-desc { font-size: 0.7em; color: #71717a; }
        .node-status {
            position: absolute;
            top: -8px;
            right: -8px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #27273a;
            border: 2px solid #1e1e32;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7em;
        }
        .node-status.processing { background: #fbbf24; animation: spin 1s linear infinite; }
        .node-status.success { background: #4ade80; }
        .node-status.error { background: #f87171; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        .connector {
            width: 40px;
            height: 2px;
            background: #52525b;
            position: relative;
        }
        .connector::after {
            content: '';
            position: absolute;
            right: 0;
            top: -3px;
            width: 0;
            height: 0;
            border-left: 6px solid #52525b;
            border-top: 4px solid transparent;
            border-bottom: 4px solid transparent;
        }

        .lead-info {
            background: #27273a;
            border-radius: 12px;
            padding: 20px;
            margin: 20px;
        }
        .lead-info h3 { margin-bottom: 15px; font-size: 0.9em; color: #a1a1aa; }
        .lead-detail {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #3f3f46;
        }
        .lead-detail:last-child { border-bottom: none; }
        .lead-label { color: #71717a; font-size: 0.85em; }
        .lead-value { font-weight: 500; }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #16162a; }
        ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Dental Lead Qualifier</h1>
        <div class="status-badge">
            <div class="status-dot"></div>
            Live
        </div>
    </div>

    <div class="workflow-container">
        <div class="sidebar">
            <div class="sidebar-header">STATISTICS</div>
            <div class="stats-grid">
                <div class="stat-box info">
                    <div class="stat-value" id="stat-total">0</div>
                    <div class="stat-label">Total</div>
                </div>
                <div class="stat-box success">
                    <div class="stat-value" id="stat-qualified">0</div>
                    <div class="stat-label">Qualified</div>
                </div>
                <div class="stat-box danger">
                    <div class="stat-value" id="stat-rejected">0</div>
                    <div class="stat-label">Rejected</div>
                </div>
                <div class="stat-box warning">
                    <div class="stat-value" id="stat-spam">0</div>
                    <div class="stat-label">Spam</div>
                </div>
            </div>

            <div class="sidebar-header">RECENT ACTIVITY</div>
            <div class="activity-feed" id="activity-feed">
                <div class="activity-item info">
                    <div class="activity-time">Waiting for leads...</div>
                    <div class="activity-content">Send a lead to Slack to start processing</div>
                </div>
            </div>
        </div>

        <div class="canvas">
            <div class="workflow">
                <div class="node slack" id="node-slack">
                    <div class="node-icon"><i class="fab fa-slack"></i></div>
                    <div class="node-title">Slack Webhook</div>
                    <div class="node-desc">Receive events</div>
                    <div class="node-status"></div>
                </div>
                <div class="connector"></div>
                <div class="node" id="node-extract">
                    <div class="node-icon"><i class="fas fa-file-export"></i></div>
                    <div class="node-title">Extract Data</div>
                    <div class="node-desc">Parse info</div>
                    <div class="node-status"></div>
                </div>
                <div class="connector"></div>
                <div class="node hubspot" id="node-hubspot">
                    <div class="node-icon"><i class="fas fa-database"></i></div>
                    <div class="node-title">HubSpot CRM</div>
                    <div class="node-desc">Check existing</div>
                    <div class="node-status"></div>
                </div>
                <div class="connector"></div>
                <div class="node ai" id="node-ai">
                    <div class="node-icon"><i class="fas fa-brain"></i></div>
                    <div class="node-title">AI Analysis</div>
                    <div class="node-desc">GLM-4.7 + Search</div>
                    <div class="node-status"></div>
                </div>
                <div class="connector"></div>
                <div class="node output slack" id="node-output">
                    <div class="node-icon"><i class="fas fa-reply"></i></div>
                    <div class="node-title">Slack Reply</div>
                    <div class="node-desc">Send result</div>
                    <div class="node-status"></div>
                </div>
            </div>

            <div class="lead-info" id="lead-info" style="display: none;">
                <h3>CURRENT LEAD</h3>
                <div class="lead-detail">
                    <span class="lead-label">Name</span>
                    <span class="lead-value" id="lead-name">-</span>
                </div>
                <div class="lead-detail">
                    <span class="lead-label">Email</span>
                    <span class="lead-value" id="lead-email">-</span>
                </div>
                <div class="lead-detail">
                    <span class="lead-label">Score</span>
                    <span class="lead-value" id="lead-score">-</span>
                </div>
                <div class="lead-detail">
                    <span class="lead-label">Status</span>
                    <span class="lead-value" id="lead-status">-</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        let lastLogCount = 0;

        function setNodeStatus(nodeId, status) {
            const node = document.getElementById(nodeId);
            if (!node) return;
            const statusEl = node.querySelector('.node-status');
            statusEl.className = 'node-status ' + status;
            if (status === 'processing') {
                statusEl.innerHTML = '<i class="fas fa-spinner"></i>';
            } else if (status === 'success') {
                statusEl.innerHTML = '<i class="fas fa-check"></i>';
            } else if (status === 'error') {
                statusEl.innerHTML = '<i class="fas fa-times"></i>';
            } else {
                statusEl.innerHTML = '';
            }
            if (status !== '') node.classList.add('active');
        }

        async function fetchUpdates() {
            try {
                const response = await fetch('/api/logs');
                const logs = await response.json();

                if (logs.length !== lastLogCount) {
                    lastLogCount = logs.length;
                    updateActivityFeed(logs);
                    processLatestLead(logs[0]);
                }

                const statsRes = await fetch('/api/stats');
                const stats = await statsRes.json();
                document.getElementById('stat-total').textContent = stats.total_processed;
                document.getElementById('stat-qualified').textContent = stats.qualified;
                document.getElementById('stat-rejected').textContent = stats.not_qualified;
                document.getElementById('stat-spam').textContent = stats.spam;
            } catch (e) {}
        }

        function updateActivityFeed(logs) {
            const feed = document.getElementById('activity-feed');
            feed.innerHTML = '';
            logs.slice(0, 20).forEach(log => {
                const item = document.createElement('div');
                item.className = 'activity-item ' + log.level;
                let metaHtml = '';
                if (log.details.profile_type) {
                    metaHtml += `<span class="tag">${log.details.profile_type}</span>`;
                    metaHtml += `<span class="tag">${log.details.score}/100</span>`;
                }
                if (log.details.contact_id) {
                    metaHtml += `<span class="tag">HubSpot</span>`;
                }
                item.innerHTML = `
                    <div class="activity-time">${log.timestamp}</div>
                    <div class="activity-content">${log.lead_name || log.message}</div>
                    ${metaHtml ? `<div class="activity-meta">${metaHtml}</div>` : ''}
                `;
                feed.appendChild(item);
            });
        }

        function processLatestLead(log) {
            if (!log || !log.lead_name) {
                document.getElementById('lead-info').style.display = 'none';
                return;
            }
            document.getElementById('lead-info').style.display = 'block';
            document.getElementById('lead-name').textContent = log.lead_name;
            const details = log.details || {};
            document.getElementById('lead-email').textContent = details.email || details.profile_type || '-';
            document.getElementById('lead-score').textContent = details.score ? details.score + '/100' : '-';
            document.getElementById('lead-status').textContent = details.profile_type || 'Processing...';
            if (log.level === 'success') {
                setNodeStatus('node-slack', 'success');
                setNodeStatus('node-extract', 'success');
                setNodeStatus('node-hubspot', 'success');
                setNodeStatus('node-ai', 'success');
                setNodeStatus('node-output', 'success');
            }
        }

        setInterval(fetchUpdates, 1000);
        fetchUpdates();
    </script>
</body>
</html>
'''

# ==================== ROUTES ====================

@app.route('/', methods=['GET'])
def dashboard():
    """Web dashboard"""
    return render_template_string(DASHBOARD_HTML, stats=stats, log=activity_log, port=PORT)

@app.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    """Simple test endpoint to verify webhook is working"""
    print("\n[TEST] Webhook received!")
    print(f"[TEST] Method: {request.method}")
    print(f"[TEST] Headers: {dict(request.headers)}")
    try:
        if request.is_json:
            data = request.get_json(silent=True)
            print(f"[TEST] Body: {json.dumps(data, indent=2)}")
    except:
        pass
    return jsonify({"status": "ok", "message": "Webhook is working!", "method": request.method})

@app.route('/webhook', methods=['POST'])
def slack_webhook():
    """Main Slack webhook"""

    data = request.json

    log_msg("")
    log_separator()
    log_msg("[WEBHOOK] Request received!")
    log_msg(f"[WEBHOOK] Data type: {data.get('type') if data else 'None'}")

    # Handle URL verification
    if data and data.get("type") == "url_verification":
        log_msg("[WEBHOOK] URL verification - returning challenge")
        return jsonify({"challenge": data.get("challenge")})

    # Handle event callbacks
    if data.get("type") == "event_callback":
        log_msg("[WEBHOOK] Event callback received")
        event = data.get("event", {})
        log_msg(f"[WEBHOOK] Event type: {event.get('type')}")

        # Skip bots and subtypes (including message_changed, message_deleted, etc.)
        if event.get("bot_id") or event.get("subtype"):
            log_msg("[WEBHOOK] Skipping bot/subtype message")
            return jsonify({"status": "ok"})

        # Only process messages
        if event.get("type") != "message":
            log_msg(f"[WEBHOOK] Skipping non-message event: {event.get('type')}")
            return jsonify({"status": "ok"})

        message = event.get("text", "")
        channel = event.get("channel", "")
        ts = event.get("ts", "")

        if not message or not channel:
            log_msg("[WEBHOOK] No message or channel - skipping")
            return jsonify({"status": "ok"})

        # Extract lead data FIRST to check for duplicate by email
        lead = extract_lead_data(message)
        email = lead.get('email', '')

        # Log the incoming message FIRST (before duplicate check)
        log_msg(f"[WEBHOOK] Processing message from channel: {channel}")
        log_msg(f"[WEBHOOK] Message: {message[:150]}...")
        log_msg("[EXTRACT] Parsing lead data...")
        log_msg(f"[EXTRACT] Name: {lead.get('fullName', 'N/A')}")
        log_msg(f"[EXTRACT] Email: {email}")
        log_msg(f"[EXTRACT] Phone: {lead.get('phone', 'N/A')}")

        # Skip if we've processed this email in the last 5 minutes
        if email and email in processed_emails:
            last_processed = processed_emails[email]
            elapsed = (datetime.now() - last_processed).total_seconds()
            if elapsed < 300:  # 5 minutes
                log_msg(f"[SKIP] Duplicate detected - processed {email} {int(elapsed)}s ago")
                return jsonify({"status": "skipped"})

        # Mark email as in-progress to prevent race condition
        if email:
            processed_emails[email] = datetime.now()

        if lead.get("skip"):
            log_msg(f"[SKIP] {lead.get('reason')}")
            log_activity("info", f"Skipped: {lead.get('reason')}", "", {"raw_message": message[:50]})
            return jsonify({"status": "skipped"})

        # Check HubSpot
        log_msg(f"[HUBSPOT] Checking: {lead['email']}")
        hubspot_result = check_hubspot_contact(lead['email'])
        lead["hubspotContactId"] = hubspot_result.get("contact_id")
        lead["hubspotContactExists"] = hubspot_result.get("exists")

        if hubspot_result.get("exists"):
            log_msg(f"[HUBSPOT] Found: {hubspot_result.get('contact_id')}")
        else:
            log_msg("[HUBSPOT] New lead")

        # AI qualification
        log_msg("[AI] Starting analysis (this takes 30-60s)...")
        prompt = build_qualification_prompt(lead)
        qualification = call_claude_code(prompt)

        log_msg("[AI] Result:")
        log_msg(f"  - Profile: {qualification.get('profile_type', '?')}")
        log_msg(f"  - Score: {qualification.get('score', 0)}/100")
        log_msg(f"  - Qualified: {qualification.get('qualified', False)}")

        if "error" in qualification:
            log_msg(f"[AI] ERROR: {qualification.get('error')}")
            stats["errors"] += 1
            return jsonify({"status": "error", "message": qualification.get("error")})

        # Update stats
        stats["total_processed"] += 1
        if qualification.get("qualified"):
            stats["qualified"] += 1
        else:
            stats["not_qualified"] += 1
        if qualification.get("profile_type") == "SPAM":
            stats["spam"] += 1

        # Update HubSpot if needed
        if lead.get("hubspotContactId"):
            update_hubspot_contact(lead["hubspotContactId"], qualification.get("qualified"))

        # Add reaction to original message (no text reply)
        if not qualification.get("qualified"):
            log_msg("[SLACK] Adding X reaction")
            add_reaction_to_message(channel, ts, "x")
        else:
            log_msg("[SLACK] Adding checkmark reaction")
            add_reaction_to_message(channel, ts, "white_check_mark")

            # Send DM to user when qualified
            dm_message = (
                f"*New Qualified Lead!* 🦷\n"
                f"*Name:* {lead.get('fullName', 'N/A')}\n"
                f"*Email:* {lead.get('email', 'N/A')}\n"
                f"*Phone:* {lead.get('phone', 'N/A')}\n"
                f"*Profile:* {qualification.get('profile_type', 'N/A')}\n"
                f"*Score:* {qualification.get('score', 0)}/100\n"
                f"*Reasoning:* {qualification.get('reasoning', '')[:200]}..."
            )
            log_msg("[SLACK] Sending DM to user...")
            send_dm_to_user("U089Z240VD5", dm_message)  # simon.gautier

        log_activity("success", f"Qualified: {qualification.get('profile_type')} | {qualification.get('score')}/100",
                      lead['fullName'], qualification)

        # Clean up old entries (older than 5 minutes)
        cutoff = datetime.now()
        for old_email in list(processed_emails.keys()):
            if (cutoff - processed_emails[old_email]).total_seconds() > 300:
                del processed_emails[old_email]

        # Summary of what was done
        log_msg("[DONE] Summary:")
        log_msg(f"  - Lead: {lead.get('fullName', 'N/A')}")
        log_msg(f"  - Status: {'QUALIFIED' if qualification.get('qualified') else 'NOT QUALIFIED'}")
        log_msg(f"  - Reaction: {'✓' if qualification.get('qualified') else '✗'}")
        log_msg(f"  - HubSpot: Updated")
        log_msg(f"  - DM Sent: {'Yes' if qualification.get('qualified') else 'No'}")

        log_separator()
        log_msg("")

        return jsonify({"status": "ok"})

    return jsonify({"status": "ok"})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get current statistics"""
    return jsonify(stats)

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get activity log"""
    return jsonify(activity_log[:50])

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "dental-lead-qualifier"})


# ==================== MAIN ====================
if __name__ == '__main__':
    log_activity("success", "Dental Lead Qualifier started", "", {
        "dashboard": f"http://localhost:{PORT}/",
        "webhook": f"http://localhost:{PORT}/webhook"
    })

    # Print startup banner
    log_msg("")
    log_separator()
    log_msg("     DENTAL LEAD QUALIFIER - RUNNING")
    log_separator()
    log_msg(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_msg("")
    log_msg(f"  Dashboard:  http://localhost:{PORT}/")
    log_msg(f"  Webhook:    http://localhost:{PORT}/webhook")
    log_msg(f"  Health:     http://localhost:{PORT}/health")
    log_msg("")
    log_separator()
    log_msg("  Waiting for Slack webhooks...")
    log_separator()
    log_msg("")

    # Disable Flask access logs - only show our custom logs
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
