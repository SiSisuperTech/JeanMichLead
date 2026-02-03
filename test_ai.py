#!/usr/bin/env python3
"""Test AI qualification with mock data"""

import os
import json
from requests import post

# Config
ZAI_API_KEY = os.getenv("ZAI_API_KEY")
if not ZAI_API_KEY:
    print("ERROR: Set ZAI_API_KEY environment variable")
    exit(1)

# Mock lead data
MOCK_LEAD = {
    'fullName': 'Dr Jean Dupont',
    'email': 'jean.dupont@cabinet-dentaire-paris.fr',
    'phone': '01 23 45 67 89',
    'country': 'France',
    'postalCode': '75001'
}

def build_prompt(lead: dict) -> str:
    """Build AI prompt for GLM-4.7 with web_search tool"""
    return f"""You are a dental lead qualification analyst for France. You have access to web search - use it to verify leads.

LEAD TO VERIFY:
Name: {lead.get('fullName', 'Unknown')}
Email: {lead.get('email', 'Unknown')}
Phone: {lead.get('phone', 'Unknown')}
Country: {lead.get('country', 'Unknown')}

CRITICAL INSTRUCTIONS:
1. Use your web_search tool to verify this lead
2. Search: name + "dentiste", name + "chirurgien dentiste", name + "doctolib"
3. Check: Doctolib.fr, annuaire.sante.fr, Google, LinkedIn
4. A Gmail address does NOT automatically mean SPAM - many dentists use Gmail

SCORING (0-100):
+50: Found on Doctolib.fr or annuaire.sante.fr as dentist
+30: Email has dental domain (cabinet*.fr, *dentaire.fr, clinique*.fr)
+20: Professional email (not gmail/yahoo/hotmail)
+10: Complete info (name+email+phone)
-20: Gmail (ONLY if no web verification found)

QUALIFICATION:
Score >= 70: QUALIFIED
Score < 70: NOT QUALIFIED

ONLY classify as SPAM if:
- No web presence found AFTER searching
- Name appears nowhere as dentist

Return ONLY JSON:
{{"is_dentist": true/false, "profile_type": "Dentiste/Orthodontiste/Etudiant/Autre/SPAM", "score": 75, "qualified": true/false, "reasoning": "What you found and where"}}"""

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
            "max_tokens": 2000,
            "temperature": 0
        }

        print("[AI] Calling GLM-4.7 with web_search...")

        response = post(url, headers=headers, json=payload, timeout=120)

        if response.status_code != 200:
            return {"error": f"API returned {response.status_code}: {response.text[:200]}"}

        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        print(f"[AI] Response: {len(text)} chars")

        # Clean up markdown
        text = text.replace("```json", "").replace("```", "").strip()

        # Parse JSON
        try:
            result = json.loads(text)
            return result
        except json.JSONDecodeError:
            # Extract JSON from response
            brace_count = 0
            start = -1
            for i, ch in enumerate(text):
                if ch == "{":
                    if brace_count == 0:
                        start = i
                    brace_count += 1
                elif ch == "}":
                    brace_count -= 1
                    if brace_count == 0 and start >= 0:
                        try:
                            json_str = text[start:i+1]
                            if json_str.count('"') % 2 != 0:
                                json_str += '"'
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            start = -1
            return {"error": "No valid JSON in response", "raw_preview": text[:500]}

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
        print("✅ LEAD QUALIFIED")
    else:
        print("❌ LEAD NOT QUALIFIED")

    print(f"Profile: {result.get('profile_type', 'Unknown')}")
    print(f"Score: {result.get('score', 0)}/100")
    print(f"Reasoning: {result.get('reasoning', 'N/A')}")
