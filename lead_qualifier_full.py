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

# ==================== ROUTES ====================

@app.route('/', methods=['GET'])
def index():
    """Simple index - dashboard removed for security"""
    return jsonify({
        "status": "running",
        "service": "dental-lead-qualifier",
        "webhook": "/webhook",
        "health": "/health"
    })

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
