#!/usr/bin/env python3
"""Test z.ai API call with retry - exactly like lead_qualifier_full.py"""

import os
import time
import re
from requests import post

# API key from environment or use provided
api_key = os.getenv("ZAI_API_KEY") or "6024c744cdc4468b8b337ff4df5038be.mmQhTB8WHG1rSXOp"

url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Test prompt - same format as the script
prompt = '''You are a lead qualification specialist.
Your task is to determine whether "Jean Dupont" is a REAL, PRACTICING DENTIST (chirurgien-dentiste).

Search the web using:
"Jean Dupont dentiste 75001"
"Jean Dupont chirurgien-dentiste 75001"

OUTPUT FORMAT (EXACT):
PROFILE: [Dentist / Not Dentist]
QUALIFIED: [yes/no]
SCORE: [0-100]
SOURCES:
- http://...
REASONING: [brief explanation]'''

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

print(f"[AI] API: {url}")
print(f"[AI] Key: {api_key[:20]}...")

# Retry loop - exactly like the script
max_retries = 3
for attempt in range(max_retries):
    try:
        print(f"[AI] Calling GLM-4.7 with web_search... (Attempt {attempt + 1}/{max_retries})")

        response = post(url, headers=headers, json=payload, timeout=180)

        if response.status_code != 200:
            print(f"[AI] HTTP {response.status_code}: {response.text[:300]}")
            if 400 <= response.status_code < 500:
                print(f"[AI] Client error - not retrying")
                break
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                print(f"[AI] Server error, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            break

        data = response.json()
        print(f"[AI] Raw response keys: {list(data.keys())}")

        if "choices" not in data or not data["choices"]:
            print(f"[AI] No choices in response: {str(data)[:300]}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                print(f"[AI] No choices, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            break

        content = data["choices"][0]["message"].get("content", "")
        text = content.strip()
        print(f"[AI] Response: {len(text)} chars")
        print(f"\n{'='*60}")
        print(text)
        print(f"{'='*60}\n")
        break

    except Exception as e:
        error_str = str(e)
        is_timeout = "timeout" in error_str.lower() or "timed out" in error_str.lower()

        if is_timeout:
            print(f"[AI] Timeout on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 3
                print(f"[AI] Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"[AI] All {max_retries} attempts timed out")
        else:
            print(f"[AI] Error: {error_str}")
        break
