# Run it in n8n

[`n8n/msp-prospect-finder.json`](../n8n/msp-prospect-finder.json) is the same MSP prospect finder for n8n. Every Monday at 8 it exports your account search, scores the new firms on their IT gap, exports the IT buyers of the ones it keeps, and writes both lists into a Google Sheet. No AI model and no extra key: the scoring is a Code node. `n8n/build_workflow.py` regenerates the JSON.

## What runs

1. **Every Monday at 8** (or **Run now**) and **Your settings**: the account search, how many companies and people per run, the two tab URLs, and the points.
2. **Firms already in your sheet** (Google Sheets): the companies of earlier runs, so each run only adds new ones.
3. **Export the companies** and **Check the companies export** (Evaboot MCP): the companies of the account search, waited for every 30 seconds.
4. **Score the IT gap** (Code): the same points as `msp.py score`. **Add to Firms** writes every company, kept or not, with the reason.
5. **IT buyers search** (Code): the people search for the buyer titles at the kept firms, like `msp.py people-url`.
6. **Export the IT buyers** and **Check the buyers export** (Evaboot MCP): those people with verified emails.
7. **Buyer rows** (Code) and **Add to People**: one row per person, without the people outside the search filters or outside `lead_area`.

## Set it up

1. **Make the sheet:** one Google Sheet with two tabs.
   - `Firms`, header row: `Date, Keep, Score, Company, Industry, City, IT staff, Employees, Growth 1y %, Why, Website, LinkedIn id`
   - `People`, header row: `Date, Name, Title, Company, Location, Email, Email status, LinkedIn`
2. **Import** the JSON in n8n: *Workflows > Import from file*.
3. **Add two credentials:**
   - **Bearer Auth** named `Evaboot MCP (Bearer)`: your key from [dash.evaboot.com/dash/api/](https://dash.evaboot.com/dash/api/). Select it on the four Evaboot MCP nodes.
   - **Google Sheets** on the three sheet nodes.
4. **Fill in Your settings:** `account_search_url` (your Sales Navigator account search; the example is law, accounting and medical practices of 11 to 200 people in Dallas-Fort Worth, with 0 to 2 IT people and more than 10% growth), `accounts_per_run`, `people_per_run`, and `firms_tab_url` and `people_tab_url` (each with its `gid`). `profile` holds the territory cities, the points, `lead_area` and the buyer titles; keep it in step with `TARGETS.md`.
5. **Test:** set `accounts_per_run` and `people_per_run` to 5, click **Execute workflow** on **Run now**, and read both tabs.
6. **Publish** the workflow to run it every Monday.

## Good to know

- Each run spends 1 Evaboot credit per exported company and per exported person. LinkedIn serves a search in a changing order, so a weekly run can return companies you already have: they cost a credit but are not added twice.
- LinkedIn sometimes leaves a company's exact headcount at 0. The score then uses the headcount band (51 to 200).
- A run stops with an error when no new company is found, no firm is kept, or no buyer is found: widen the account search, add titles, or raise `accounts_per_run`.

Back to the [README](../README.md).
