"""Test if z.ai web_search actually works"""
import os
import sys
import json
from requests import post

ZAI_API_KEY = sys.argv[1] if len(sys.argv) > 1 else os.getenv("ZAI_API_KEY")

url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
headers = {"Authorization": f"Bearer {ZAI_API_KEY}", "Content-Type": "application/json"}

payload = {
    "model": "glm-4.7",
    "messages": [{"role": "user", "content": "Search for 'Yann Panissard dentiste Montech' and tell me what you find. Be specific about address, phone, and whether he is a real dentist."}],
    "tools": [{
        "type": "web_search",
        "web_search": {"enable": True, "search_result": True, "count": 5}
    }],
    "max_tokens": 4000,
    "temperature": 0,
    "stream": False
}

print("Testing z.ai web_search with simple query...")
print("-" * 50)

response = post(url, headers=headers, json=payload, timeout=60)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"\nFull JSON response:")
    print(json.dumps(data, indent=2)[:2000])
    if "choices" in data and data["choices"]:
        content = data["choices"][0]["message"]["content"]
        print(f"\nAI Response:")
        print(content)
        print(f"\nTool calls: {data['choices'][0]['message'].get('tool_calls', 'None')}")
else:
    print(f"Error: {response.text}")
