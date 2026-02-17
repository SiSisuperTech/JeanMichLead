# 🤖 Jean Mich Lead - AI Lead Qualifier

Hey team! 👋

We've deployed an **automated lead qualification bot** called **Jean Mich Lead** in the `#jordan-test` channel.

## What it does:

When a new lead message arrives (from Calendly, Meta, etc.), the bot:
1. 🔍 **Searches the web** to verify if the person is a real dentist
2. ✅ **Qualifies** or ❌ **Disqualifies** the lead
3. 💬 **Replies in the thread** with the result

## What you'll see:

**Qualified Lead:**
```
✅ **Dr. Sophie Martin** • Dentist
sophie.martin@cabinet-dental.fr • +33 6 12 34 56 78
✓ RPPS: 10123456789
Source: https://doctolib.fr/dentiste/sophie-martin
```

**Not Qualified:**
```
❌ **John Doe** • Patient
john@gmail.com • No phone
❌ Not a dentist
```

## What to do:

- ✅ **Qualified leads**: Follow up as usual
- ❌ **Not qualified**: Skip or verify manually if unsure
- 🤔 **Medium confidence**: Double-check before calling

## How it works:

The bot searches:
- Doctolib profiles
- Ordre des Chirurgiens-Dentistes
- Practice websites (lemedecin.fr, doctoome.com)
- LinkedIn, RPPS database

It uses **Claude AI with web search** to verify each lead automatically.

## Questions?

Ask Alan or ping in `#jordan-test` if you see any issues!

---
*Powered by n8n + Claude Haiku 4.5*
