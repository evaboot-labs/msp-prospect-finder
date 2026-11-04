#!/usr/bin/env python3
"""MSP prospect finder: score a Sales Navigator account export for an IT gap, then find who buys IT there.

Usage:
  python3 msp.py score <accounts.json> [--targets TARGETS.md] [--csv out.csv]
      Scores every company with the points in TARGETS.md and prints the ranked list (Markdown).
      Writes the kept company ids to data/kept-<date>.txt.
  python3 msp.py people-url <kept.txt> [--targets TARGETS.md]
      Prints the Sales Navigator people search for the IT buyers of the kept companies.
  python3 msp.py leads <leads.json> [--targets TARGETS.md] [--csv out.csv]
      Prints the IT buyers found, with their verified email (Markdown).

<accounts.json> and <leads.json> are Evaboot exports: GET https://api.evaboot.com/v1/extractions/<id>/
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

DEFAULTS = {
    "territory": [],
    "it_staff_max": 2,
    "seats_min": 20,
    "seats_max": 150,
    "growth_min": 10,
    "growth_high": 25,
    "keep_score": 5,
    "office_words": ["offices in", "locations in", "new office", "second office", "clinics in"],
    "lead_area": [],
    "titles": ["Owner", "Managing Partner", "COO", "Office Manager", "Operations Manager", "IT Manager"],
}


def targets(path):
    """Reads the `- key: value` lines of TARGETS.md over the defaults."""
    p = dict(DEFAULTS)
    if path and Path(path).exists():
        for line in open(path, encoding="utf-8"):
            m = re.match(r"-\s+`?(\w+)`?:\s*(.+)", line.strip())
            if m and m.group(1) in DEFAULTS:
                k, v = m.group(1), m.group(2).strip()
                p[k] = [x.strip() for x in v.split(";") if x.strip()] if isinstance(DEFAULTS[k], list) else float(v)
    return p


def num(v):
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def rows(path):
    d = json.load(open(path, encoding="utf-8"))
    return d.get("prospects", d) if isinstance(d, dict) else d


def it_staff(c):
    """People in the Information Technology department on LinkedIn (0 when the line is missing)."""
    m = re.search(r"Information Technology:\s*(\d+)", c.get("Department Headcounts") or "")
    return int(m.group(1)) if m else 0


def headcount(c):
    exact = num(c.get("Company Employee Exact Count"))
    return int(exact) if exact else None


def score_company(c, p):
    """Returns (score, reasons, excluded reason or '')."""
    if c.get("Matches Filters") == "no_match":
        return 0, [], f"does not match the search ({c.get('No Match Reasons')})"
    hq = c.get("Company Headquarters (Full Address)") or c.get("Company Location") or ""
    parts = [x.strip().lower() for x in hq.split(",")]  # match whole address parts: "Allen" is not "McAllen"
    if p["territory"] and not any(t.lower() in parts for t in p["territory"]):
        return 0, [], f"headquarters outside your territory ({c.get('Company Location') or hq or 'unknown'})"
    it = it_staff(c)
    if it > p["it_staff_max"]:
        return 0, [], f"{it} IT people on LinkedIn, an IT team already"
    pts, why = {0: 3, 1: 2}.get(it, 1), [{0: "no IT person on LinkedIn", 1: "one IT person"}.get(it, f"{it} IT people")]
    seats, band = headcount(c), c.get("Company Employee Range", "") or "?"
    lo_hi = [int(x) for x in re.findall(r"\d+", band)]
    if seats and p["seats_min"] <= seats <= p["seats_max"]:
        pts += 1
        why.append(f"{seats} employees")
    elif seats:
        why.append(f"{seats} employees, outside {int(p['seats_min'])}-{int(p['seats_max'])}")
    elif len(lo_hi) == 2 and lo_hi[0] <= p["seats_max"] and lo_hi[1] >= p["seats_min"]:
        pts += 1  # LinkedIn sometimes leaves the exact count at 0: the band overlaps your range
        why.append(f"{band} employees")
    else:
        why.append(f"{band} employees")
    growth = num(c.get("Company Employee Growth 1 Year (%)"))
    if growth is not None and growth >= p["growth_high"]:
        pts += 3
        why.append(f"+{growth:g}% staff in 1 year")
    elif growth is not None and growth >= p["growth_min"]:
        pts += 2
        why.append(f"+{growth:g}% staff in 1 year")
    text = f"{c.get('Company Description', '')} {c.get('Company Specialities', '')}".lower()
    hit = [w for w in p["office_words"] if w in text]
    if hit:
        pts += 1
        why.append(f"several sites ('{hit[0]}')")
    return pts, why, ""


def company_id(c):
    return str(c.get("Company Linkedin URL Unique ID", "")).rstrip("/").rsplit("/", 1)[-1]


def write_csv(path, data):
    if path and data:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)


def cmd_score(path, tpath, csv_path):
    p = targets(tpath)
    scored = []
    for c in rows(path):
        s, why, out = score_company(c, p)
        keep = not out and s >= p["keep_score"]
        scored.append({"Keep": "yes" if keep else "no", "Score": "" if out else s, "Company": c.get("Company Name", ""),
                       "Industry": c.get("Company Industry", ""), "City": c.get("Company Location", ""),
                       "IT staff": it_staff(c), "Employees": headcount(c) or c.get("Company Employee Range", ""),
                       "Growth 1y %": c.get("Company Employee Growth 1 Year (%)", ""), "Why": out or "; ".join(why),
                       "Website": c.get("Company Website URL", ""), "LinkedIn id": company_id(c)})
    scored.sort(key=lambda r: (r["Keep"] != "yes", -(r["Score"] if r["Score"] != "" else -99)))
    print("| Keep | Score | Company | IT staff | Employees | Growth 1y | Why |\n|---|---|---|---|---|---|---|")
    for r in scored:
        print(f"| {r['Keep']} | {r['Score']} | {r['Company']} | {r['IT staff']} | {r['Employees']} | {r['Growth 1y %']}% | {r['Why']} |")
    kept = [r["LinkedIn id"] for r in scored if r["Keep"] == "yes"]
    out = Path("data") / f"kept-{dt.date.today()}.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(kept) + "\n")
    print(f"\n{len(kept)} of {len(scored)} companies kept. Ids in {out}.")
    write_csv(csv_path, scored)


def cmd_people_url(kept_path, tpath):
    p = targets(tpath)
    ids = [l.strip() for l in open(kept_path) if l.strip()]
    if not ids:
        sys.exit("No company kept: loosen TARGETS.md or export more accounts.")
    if not p["titles"]:
        sys.exit("Add the buyer titles to TARGETS.md (titles: ...).")
    enc = lambda s: quote(s, safe="")
    comp = "%2C".join(f"(id%3A{enc(enc('urn:li:organization:' + i))}%2CselectionType%3AINCLUDED)" for i in ids)
    titles = "%2C".join(f"(text%3A{enc(enc(t))}%2CselectionType%3AINCLUDED)" for t in p["titles"])
    print("https://www.linkedin.com/sales/search/people?query=(filters%3AList("
          f"(type%3ACURRENT_COMPANY%2Cvalues%3AList({comp}))%2C(type%3ACURRENT_TITLE%2Cvalues%3AList({titles}))))")


def cmd_leads(path, tpath, csv_path):
    p = targets(tpath)
    out, dropped, away = [], 0, []
    for r in rows(path):
        if str(r.get("Matches Filters", "")).lower() in ("no", "no_match"):
            dropped += 1  # LinkedIn served someone outside the search (another company or title)
            continue
        where = str(r.get("Location", ""))
        if p["lead_area"] and not any(a.lower() in where.lower() for a in p["lead_area"]):
            away.append(f"{r.get('Full Name', '')} ({where or 'no location'})")  # runs another office
            continue
        out.append({"Name": r.get("Full Name", ""), "Title": str(r.get("Current Job", "")).strip(),
                    "Company": r.get("Company Name", ""), "Email": r.get("Email", ""),
                    "Email status": r.get("Email Status", "") or "not found", "LinkedIn": r.get("Linkedin URL Public", "")})
    print("| Name | Title | Company | Email status |\n|---|---|---|---|")
    for r in out:
        print(f"| {r['Name']} | {r['Title']} | {r['Company']} | {r['Email status']} |")
    safe = sum(r["Email status"] == "safe" for r in out)
    print(f"\n{len(out)} people kept, {safe} with a safe email. {dropped} dropped: outside the search filters.")
    if away:
        print(f"{len(away)} dropped: based outside your area, " + "; ".join(away) + ".")
    write_csv(csv_path, out)


def opt(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "score":
        cmd_score(a[1], opt(a, "--targets") or "TARGETS.md", opt(a, "--csv"))
    elif len(a) >= 2 and a[0] == "people-url":
        cmd_people_url(a[1], opt(a, "--targets") or "TARGETS.md")
    elif len(a) >= 2 and a[0] == "leads":
        cmd_leads(a[1], opt(a, "--targets") or "TARGETS.md", opt(a, "--csv"))
    else:
        sys.exit(__doc__)
