---
name: msp-prospect-finder
description: Find SMB prospects for a managed service provider (MSP) on LinkedIn - run a Sales Navigator account search in the MSP's territory for firms with 0 to 2 IT people through Evaboot, score each company on its IT gap with the points in TARGETS.md (IT headcount, size, headcount growth, several sites, headquarters in the territory), then export the owners, COOs, operations and office managers of the companies kept, with verified emails. Use when the user asks for MSP lead generation, SMBs that need outsourced IT, or the IT decision makers of small firms.
---

# MSP prospect finder

This skill runs inside a clone of https://github.com/evaboot-labs/msp-prospect-finder: it uses the repo's `msp.py`, `TARGETS.md` and `docs/`. If `msp.py` is not in the working directory, clone the repo and work from there.

You do the Sales Navigator and Evaboot work through the Evaboot MCP server (`https://mcp.evaboot.com/mcp`). Every tool named below is an Evaboot MCP tool. `msp.py` scores the companies, builds the people search and writes the lists, the same way every time.

## Rules

- **You never contact anyone.** The lists tell the user which firms and people to reach; they do it.
- Confirm with the user before each `export_sn_search_or_list`. Show the search and the cost (1 Evaboot credit per exported company or person), then wait for a yes.
- Never invent a fact about a company or a person. The lists show only what the exports hold. The IT headcount is what LinkedIn counts in the Information Technology department: say "no IT person on LinkedIn", never "no IT team".
- Never ask for or paste an API key. The user writes `EVABOOT_API_KEY` into `.env` and exports it before starting the agent (`docs/connect-your-agent.md`).
- Print every Sales Navigator URL as a Markdown link with the URL in angle brackets: `[Open in Sales Navigator](<url>)`.

## Step 0: check the setup

1. If the Evaboot MCP tools are not in this session, walk the user through `docs/connect-your-agent.md`, then ask them to restart the agent from this folder.
2. Otherwise call `get_daily_export_quota`. If `has_valid_salesnav` is false, ask the user to sign in to Evaboot in Chrome, open any Sales Navigator search with the Evaboot extension, and click Export with Evaboot, then call it again.
3. Run `mkdir -p data lists`.
4. Read `TARGETS.md`. If it says `Status: EXAMPLE`, ask the user where their office is and how far they send a technician (the territory and its cities), which verticals they serve, which company sizes they price for, and who signs IT contracts at their clients. Rewrite the file and set `Status: yours`.

## Step 1: the account search

1. Build the account search with `build_sn_search_from_prompt`: say **account search, companies only**, with the headquarters location, industries and headcount from `TARGETS.md`. Ask the user how many companies they want and pass it as `max_results`. When it answers `building`, poll `get_search_build`.
2. Check the URL it returns. The builder can add a long `keywords:` list or shrink a metro area to one city: remove the keywords, and put the region back.
3. Add the two filters the builder leaves out. Insert each one right after `filters:List(` (`filters%3AList(`), followed by a comma (`%2C`):
   - IT department of 0 to 2 people: `(type:DEPARTMENT_HEADCOUNT,selectedSubFilter:13,rangeValue:(min:0,max:2))` (13 is Information Technology)
   - headcount growth above 10% in a year: `(type:COMPANY_HEADCOUNT_GROWTH,rangeValue:(min:10))`

   URL-encode the added text the same way as the rest of the URL (`:` is `%3A`, `,` is `%2C`).
4. Show the URL as a link so the user can open it and see the count. In our test (Dallas-Fort Worth, law, accounting and medical practices, 11-200 people) the IT filter left 436 companies and the growth filter 107.

## Step 2: export and score the companies

1. On a yes, export it with `export_sn_search_or_list` and `max_results` (25 to start), and poll `get_export` with `limit: 0` until it is done.
2. Save it:

```bash
set -a; [ -n "$EVABOOT_API_KEY" ] || . ./.env; set +a
curl -s -H "Authorization: Bearer $EVABOOT_API_KEY" \
  https://api.evaboot.com/v1/extractions/<extraction_id>/ > data/accounts-$(date +%F).json
python3 msp.py score data/accounts-$(date +%F).json --csv lists/accounts-$(date +%F).csv
```

3. Show the table: the kept firms first, then the dropped ones with the reason. Sales Navigator's headquarters filter also returns firms with only a branch in the area: `msp.py` drops a firm whose headquarters address names no territory city. Read the description of each kept firm: if one is clearly not an SMB that buys IT (a hospital system, a franchise run from elsewhere), say so and remove its id from `data/kept-<date>.txt`.

## Step 3: export the IT buyers

1. `python3 msp.py people-url data/kept-$(date +%F).txt` prints the people search: the kept companies, with the titles from `TARGETS.md`. Show it as a link.
2. On a yes, export it with `export_sn_search_or_list` and `max_results`, poll `get_export`, and save it to `data/buyers-$(date +%F).json` with the same `curl`.
3. `python3 msp.py leads data/buyers-$(date +%F).json --csv lists/buyers-$(date +%F).csv` writes the list. It drops the people outside the search filters (LinkedIn's title match is loose) and the people based outside `lead_area`. Show it, with the email status of each person.
4. A kept firm with nobody in the list has its IT buyer under another title (a CPA firm's partners, a clinic's practice administrator). Tell the user which firms these are and offer to add a title to `TARGETS.md`.

## Every week

Offer the n8n version (`docs/n8n.md`): every Monday it exports the account search, skips the firms already in the user's sheet, scores the new ones and exports their IT buyers into the same sheet.
