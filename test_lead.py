#!/usr/bin/env python3
from lead_qualifier_full import extract_lead_data, call_claude_code, build_qualification_prompt

# Test lead for Saha Kakai
lead = {
    'name': 'Saha Kakai',
    'email': 'saha.kakai@gmail.com',
    'phone': '0612345678',
    'country': 'France'
}

print('=' * 50)
print('  LEAD QUALIFICATION TEST: Saha Kakai')
print('=' * 50)
print()
print('Lead Data:')
for k, v in lead.items():
    if v:
        print(f'  {k}: {v}')
print()

# Build prompt and call AI
prompt = build_qualification_prompt(lead)
print('Calling AI...')
result = call_claude_code(prompt)

print()
print('RESULT:')
print(f'  Is Dentist: {result.get("is_dentist")}')
print(f'  Profile Type: {result.get("profile_type")}')
print(f'  Score: {result.get("score")}/100')
print(f'  Qualified: {result.get("qualified")}')
print(f'  Reasoning: {result.get("reasoning")[:300]}...')
