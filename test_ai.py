#!/usr/bin/env python3
"""Test AI qualification with mock data"""

import os
import sys
import json
from requests import post

# Config - accept from env or arg
ZAI_API_KEY = os.getenv("ZAI_API_KEY") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not ZAI_API_KEY:
    print("ERROR: Set ZAI_API_KEY environment variable or pass as argument")
    print("Usage: python test_ai.py <api_key>")
    exit(1)

# Real lead data
MOCK_LEAD = {
    'fullName': 'Yann Panissard',
    'email': 'yann-panissard@orange.fr',
    'phone': '0000000',
    'country': 'France',
    'postalCode': '82700'
}

def build_prompt(lead: dict) -> str:
    """Build AI prompt for GLM-4.7 with web_search tool"""
    postal = lead.get('postalCode', '')
    name = lead.get('fullName', '')

    # Simple direct query that worked
    return f'Is "{name} dentiste {postal}" a real dentist? Search and give me the address, phone, and sources where you found this information. End with: QUALIFIED: yes/no and SCORE: X/100'

def call_ai(prompt: str) -> dict:
    """Call Z.ai GLM-4.7 with web_search tool"""
    try:
        url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
        headers = {
            "Authorization": f"Bearer {ZAI_API_KEY}",
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
            "max_tokens": 4000,
            "temperature": 0
        }

        print("[AI] Calling GLM-4.7 with web_search...")

        response = post(url, headers=headers, json=payload, timeout=120)

        print(f"[DEBUG] Status: {response.status_code}")
        print(f"[DEBUG] Response: {response.text[:500]}")

        if response.status_code != 200:
            return {"error": f"API returned {response.status_code}: {response.text[:200]}"}

        data = response.json()

        # Check for choices
        if "choices" not in data or not data["choices"]:
            return {"error": "No choices in response", "raw": data}

        text = data["choices"][0]["message"]["content"].strip()
        print(f"[AI] Response: {len(text)} chars")
        print(f"\n[Full Response]:\n{text}\n")

        # Parse the response
        result = {
            "is_dentist": False,
            "profile_type": "SPAM",
            "score": 0,
            "qualified": False,
            "reasoning": text[:500]
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

            # Check qualified status
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

        return result

    except Exception as e:
        return {"error": f"API call failed: {str(e)}"}

if __name__ == '__main__':
    print("=" * 60)
    print("TESTING AI LEAD QUALIFICATION")
    print("=" * 60)
    print(f"\nMock Lead:")
    print(f"  Name: {MOCK_LEAD['fullName']}")
    print(f"  Email: {MOCK_LEAD['email']}")
    print(f"  Phone: {MOCK_LEAD['phone']}")
    print()

    prompt = build_prompt(MOCK_LEAD)
    result = call_ai(prompt)

    print()
    print("=" * 60)
    print("RESULT:")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print()

    if result.get("qualified"):
        print("[OK] LEAD QUALIFIED")
    else:
        print("[X] LEAD NOT QUALIFIED")

    print(f"Profile: {result.get('profile_type', 'Unknown')}")
    print(f"Score: {result.get('score', 0)}/100")
    print(f"Reasoning: {result.get('reasoning', 'N/A')}")
