#!/usr/bin/env python3
"""Test HubSpot integration"""

import os
import sys
import json
from requests import post, patch

HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not HUBSPOT_TOKEN:
    print("ERROR: Set HUBSPOT_TOKEN environment variable or pass as argument")
    print("Usage: python test_hubspot.py <api_key>")
    exit(1)

def check_contact(email: str) -> dict:
    """Check if contact exists in HubSpot"""
    print(f"[HUBSPOT] Searching for: {email}")
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
                "properties": ["hs_lead_status", "lifecyclestage", "firstname", "lastname", "email"],
                "limit": 1
            },
            timeout=10
        )

        data = response.json()
        results = data.get("results", [])
        exists = len(results) > 0

        if exists:
            contact = results[0]
            props = contact.get("properties", {})
            print(f"[HUBSPOT] Found: {props.get('firstname')} {props.get('lastname')}")
            print(f"[HUBSPOT] Email: {props.get('email')}")
            print(f"[HUBSPOT] Lifecycle: {props.get('lifecyclestage')}")
            print(f"[HUBSPOT] Lead Status: {props.get('hs_lead_status')}")
            return {"exists": True, "contact_id": contact["id"], "properties": props}
        else:
            print(f"[HUBSPOT] Not found")
            return {"exists": False, "contact_id": None}

    except Exception as e:
        print(f"[ERROR] {e}")
        return {"exists": False, "error": str(e)}

def update_contact(contact_id: str, qualified: bool) -> bool:
    """Update HubSpot contact status"""
    status = "Qualified" if qualified else "UNQUALIFIED"
    print(f"[HUBSPOT] Updating {contact_id} -> {status}")

    try:
        if qualified:
            properties = {
                "lifecyclestage": "lead",
                "hs_lead_status": "OPEN",
                "lead_status": "Qualified"
            }
        else:
            properties = {
                "hs_lead_status": "UNQUALIFIED",
                "lead_status": "KO"
            }

        response = patch(
            f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}",
            headers={
                "Authorization": f"Bearer {HUBSPOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"properties": properties},
            timeout=10
        )

        if response.status_code in [200, 201]:
            print(f"[HUBSPOT] Updated successfully")
            return True
        else:
            print(f"[HUBSPOT] Failed: {response.status_code}")
            print(f"[HUBSPOT] Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("HUBSPOT INTEGRATION TEST")
    print("=" * 60)

    # Test 1: Search for an existing contact (use a test email)
    test_email = input("\nEnter email to search (or press Enter to skip): ").strip()

    if test_email:
        result = check_contact(test_email)

        if result.get("exists"):
            # Test 2: Update the contact
            contact_id = result["contact_id"]
            print("\n" + "-" * 60)
            action = input(f"Update this contact? (qualified/KO/none): ").strip().lower()

            if action == "qualified":
                update_contact(contact_id, True)
            elif action == "ko":
                update_contact(contact_id, False)
            else:
                print("Skipped update")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
