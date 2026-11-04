"""Builds n8n/msp-prospect-finder.json. Run: python3 n8n/build_workflow.py

Every Monday at 8 (or on Run now), Evaboot exports the companies of your Sales Navigator account search, a Code node
scores each one on its IT gap like msp.py (IT headcount, size, growth, several sites, headquarters in your territory)
and skips the companies already in your sheet, a second Code node builds the people search for the IT buyers of the
kept firms, Evaboot exports them with verified emails, and both lists land in your Google Sheet.
"""
import json
import uuid
from pathlib import Path

MCP = "https://mcp.evaboot.com/mcp"
EVABOOT_CRED = {"httpBearerAuth": {"id": "", "name": "Evaboot MCP (Bearer)"}}
SHEETS_CRED = {"googleSheetsOAuth2Api": {"id": "", "name": "Google Sheets account"}}
ACCOUNT_SEARCH = "https://www.linkedin.com/sales/search/company?query=(filters%3AList((type%3ACOMPANY_HEADCOUNT%2Cvalues%3AList((id%3AC%2CselectionType%3AINCLUDED)%2C(id%3AD%2CselectionType%3AINCLUDED)))%2C(type%3AREGION%2Cvalues%3AList((id%3A90000031%2CselectionType%3AINCLUDED)))%2C(type%3AINDUSTRY%2Cvalues%3AList((id%3A9%2CselectionType%3AINCLUDED)%2C(id%3A47%2CselectionType%3AINCLUDED)%2C(id%3A13%2CselectionType%3AINCLUDED)))%2C(type%3ACOMPANY_HEADCOUNT_GROWTH%2CrangeValue%3A(min%3A10))%2C(type%3ADEPARTMENT_HEADCOUNT%2CselectedSubFilter%3A13%2CrangeValue%3A(min%3A0%2Cmax%3A2))))"
PROFILE = {"territory": ["Dallas", "Fort Worth", "Plano", "Irving", "Frisco", "Richardson", "Addison", "Arlington",
                         "McKinney", "Allen", "Carrollton", "Grapevine", "Southlake", "Denton", "Lewisville"],
           "it_staff_max": 2, "seats_min": 20, "seats_max": 150, "growth_min": 10, "growth_high": 25, "keep_score": 5,
           "office_words": ["offices in", "locations in", "new office", "second office", "clinics in"],
           "lead_area": ["Texas", "Dallas-Fort Worth"],
           "titles": ["Owner", "Managing Partner", "COO", "Chief Operating Officer", "Firm Administrator",
                      "Practice Administrator", "Practice Manager", "Office Manager", "Operations Manager",
                      "Director of Operations", "IT Manager", "Systems Administrator"]}

nodes, connections = [], {}


def node(name, type_, version, params, pos, creds=None, **extra):
    n = {"parameters": params, "id": str(uuid.uuid4()), "name": name, "type": type_,
         "typeVersion": version, "position": pos, **extra}
    if creds:
        n["credentials"] = creds
    nodes.append(n)


def link(a, b, out=0):
    connections.setdefault(a, {}).setdefault("main", [])
    while len(connections[a]["main"]) <= out:
        connections[a]["main"].append([])
    connections[a]["main"][out].append({"node": b, "type": "main", "index": 0})


def mcp_call(name, tool, json_expr, pos):
    node(name, "@n8n/n8n-nodes-langchain.mcpClient", 1.1, {
        "endpointUrl": MCP, "authentication": "bearerAuth",
        "tool": {"__rl": True, "mode": "list", "value": tool, "cachedResultName": tool},
        "inputMode": "json", "jsonInput": json_expr, "options": {"timeout": 120000},
    }, pos, EVABOOT_CRED, executeOnce=True)


def code(name, js, pos, **extra):
    node(name, "n8n-nodes-base.code", 2, {"jsCode": js}, pos, **extra)


def is_equal(name, left, right, pos):
    node(name, "n8n-nodes-base.if", 2.2, {"conditions": {
        "options": {"caseSensitive": True, "typeValidation": "loose", "version": 2},
        "conditions": [{"id": str(uuid.uuid4()), "leftValue": left, "rightValue": right,
                        "operator": {"type": "string", "operation": "equals"}}],
        "combinator": "and"}, "options": {}}, pos)


def sheet(name, op, pos, **params):
    p = {"operation": op,
         "documentId": {"__rl": True, "mode": "url", "value": "={{ $('Your settings').first().json.%s }}" % params.pop("tab")},
         "options": {}, **params}
    p["sheetName"] = {"__rl": True, "mode": "url", "value": p["documentId"]["value"]}
    extra = {"alwaysOutputData": True, "executeOnce": True} if op == "read" else {}
    node(name, "n8n-nodes-base.googleSheets", 4.7, p, pos, SHEETS_CRED, **extra)


def poll(prefix, launch, pos):
    """Wait, check the export, loop until it is done; stop on a failed export."""
    x, y = pos
    node(f"Wait 30 s ({prefix})", "n8n-nodes-base.wait", 1.1, {"amount": 30}, [x, y])
    mcp_call(f"Check the {prefix} export", "get_export",
             "={{ JSON.stringify({ extraction_id: $('%s').first().json.structuredContent.result.extraction_id }) }}" % launch,
             [x + 220, y])
    is_equal(f"{prefix.capitalize()} done?", "={{ $json.structuredContent.result.status }}", "EXECUTED", [x + 440, y])
    code(f"Still running? ({prefix})", r"""
// Stop instead of waiting forever when the export failed.
const r = $json.structuredContent.result;
if (r.failure_reason || /FAIL|ERROR|CANCEL/i.test(r.status || '')) throw new Error(`The export stopped: ${r.status} ${r.failure_reason || ''}`);
return [$input.first()];
""", [x + 440, y + 180])
    link(launch, f"Wait 30 s ({prefix})")
    link(f"Wait 30 s ({prefix})", f"Check the {prefix} export")
    link(f"Check the {prefix} export", f"{prefix.capitalize()} done?")
    link(f"{prefix.capitalize()} done?", f"Still running? ({prefix})", out=1)
    link(f"Still running? ({prefix})", f"Wait 30 s ({prefix})")


SCORE_JS = r"""
// Same points as msp.py score: territory, IT headcount, size, growth, several sites.
const P = JSON.parse($('Your settings').first().json.profile);
const seen = new Set($('Firms already in your sheet').all().map(i => String(i.json['LinkedIn id'] || '')).filter(Boolean));
const num = v => { const n = parseFloat(String(v ?? '').replace(/[,%]/g, '')); return isNaN(n) ? null : n; };
const today = $now.toFormat('yyyy-MM-dd');
const out = [];
for (const c of $json.structuredContent.result.prospects || []) {
  const id = String(c['Company Linkedin URL Unique ID'] || '').replace(/\/$/, '').split('/').pop();
  if (seen.has(id)) continue;
  const m = /Information Technology:\s*(\d+)/.exec(c['Department Headcounts'] || '');
  const it = m ? Number(m[1]) : 0;
  const seats = num(c['Company Employee Exact Count']) || null;
  const hq = c['Company Headquarters (Full Address)'] || c['Company Location'] || '';
  let pts = 0, why = [], drop = '';
  if (c['Matches Filters'] === 'no_match') drop = `does not match the search (${c['No Match Reasons']})`;
  else if (P.territory.length && !P.territory.some(t => hq.split(',').map(x => x.trim().toLowerCase()).includes(t.toLowerCase())))
    drop = `headquarters outside your territory (${c['Company Location'] || hq || 'unknown'})`;
  else if (it > P.it_staff_max) drop = `${it} IT people on LinkedIn, an IT team already`;
  else {
    pts += it === 0 ? 3 : it === 1 ? 2 : 1;
    why.push(it === 0 ? 'no IT person on LinkedIn' : it === 1 ? 'one IT person' : `${it} IT people`);
    const band = c['Company Employee Range'] || '?', lh = (band.match(/\d+/g) || []).map(Number);
    if (seats && seats >= P.seats_min && seats <= P.seats_max) { pts += 1; why.push(`${seats} employees`); }
    else if (seats) why.push(`${seats} employees, outside ${P.seats_min}-${P.seats_max}`);
    // LinkedIn sometimes leaves the exact count at 0: the band overlaps your range
    else if (lh.length === 2 && lh[0] <= P.seats_max && lh[1] >= P.seats_min) { pts += 1; why.push(`${band} employees`); }
    else why.push(`${band} employees`);
    const g = num(c['Company Employee Growth 1 Year (%)']);
    if (g !== null && g >= P.growth_high) { pts += 3; why.push(`+${g}% staff in 1 year`); }
    else if (g !== null && g >= P.growth_min) { pts += 2; why.push(`+${g}% staff in 1 year`); }
    const text = `${c['Company Description'] || ''} ${c['Company Specialities'] || ''}`.toLowerCase();
    const hit = P.office_words.filter(w => text.includes(w));
    if (hit.length) { pts += 1; why.push(`several sites ('${hit[0]}')`); }
  }
  out.push({ json: { Date: today, Keep: !drop && pts >= P.keep_score ? 'yes' : 'no', Score: drop ? '' : pts,
    Company: c['Company Name'] || '', Industry: c['Company Industry'] || '', City: c['Company Location'] || '',
    'IT staff': it, Employees: seats || c['Company Employee Range'] || '',
    'Growth 1y %': c['Company Employee Growth 1 Year (%)'] || '', Why: drop || why.join('; '),
    Website: c['Company Website URL'] || '', 'LinkedIn id': id } });
}
if (!out.length) throw new Error('No new company in this run: every company is already in your sheet.');
return out.sort((a, b) => (a.json.Keep !== 'yes') - (b.json.Keep !== 'yes') || (b.json.Score === '' ? -99 : b.json.Score) - (a.json.Score === '' ? -99 : a.json.Score));
"""

PEOPLE_JS = r"""
// Same as msp.py people-url: the IT buyers (titles) of the kept firms.
const P = JSON.parse($('Your settings').first().json.profile);
const ids = $('Score the IT gap').all().filter(i => i.json.Keep === 'yes').map(i => i.json['LinkedIn id']);
if (!ids.length) throw new Error('No firm kept this week: loosen the profile or raise accounts_per_run.');
// Encode like Python's quote(safe=''): a raw parenthesis would break the Sales Navigator query.
const enc1 = s => encodeURIComponent(s).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
const enc = s => enc1(enc1(s));
const comp = ids.map(i => `(id%3A${enc('urn:li:organization:' + i)}%2CselectionType%3AINCLUDED)`).join('%2C');
const titles = P.titles.map(t => `(text%3A${enc(t)}%2CselectionType%3AINCLUDED)`).join('%2C');
const url = 'https://www.linkedin.com/sales/search/people?query=(filters%3AList('
  + `(type%3ACURRENT_COMPANY%2Cvalues%3AList(${comp}))%2C(type%3ACURRENT_TITLE%2Cvalues%3AList(${titles}))))`;
return [{ json: { url, firms: ids.length } }];
"""

ROWS_JS = r"""
// One row per IT buyer; people outside the search filters or based outside lead_area are dropped.
const P = JSON.parse($('Your settings').first().json.profile);
const today = $now.toFormat('yyyy-MM-dd');
const rows = ($json.structuredContent.result.prospects || [])
  .filter(p => !['no', 'no_match'].includes(String(p['Matches Filters'] || '').toLowerCase()))
  .filter(p => !P.lead_area.length || P.lead_area.some(a => String(p['Location'] || '').toLowerCase().includes(a.toLowerCase())))
  .map(p => ({ json: { Date: today, Name: p['Full Name'] || '', Title: String(p['Current Job'] || '').trim(),
    Company: p['Company Name'] || '', Location: p['Location'] || '', Email: p['Email'] || '',
    'Email status': p['Email Status'] || 'not found', LinkedIn: p['Linkedin URL Public'] || '' } }));
if (!rows.length) throw new Error('No IT buyer found inside the filters and your area.');
return rows;
"""

node("Every Monday at 8", "n8n-nodes-base.scheduleTrigger", 1.2, {"rule": {"interval": [
    {"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 8}]}}, [0, 0])
node("Run now", "n8n-nodes-base.manualTrigger", 1, {}, [0, 200])
node("Your settings", "n8n-nodes-base.set", 3.4, {"assignments": {"assignments": [
    {"id": str(uuid.uuid4()), "name": k, "type": t, "value": v} for k, t, v in [
        ("account_search_url", "string", ACCOUNT_SEARCH),
        ("accounts_per_run", "number", 25),
        ("people_per_run", "number", 25),
        ("firms_tab_url", "string", "PASTE_THE_FIRMS_TAB_URL_WITH_GID"),
        ("people_tab_url", "string", "PASTE_THE_PEOPLE_TAB_URL_WITH_GID"),
        ("profile", "string", json.dumps(PROFILE)),
    ]]}, "options": {}}, [220, 100])
sheet("Firms already in your sheet", "read", [440, 100], tab="firms_tab_url")
mcp_call("Export the companies", "export_sn_search_or_list",
         "={{ JSON.stringify({ search_url: $('Your settings').first().json.account_search_url, "
         "max_results: $('Your settings').first().json.accounts_per_run, "
         "name: 'MSP finder companies ' + $now.toFormat('yyyy-MM-dd') }) }}", [660, 100])
poll("companies", "Export the companies", [880, 100])
code("Score the IT gap", SCORE_JS, [220, 520])
sheet("Add to Firms", "append", [440, 400], tab="firms_tab_url",
      columns={"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
code("IT buyers search", PEOPLE_JS, [440, 600], executeOnce=True)
mcp_call("Export the IT buyers", "export_sn_search_or_list",
         "={{ JSON.stringify({ search_url: $json.url, max_results: $('Your settings').first().json.people_per_run, "
         "name: 'MSP finder IT buyers ' + $now.toFormat('yyyy-MM-dd') }) }}", [660, 600])
poll("buyers", "Export the IT buyers", [880, 600])
code("Buyer rows", ROWS_JS, [1540, 600])
sheet("Add to People", "append", [1760, 600], tab="people_tab_url",
      columns={"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})

for a, b in [("Every Monday at 8", "Your settings"), ("Run now", "Your settings"),
             ("Your settings", "Firms already in your sheet"),
             ("Firms already in your sheet", "Export the companies"),
             ("Score the IT gap", "Add to Firms"), ("Score the IT gap", "IT buyers search"),
             ("IT buyers search", "Export the IT buyers"), ("Buyer rows", "Add to People")]:
    link(a, b)
link("Companies done?", "Score the IT gap", out=0)
link("Buyers done?", "Buyer rows", out=0)

workflow = {"name": "MSP prospect finder (Evaboot MCP)", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}, "pinData": {}}
out = Path(__file__).with_name("msp-prospect-finder.json")
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
print(out, len(nodes), "nodes")
