"""
🧪 Dental Lead Qualifier - Module Testing
Test each component individually via command line

Usage:
    python test_modules.py --module slack
    python test_modules.py --module hubspot
    python test_modules.py --module claude
    python test_modules.py --module all
"""

import os
import sys
import json
import argparse
from datetime import datetime

# ==================== CONFIG ====================
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN")
PORT = 5678

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_info(text):
    print(f"{YELLOW}ℹ {text}{RESET}")

# ==================== MODULE 1: SLACK WEBHOOK ====================
def test_slack():
    """Test Slack API connection"""
    print_header("MODULE 1: SLACK API")

    from requests import get

    try:
        print_info("Testing Slack API connection...")

        response = get("https://slack.com/api/auth.test", headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
        })

        data = response.json()

        if data.get("ok"):
            print_success("Slack API connection: OK")
            print(f"  Team: {data.get('team')}")
            print(f"  User: {data.get('user')}")
            return True
        else:
            print_error(f"Slack API error: {data.get('error')}")
            return False

    except Exception as e:
        print_error(f"Slack connection failed: {e}")
        return False

# ==================== MODULE 2: HUBSPOT ====================
def test_hubspot():
    """Test HubSpot API connection"""
    print_header("MODULE 2: HUBSPOT CRM")

    from requests import post

    try:
        print_info("Testing HubSpot API connection...")

        # Test search endpoint - use empty filter to just list contacts
        response = post(
            "https://api.hubapi.com/crm/v3/objects/contacts/search",
            headers={
                "Authorization": f"Bearer {HUBSPOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "limit": 1
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success("HubSpot API connection: OK")
            print(f"  Total contacts: {data.get('total', 0)}")
            return True
        elif response.status_code == 401:
            print_error("HubSpot: Invalid API token")
            return False
        else:
            print_error(f"HubSpot error: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print_error(f"HubSpot connection failed: {e}")
        return False

# ==================== MODULE 3: LEAD EXTRACTION ====================
def test_extraction():
    """Test lead data extraction from message"""
    print_header("MODULE 3: LEAD DATA EXTRACTION")

    import re

    # Sample messages
    test_messages = [
        "New lead: Dr Jean Dupont, email: jean.dupont@cabinet-dentaire.fr, phone: 0123456789",
        "Prospect: Marie Martin, marie.martin@gmail.com, France",
        "Invalid message without lead data"
    ]

    pattern = r'(?:Dr|Doctor|Pr|Prof)?\s*([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'

    for i, msg in enumerate(test_messages, 1):
        print_info(f"Test message {i}: {msg[:50]}...")

        match = re.search(pattern, msg, re.IGNORECASE)

        if match:
            name = match.group(1).strip()
            print_success(f"  Extracted name: {name}")
        else:
            print_error("  No name found")

        # Extract email
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', msg)
        if email_match:
            print(f"    Email: {email_match.group()}")

    return True

# ==================== MODULE 4: PROMPT BUILDING ====================
def test_prompt():
    """Test qualification prompt generation"""
    print_header("MODULE 4: PROMPT GENERATION")

    sample_lead = {
        "fullName": "Dr Jean Dupont",
        "email": "jean.dupont@cabinet-dentaire.fr",
        "phone": "0123456789",
        "country": "France",
        "source": "Website"
    }

    email_hint = "YES" if any(x in sample_lead["email"].lower() for x in ["dr", "doctor", "cabinet"]) else "NO"

    prompt = f"""You are a dental lead qualification expert for a French dental software company.

LEAD DATA:
Name: {sample_lead['fullName']}
Email: {sample_lead['email']}
Phone: {sample_lead['phone']}
Country: {sample_lead['country']}
Source: {sample_lead['source']}

VERIFICATION SIGNALS:
✓ Email contains dental terms (dr/doctor/cabinet): {email_hint}

TASK:
1. Search Google for "{sample_lead['fullName']} dentiste" to verify if they are a real dentist
2. Check trusted sources: Doctolib, Ordre des Chirurgiens-Dentistes, sante.fr, ameli.fr
3. Analyze the lead based on search results + email pattern

SCORING CRITERIA (0-100):
+40 points: Name appears in dentist search results (verified dentist)
+30 points: Email contains dental-related terms
+20 points: Professional email domain (not gmail/yahoo/etc)
+10 points: Complete contact info (phone + email)

QUALIFICATION RULES:
- Score 70+ = QUALIFIED (hot lead)
- Score 40-69 = POSSIBLE (needs verification)
- Score <40 = UNQUALIFIED or SPAM

Profile types:
- "Dentiste": Confirmed dental professional
- "Autre": Related but not dentist (lab, supplier, student)
- "SPAM": Invalid, fake, or irrelevant

Return JSON only:
{{
  "is_dentist": true/false,
  "profile_type": "Dentiste"|"Autre"|"SPAM",
  "score": 0-100,
  "qualified": true/false,
  "reasoning": "brief explanation of score and decision"
}}"""

    print_success("Prompt generated successfully")
    print(f"\n{prompt[:500]}...\n")

    return True

# ==================== MODULE 5: CLAUDE CODE CLI ====================
def test_claude():
    """Test Claude Code CLI with GLM"""
    print_header("MODULE 5: CLAUDE CODE CLI + GLM")

    import subprocess

    test_prompt = """Say "Hello from Claude Code CLI" in JSON format: {"message": "..."}"""

    print_info("Testing Claude Code CLI...")

    try:
        # Check if claude command exists
        check = subprocess.run("claude --version", capture_output=True, timeout=5, shell=True)

        if check.returncode != 0:
            print_error("Claude Code CLI not found. Install from: https://claude.ai/download")
            return False

        print_success(f"Claude Code CLI found: {check.stdout.decode().strip()}")

        print_info("Sending test prompt with GLM-4.7...")

        env = os.environ.copy()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        env["CLAUDE_CONFIG_DIR"] = os.path.join(script_dir, ".claude")

        # Write temp prompt
        temp_file = os.path.join(script_dir, "test_prompt.txt")
        with open(temp_file, "w") as f:
            f.write(test_prompt)

        result = subprocess.run(
            f"claude \"{temp_file}\"",
            capture_output=True,
            text=True,
            timeout=30,
            shell=True,
            env=env
        )

        os.remove(temp_file)

        if result.returncode == 0:
            print_success("Claude Code CLI response:")
            print(f"  {result.stdout.strip()[:200]}")
            return True
        else:
            print_error(f"Claude Code CLI error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print_error("Claude Code CLI timeout")
        return False
    except FileNotFoundError:
        print_error("Claude Code CLI not installed")
        print_info("Install from: https://claude.ai/download")
        return False
    except Exception as e:
        print_error(f"Claude Code CLI test failed: {e}")
        return False

# ==================== MODULE 6: WEB SERVER ====================
def test_server():
    """Test Flask web server"""
    print_header("MODULE 6: WEB SERVER")

    try:
        import flask
        print_success(f"Flask installed: v{flask.__version__}")
    except ImportError:
        print_error("Flask not installed. Run: pip install flask")
        return False

    try:
        import requests
        print_success("Requests library installed")
    except ImportError:
        print_error("Requests not installed. Run: pip install requests")
        return False

    print_info("Checking if server is running...")

    try:
        response = requests.get(f"http://localhost:{PORT}/health", timeout=2)
        if response.status_code == 200:
            print_success("Server is running!")
            print(f"  Dashboard: http://localhost:{PORT}")
            print(f"  Webhook: http://localhost:{PORT}/webhook")
            return True
    except:
        pass

    print_info("Server not running. Start with: start.bat")
    print_info("  Or: python lead_qualifier_full.py")
    return False

# ==================== MAIN ====================
def main():
    parser = argparse.ArgumentParser(description="Test Dental Lead Qualifier modules")
    parser.add_argument("--module", "-m",
                       choices=["slack", "hubspot", "extraction", "prompt", "claude", "server", "all"],
                       default="all",
                       help="Which module to test (default: all)")

    args = parser.parse_args()

    print(f"\n{BLUE}🧪 Dental Lead Qualifier - Module Testing{RESET}")
    print(f"{BLUE}{'─'*60}{RESET}")

    results = {}

    if args.module in ["slack", "all"]:
        results["Slack API"] = test_slack()

    if args.module in ["hubspot", "all"]:
        results["HubSpot CRM"] = test_hubspot()

    if args.module in ["extraction", "all"]:
        results["Lead Extraction"] = test_extraction()

    if args.module in ["prompt", "all"]:
        results["Prompt Generation"] = test_prompt()

    if args.module in ["claude", "all"]:
        results["Claude Code CLI"] = test_claude()

    if args.module in ["server", "all"]:
        results["Web Server"] = test_server()

    # Summary
    print_header("TEST SUMMARY")
    for name, passed in results.items():
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {name:.<40} {status}")

    total = len(results)
    passed = sum(results.values())

    print(f"\n{BLUE}Result: {passed}/{total} modules passed{RESET}\n")

    return 0 if passed == total else 1

if __name__ == "__main__":
    # Fix Windows encoding
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    sys.exit(main())
