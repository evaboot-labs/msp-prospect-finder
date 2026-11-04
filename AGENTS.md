# Agent instructions

This repo finds small and mid-size companies that need a managed service provider (MSP), and the people who buy IT there. It runs a Sales Navigator account search in the MSP's territory for firms with almost no IT staff, exports them with Evaboot, scores each one on its IT gap with the points in `TARGETS.md` (IT headcount, size, growth, several sites, headquarters inside the territory), then exports the owners, operations leads and office managers of the companies it keeps, with verified emails. The user does the outreach. When the user asks to find MSP prospects, SMBs that need IT support, or the IT decision makers of small firms:

1. Follow the skill in `skills/msp-prospect-finder/SKILL.md` step by step.
2. Read `TARGETS.md` for the territory, the account search, the points and who to reach. If it says `Status: EXAMPLE`, ask the user and update it.
3. Use `msp.py` to score the companies, build the people search and write the lists. The Evaboot MCP server does the Sales Navigator work (`.mcp.json`).
4. If the user is not connected yet, follow `docs/connect-your-agent.md` with them.
5. If the user wants n8n instead, follow `docs/n8n.md` with them one step at a time: you cannot click inside n8n, so say exactly what to do and wait for their confirmation.

Exports cost 1 Evaboot credit per company or lead. Confirm with the user before every export. Never contact anyone yourself. Never ask for or handle an API key: the user writes it into `.env`. Never commit `.env`, `data/` or `lists/`: they hold real people's data.
