# Apply session blockers — 2026-09-18

## Status
- Scraped **210** matching roles from Greenhouse/Lever; **60** prioritized in `applications/tracker.csv`
- Materials ready: resume, DE/ML cover letters, outreach email template
- Greenhouse apply automation written (`scripts/apply_greenhouse.py`)
- **Cannot auto-submit yet** — nearly every US form requires work authorization / sponsorship answers

## Blockers (need from you)
1. **Are you currently authorized to work in the US?** (Yes/No)
2. **Will you now or in the future need visa sponsorship?** (Yes/No) — e.g. H-1B after OPT
3. **LinkedIn URL** (required on many forms, e.g. Gusto)
4. **ZIP / city** of primary residence
5. **Portfolio URL** if you have one
6. Connect **Gmail** MCP auth (timed out twice) for email outreach
7. Log into **LinkedIn / Handshake / Jobright / Indeed** in this environment (or apply Easy Apply yourself using the tracker links)

## Immediate next step after you reply
```bash
# edit materials/applicant_profile.json with auth + linkedin + zip
python3 job-search/scripts/apply_greenhouse.py --limit 20 --submit
```

## Manual apply (today)
Open `applications/tracker.csv` and apply the top Data Engineer rows on company career pages / LinkedIn Easy Apply while auth answers are pending.
