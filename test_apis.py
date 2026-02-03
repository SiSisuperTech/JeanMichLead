#!/usr/bin/env python3
"""
Test Slack and HubSpot API connections
Run this to verify your bot can interact with both services
"""

import os
import sys
import json
from requests import post, patch, get

# ==================== CONFIG ====================
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN")
TEST_USER_ID = "U089Z240VD5"  # User to send test DM to (simon.gautier)

if not SLACK_BOT_TOKEN or not HUBSPOT_TOKEN:
    print("ERROR: Set SLACK_BOT_TOKEN and HUBSPOT_TOKEN environment variables")
    sys.exit(1)

print("=" * 60)
print("  API CONNECTION TEST")
print("=" * 60)
print()
print("REQUIREMENTS:")
print("  Slack Bot Scopes needed:")
print("    - chat:write          (send messages)")
print("    - chat:write.public   (post in channels)")
print("    - reactions:write     (add emoji reactions)")
print("    - channels:read       (read channel info)")
print("    - groups:read         (read private channels)")
print("    - im:write            (send DMs)")
print("    - users:read          (read user info)")
print()

# First, test bot auth
print("[0/3] Testing Slack Bot Auth...")
print("-" * 40)
response = post(
    "https://slack.com/api/auth.test",
    headers={
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    },
    timeout=10
)
result = response.json()
if result.get("ok"):
    print(f"  Bot: {result.get('bot', 'N/A')}")
    print(f"  User: {result.get('user', 'N/A')}")
    print(f"  Team: {result.get('team', 'N/A')}")
else:
    print(f"  ERROR: {result.get('error', 'unknown')}")
print()

# ==================== TEST HUBSPOT ====================
print("[1/3] Testing HubSpot API...")
print("-" * 40)

# Test searching for a contact
test_email = "papamaria696@gmail.com"
print(f"Searching for: {test_email}")

response = get(
    f"https://api.hubapi.com/crm/v3/objects/contacts/{test_email}",
    headers={
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json"
    },
    params={"idProperty": "email"},
    timeout=10
)

print(f"  Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    if data.get("results"):
        contact = data["results"][0]
        contact_id = contact["id"]
        properties = contact.get("properties", {})
        print(f"  Found: YES")
        print(f"  ID: {contact_id}")
        print(f"  Name: {properties.get('firstname', '')} {properties.get('lastname', '')}")
        print(f"  Status: {properties.get('hs_lead_status', 'N/A')}")
    else:
        print(f"  Found: NO (new lead)")
else:
    print(f"  ERROR: {response.text[:200]}")

print()

# ==================== TEST HUBSPOT UPDATE ====================
print("[2/3] Testing HubSpot UPDATE...")
print("-" * 40)

# Test updating a contact (using the contact we just found)
if response.status_code == 200 and data.get("results"):
    contact_id = data["results"][0]["id"]
    print(f"Updating contact: {contact_id}")

    response = patch(
        f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}",
        headers={
            "Authorization": f"Bearer {HUBSPOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "properties": {
                "hs_lead_status": "OPEN",
                "lead_status": "TESTED"
            }
        },
        timeout=10
    )

    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        print(f"  Result: UPDATE SUCCESSFUL")
    else:
        print(f"  ERROR: {response.text[:200]}")
else:
    print("  Skipping - no contact found to update")

print()

# ==================== TEST SLACK DM ====================
print("[3/4] Listing available users...")
print("-" * 40)

# First, list users to find the right user
response = post(
    "https://slack.com/api/users.list",
    headers={
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    },
    timeout=10
)

result = response.json()
print(f"  Users list: {result.get('ok', False)}")

if result.get("ok"):
    members = result.get("members", [])
    print(f"  Total members: {len(members)}")

    # Find Simon Gautier
    simon_id = None
    for member in members:
        name = member.get("real_name") or member.get("name", "")
        if "simon" in name.lower() or "gautier" in name.lower():
            print(f"  Found: {name} (ID: {member.get('id')}) - Deleted: {member.get('deleted', False)}")
            if "simon" in name.lower():
                simon_id = member.get("id")
                simon_name = name

    if simon_id:
        TEST_USER_ID = simon_id
        print(f"  Using: {simon_name} ({simon_id})")

print()
print("[4/4] Testing Slack DM...")
print("-" * 40)

print(f"Target user ID: {TEST_USER_ID}")
print("Opening DM channel...")
response = post(
    "https://slack.com/api/conversations.open",
    headers={
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    },
    json={"users": TEST_USER_ID},
    timeout=10
)

result = response.json()
print(f"  Open DM: {result.get('ok', False)}")
if not result.get("ok"):
    error = result.get('error', 'unknown')
    needed = result.get('needed', 'N/A')
    print(f"  Error: {error}")
    if needed:
        print(f"  Needed scopes: {needed}")

if result.get("ok"):
    dm_channel = result.get("channel", {}).get("id")
    print(f"  DM Channel ID: {dm_channel}")

    # Check if this is an actual DM or something else
    if dm_channel and dm_channel.startswith("D"):
        print(f"  This is a DM channel (starts with D)")
    elif dm_channel and dm_channel.startswith("G"):
        print(f"  This is a MPIM channel (starts with G)")

    # Try sending a SIMPLE plain text message (no formatting)
    print(f"Sending SIMPLE test message...")
    response = post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "channel": dm_channel,
            "text": "TEST MESSAGE from dental lead bot - if you see this, DM is working!"
        },
        timeout=10
    )

    result = response.json()
    print(f"  Send result: {result.get('ok', False)}")
    if result.get("ok"):
        print(f"  Message timestamp: {result.get('ts')}")
        print(f"  Channel: {result.get('channel')}")
        print(f"  CHECK YOUR SLACK APP - look for 'Direct Messages' with jeanmichlead bot")
    else:
        error = result.get('error', 'unknown')
        needed = result.get('needed', 'N/A')
        print(f"  Error: {error}")
        if needed:
            print(f"  Needed scopes: {needed}")
        print(f"  Full response: {result}")

print()
print("=" * 60)
print("  TEST COMPLETE")
print("=" * 60)
print()
print("If all tests passed, your bot is ready to use!")
print()
