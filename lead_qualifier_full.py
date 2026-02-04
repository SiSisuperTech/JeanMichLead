#!/usr/bin/env python3
"""
Dental Lead Qualifier - Koyeb Deployment
Uses GLM-4.7 via z.ai API with web search
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from requests import post, patch, get

# ==================== CONFIG ====================
# API tokens from environment variables (Railway, local, etc.)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN")
PORT = int(os.getenv("PORT", 8000))

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

# ==================== HUBSPOT ENGAGEMENT HISTORY ====================
def get_engagement_history(contact_id: str) -> dict:
    """Get all engagement history for a contact (notes, calls, tasks, meetings)"""
    if not HUBSPOT_TOKEN:
        return {"has_history": False, "reason": "No HubSpot token"}

    history = {
        "notes": [],
        "calls": [],
        "tasks": [],
        "meetings": [],
        "summary": []
    }

    try:
        # 1. Get Notes
        response = get(
            "https://api.hubapi.com/crm/v3/objects/notes",
            headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
            params={
                "limit": 10,
                "properties": ["hs_note_body", "hs_createdate", "hs_object_id"],
                "archived": "false"
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            for note in data.get("results", []):
                props = note.get("properties", {})
                body = props.get("hs_note_body", "")
                # Clean HTML from note body
                import re
                body = re.sub(r'<[^>]+>', '', body).strip()
                if body:
                    history["notes"].append({
                        "date": props.get("hs_createdate", "")[:10],
                        "body": body[:200]
                    })

        # 2. Get Calls
        response = get(
            "https://api.hubapi.com/crm/v3/objects/calls",
            headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
            params={
                "limit": 10,
                "properties": ["hs_call_title", "hs_call_body", "hs_call_direction", "hs_call_status", "hs_createdate"]
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            for call in data.get("results", []):
                props = call.get("properties", {})
                title = props.get("hs_call_title", "")
                body = props.get("hs_call_body", "")
                direction = props.get("hs_call_direction", "")
                if title or body:
                    history["calls"].append({
                        "date": props.get("hs_createdate", "")[:10],
                        "direction": direction,
                        "title": title,
                        "body": body[:150]
                    })

        # 3. Get Tasks
        response = get(
            "https://api.hubapi.com/crm/v3/objects/tasks",
            headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
            params={
                "limit": 10,
                "properties": ["hs_task_subject", "hs_task_status", "hs_task_priority", "hs_timestamp"]
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            for task in data.get("results", []):
                props = task.get("properties", {})
                subject = props.get("hs_task_subject", "")
                status = props.get("hs_task_status", "")
                if subject:
                    history["tasks"].append({
                        "date": props.get("hs_timestamp", "")[:10],
                        "status": status,
                        "subject": subject
                    })

        # 4. Get Meetings
        response = get(
            "https://api.hubapi.com/crm/v3/objects/meetings",
            headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
            params={
                "limit": 10,
                "properties": ["hs_meeting_title", "hs_meeting_body", "hs_meeting_starttime", "hs_meeting_status"]
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            for meeting in data.get("results", []):
                props = meeting.get("properties", {})
                title = props.get("hs_meeting_title", "")
                if title:
                    history["meetings"].append({
                        "date": props.get("hs_meeting_starttime", "")[:10],
                        "status": props.get("hs_meeting_status", ""),
                        "title": title
                    })

        # Build summary for AI
        if history["notes"]:
            history["summary"].append(f"Notes: {len(history['notes'])} found")
            for note in history["notes"][:3]:
                history["summary"].append(f"  - [{note['date']}] {note['body'][:80]}")

        if history["calls"]:
            history["summary"].append(f"Calls: {len(history['calls'])} found")
            for call in history["calls"][:3]:
                history["summary"].append(f"  - [{call['date']}] {call['direction']}: {call['title'][:50]}")

        if history["tasks"]:
            history["summary"].append(f"Tasks: {len(history['tasks'])} pending")
            for task in history["tasks"][:3]:
                history["summary"].append(f"  - [{task['status']}] {task['subject'][:50]}")

        if history["meetings"]:
            history["summary"].append(f"Meetings: {len(history['meetings'])} scheduled/completed")
            for meeting in history["meetings"][:3]:
                history["summary"].append(f"  - [{meeting['date']}] {meeting['title'][:50]}")

        history["has_history"] = bool(history["notes"] or history["calls"] or history["tasks"] or history["meetings"])

        log_msg(f"[HUBSPOT] Engagement: {len(history['notes'])} notes, {len(history['calls'])} calls, {len(history['tasks'])} tasks, {len(history['meetings'])} meetings")

        return history

    except Exception as e:
        log_msg(f"[HUBSPOT] Engagement fetch error: {str(e)}")
        return {"has_history": False, "error": str(e)}

# ==================== BUILD QUALIFICATION PROMPT ====================
def build_qualification_prompt(lead: dict, engagement: dict = None) -> str:
    """Build AI prompt for GLM-4.7 with web_search tool and engagement context"""
    postal = lead.get('postalCode', '')
    name = lead.get('fullName', '')

    prompt = f'Is "{name} dentiste {postal}" a real dentist? Search and give me the address, phone, and sources.'

    # Add engagement history context if available
    if engagement and engagement.get("has_history"):
        prompt += '\n\nIMPORTANT - Previous engagement history for this lead:\n'
        for line in engagement.get("summary", []):
            prompt += f"  {line}\n"
        prompt += "\nConsider this history when qualifying. If notes say 'wrong number', 'not interested', or 'fake', mark as NOT QUALIFIED."

    prompt += '\n\nEnd with: QUALIFIED: yes/no and SCORE: X/100'
    return prompt

# ==================== CALL Z.AI API WITH WEB SEARCH ====================
def call_ai(prompt: str) -> dict:
    """Call Z.ai GLM-4.7 with web_search tool"""
    try:
        api_key = os.getenv("ZAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {"error": "ZAI_API_KEY not set in environment"}

        url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "glm-4.7",
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{
                "type": "web_search",
                "web_search": {
                    "enable": True,
                    "search_result": True,
                    "count": 5
                }
            }],
            "max_tokens": 8000,
            "temperature": 0
        }

        log_msg(f"[AI] API: {url}")
        log_msg(f"[AI] Key: {api_key[:20]}..." if api_key else "[AI] No key!")
        log_msg("[AI] Calling GLM-4.7 with web_search...")

        response = post(url, headers=headers, json=payload, timeout=120)

        if response.status_code != 200:
            log_msg(f"[AI] HTTP {response.status_code}: {response.text[:300]}")
            return {"error": f"API returned {response.status_code}: {response.text[:200]}"}

        data = response.json()
        log_msg(f"[AI] Raw response keys: {list(data.keys())}")

        if "choices" not in data or not data["choices"]:
            log_msg(f"[AI] No choices in response: {str(data)[:300]}")
            return {"error": "No choices in response", "raw": data}

        content = data["choices"][0]["message"].get("content", "")
        text = content.strip()
        log_msg(f"[AI] Response: {len(text)} chars")

        if not text:
            log_msg(f"[AI] EMPTY RESPONSE! Full message: {data['choices'][0]['message']}")
            return {"error": "Empty response from AI", "raw_message": data["choices"][0]["message"]}

        # Parse natural language response
        result = {
            "is_dentist": False,
            "profile_type": "SPAM",
            "score": 0,
            "qualified": False,
            "reasoning": text[:300]
        }

        text_upper = text.upper()

        # Check if it's spam first (explicit mentions)
        if " NOT A REAL DENTIST" in text_upper or " NOT DENTIST" in text_upper or "FAKE" in text_upper[:400]:
            result["profile_type"] = "SPAM"
            result["qualified"] = False
            result["score"] = 0
        # Check if dentist (look for positive indicators with context)
        elif (" REAL DENTIST" in text_upper or " IS A DENTIST" in text_upper or "CHIRURGIEN-DENTISTE" in text_upper
              or "CHIRURGIEN DENTIST" in text_upper):
            result["is_dentist"] = True
            result["profile_type"] = "Dentiste"

            # Now check qualified status
            if "QUALIFIED: NO" in text_upper or "QUALIFIED:NO" in text_upper:
                result["qualified"] = False
            else:
                result["qualified"] = True

            # Extract score
            import re
            score_match = re.search(r'SCORE:\s*(\d+)', text, re.IGNORECASE)
            if score_match:
                result["score"] = int(score_match.group(1))
            else:
                result["score"] = 90

        # Fallback: check QUALIFIED: indicator at end
        elif "QUALIFIED: YES" in text_upper or "QUALIFIED:YES" in text_upper:
            result["qualified"] = True
            result["is_dentist"] = True
            result["profile_type"] = "Dentiste"
            score_match = re.search(r'SCORE:\s*(\d+)', text, re.IGNORECASE)
            result["score"] = int(score_match.group(1)) if score_match else 90
        elif "QUALIFIED: NO" in text_upper or "QUALIFIED:NO" in text_upper:
            result["qualified"] = False
            result["profile_type"] = "SPAM"
            score_match = re.search(r'SCORE:\s*(\d+)', text, re.IGNORECASE)
            result["score"] = int(score_match.group(1)) if score_match else 0

        log_msg(f"[AI] {result.get('profile_type')} | Qualified: {result.get('qualified')} | Score: {result.get('score')}")
        return result

    except Exception as e:
        return {"error": f"API call failed: {str(e)}"}

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

def find_user_by_name(name: str) -> str:
    """Find a Slack user ID by their name (first.last or display name)"""
    if not SLACK_BOT_TOKEN:
        log_msg("[SLACK] Skipping user lookup - no token configured")
        return None
    try:
        log_msg(f"[SLACK] Looking up user: {name}")
        response = post("https://slack.com/api/users.list", headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        })

        result = response.json()
        if not result.get("ok"):
            log_msg(f"[SLACK] User list failed: {result.get('error', 'unknown')}")
            return None

        # Search for user by name or display name
        search_name = name.lower().replace(" ", ".").replace(".", "")
        for member in result.get("members", []):
            if not member.get("deleted", False):
                # Check real_name (e.g., "Alan Rossato")
                real_name = member.get("real_name", "").lower().replace(" ", "").replace(".", "")
                # Check name (e.g., "alan.rossato")
                username = member.get("name", "").lower().replace(".", "")
                # Check profile display_name
                display_name = member.get("profile", {}).get("display_name", "").lower().replace(" ", "").replace(".", "")

                if (search_name in real_name or
                    search_name in username or
                    search_name in display_name or
                    real_name in search_name or
                    username in search_name):
                    user_id = member.get("id")
                    log_msg(f"[SLACK] Found user: {member.get('real_name')} ({user_id})")
                    return user_id

        log_msg(f"[SLACK] User '{name}' not found")
        return None
    except Exception as e:
        log_msg(f"[SLACK] User lookup error: {e}")
        return None

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

        # Get engagement history if contact exists
        engagement_history = None
        if hubspot_result.get("contact_id"):
            engagement_history = get_engagement_history(hubspot_result["contact_id"])

        # AI qualification
        log_msg("[AI] Starting analysis...")
        prompt = build_qualification_prompt(lead, engagement_history)
        qualification = call_ai(prompt)

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
            send_dm_to_user("U08M425UAV8", dm_message)  # alan.rossato

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
