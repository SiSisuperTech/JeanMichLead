#!/usr/bin/env python3
"""Test HubSpot engagement history extraction"""

import os
import sys
import json
import re
from requests import get

HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not HUBSPOT_TOKEN:
    print("ERROR: Set HUBSPOT_TOKEN or pass as argument")
    exit(1)

def get_engagement_history(contact_id: str) -> dict:
    """Get all engagement history for a contact"""
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
                "properties": ["hs_note_body", "hs_createdate"],
                "archived": "false"
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            for note in data.get("results", []):
                props = note.get("properties", {})
                body = props.get("hs_note_body", "")
                # Clean HTML
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
                "properties": ["hs_call_title", "hs_call_body", "hs_call_direction", "hs_createdate"]
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
                "properties": ["hs_task_subject", "hs_task_status"]
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
                        "status": status,
                        "subject": subject
                    })

        # 4. Get Meetings
        response = get(
            "https://api.hubapi.com/crm/v3/objects/meetings",
            headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
            params={
                "limit": 10,
                "properties": ["hs_meeting_title", "hs_meeting_starttime"]
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
                        "title": title
                    })

        return history

    except Exception as e:
        print(f"Error: {e}")
        return history

if __name__ == '__main__':
    print("=" * 60)
    print("HUBSPOT ENGAGEMENT HISTORY TEST")
    print("=" * 60)

    history = get_engagement_history("dummy")

    print(f"\n1. NOTES ({len(history['notes'])} total):")
    for note in history['notes'][:5]:
        print(f"   [{note['date']}] {note['body']}")

    print(f"\n2. CALLS ({len(history['calls'])} total):")
    for call in history['calls'][:5]:
        print(f"   [{call['date']}] {call['direction']}: {call['title']}")

    print(f"\n3. TASKS ({len(history['tasks'])} total):")
    for task in history['tasks'][:5]:
        print(f"   [{task['status']}] {task['subject']}")

    print(f"\n4. MEETINGS ({len(history['meetings'])} total):")
    for meeting in history['meetings'][:5]:
        print(f"   [{meeting['date']}] {meeting['title']}")

    print("\n" + "=" * 60)
