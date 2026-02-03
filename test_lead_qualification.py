"""
Test Lead Qualification Engine with Fake Leads
Tests the GLM-4.7 + Web Search integration
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_with_fake_leads(api_key=None):
    """Test qualification with various fake leads"""

    # Import after path is set
    from lead_qualifier_full import build_qualification_prompt, call_ai_api

    # Set API key if provided
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    fake_leads = [
        {
            "id": "test-1",
            "fullName": "Dr Jean Dupont",
            "email": "j.dupont@cabinet-dentaire-paris.fr",
            "phone": "+33 1 23 45 67 89",
            "country": "France",
            "expected": "QUALIFIED - Professional domain, has Dr title"
        },
        {
            "id": "test-2",
            "fullName": "Marie Martin",
            "email": "marie.martin@gmail.com",
            "phone": "+33 6 12 34 56 78",
            "country": "France",
            "expected": "POSSIBLE - Gmail but could be real dentist"
        },
        {
            "id": "test-3",
            "fullName": "Pierre Durant",
            "email": "p.durant@hotmail.com",
            "phone": "",
            "country": "France",
            "expected": "UNCERTAIN - No web verification possible"
        },
        {
            "id": "test-4",
            "fullName": "Dr Sophie Bernard",
            "email": "contact@clinique-bernard.fr",
            "phone": "+33 4 56 78 90 12",
            "country": "France",
            "expected": "QUALIFIED - Dr title + clinical domain"
        },
    ]

    print("=" * 60)
    print("LEAD QUALIFICATION ENGINE TEST")
    print("=" * 60)

    # Check API config
    api_key = os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    model = os.getenv("ANTHROPIC_MODEL", "glm-4.7")

    print(f"\nAPI Config:")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  API Key: {'Set (hidden)' if api_key else 'NOT SET'}")

    if not api_key:
        print("\nERROR: ANTHROPIC_API_KEY not set!")
        print("Set it with: export ANTHROPIC_API_KEY=your_key")
        return

    # Test each lead
    for i, lead in enumerate(fake_leads, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}/{len(fake_leads)}: {lead['id']}")
        print(f"{'='*60}")
        print(f"Name: {lead['fullName']}")
        print(f"Email: {lead['email']}")
        print(f"Phone: {lead['phone']}")
        print(f"Expected: {lead['expected']}")
        print("-" * 60)

        # Build prompt
        prompt = build_qualification_prompt(lead)
        print(f"\n[Prompt length: {len(prompt)} chars]")

        # Call API
        print("[Calling API with web search enabled...]")
        result = call_ai_api(prompt)

        # Display results
        print("\n[RESULT]")
        if "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  is_dentist: {result.get('is_dentist', '?')}")
            print(f"  profile_type: {result.get('profile_type', '?')}")
            print(f"  score: {result.get('score', 0)}/100")
            print(f"  qualified: {result.get('qualified', '?')}")
            print(f"  reasoning: {result.get('reasoning', '?')}")

    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print("="*60)

def test_direct_search(api_key=None):
    """Just test the web search API call directly using OpenAI SDK (z.ai compatible)"""

    api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.z.ai/api/paas/v4/")
    model = os.getenv("OPENAI_MODEL", "glm-4.7")

    if not api_key:
        print("ERROR: API key not set!")
        print("Pass it as argument: --api-key YOUR_KEY")
        return

    print("=" * 60)
    print("DIRECT WEB SEARCH TEST (OpenAI SDK + z.ai)")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print(f"\nSearching for: 'Dr Jean Dupont dentiste France'\n")

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    # z.ai's web_search tool format (OpenAI compatible)
    response = client.chat.completions.create(
        model=model,
        max_tokens=2000,
        temperature=0,
        extra_body={
            "tools": [{
                "type": "web_search",
                "web_search": {
                    "search_context_size": "medium"
                }
            }]
        },
        messages=[{
            "role": "user",
            "content": "Search the web for 'Dr Jean Dupont dentiste France' and tell me what you find. Is there a real dentist with this name?"
        }]
    )

    print("Response:")
    print("-" * 60)
    print(response.choices[0].message.content)

    # Check if web search was used
    if hasattr(response, 'web_search') and response.web_search:
        print("\n[Web search results used]")
        for result in response.web_search[:3]:
            print(f"  - {result.get('title', 'N/A')}")
    print("-" * 60)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Lead Qualification Engine")
    parser.add_argument("--direct", action="store_true", help="Test direct web search only")
    parser.add_argument("--leads", action="store_true", help="Test with fake leads")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--api-key", help="Anthropic/z.ai API key")

    args = parser.parse_args()

    if args.all or (not args.direct and not args.leads):
        test_direct_search(args.api_key)
        print("\n\n")
        test_with_fake_leads(args.api_key)
    elif args.direct:
        test_direct_search(args.api_key)
    elif args.leads:
        test_with_fake_leads(args.api_key)
