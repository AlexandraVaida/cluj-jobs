"""
Cluj-Napoca Tech Job Scraper
Scrapes jobs from company career pages + Romanian job boards.
Outputs: docs/jobs.json + docs/index.html
"""

import json
import re
import time
import os
import random
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, quote_plus
import urllib.request
import urllib.error

# ─── Helpers ────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ro;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch(url, timeout=15, retries=2):
    """Fetch a URL with retry logic. Returns HTML string or None."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("latin-1", errors="replace")
        except Exception as e:
            if attempt < retries:
                time.sleep(2 ** attempt + random.uniform(0, 1))
            else:
                print(f"  [WARN] Failed to fetch {url}: {e}")
                return None


def normalize_title(title):
    return re.sub(r"\s+", " ", title.strip())


def dedupe(jobs):
    seen = set()
    out = []
    for j in jobs:
        key = (j.get("company", ""), j.get("title", "").lower(), j.get("url", ""))
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


# ─── Scrapers ────────────────────────────────────────────────────────────────

def scrape_hipo(keyword="cluj"):
    """hipo.ro – Romania's tech-focused job board."""
    jobs = []
    url = f"https://www.hipo.ro/locuri-de-munca/lista/0/data-publicarii/toate/toate-locatiile/toate-companiile/toate-domeniile/toate-specializarile/?q={quote_plus(keyword)}&location=Cluj-Napoca"
    html = fetch(url)
    if not html:
        return jobs

    # Job cards on hipo
    pattern = re.compile(
        r'<div[^>]+class="[^"]*job[^"]*"[^>]*>.*?'
        r'<a[^>]+href="(/ro/job/[^"]+)"[^>]*>([^<]+)</a>.*?'
        r'<[^>]+class="[^"]*company[^"]*"[^>]*>([^<]+)<',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        jobs.append({
            "title": normalize_title(m.group(2)),
            "company": normalize_title(m.group(3)),
            "url": "https://www.hipo.ro" + m.group(1),
            "source": "hipo.ro",
            "location": "Cluj-Napoca",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })

    # Fallback: generic link scrape
    if not jobs:
        link_pat = re.compile(r'href="(/ro/job/[^"]+)"[^>]*>\s*([^<]{5,80})\s*<')
        for m in link_pat.finditer(html):
            jobs.append({
                "title": normalize_title(m.group(2)),
                "company": "N/A",
                "url": "https://www.hipo.ro" + m.group(1),
                "source": "hipo.ro",
                "location": "Cluj-Napoca",
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })

    return jobs[:50]


def scrape_ejobs(keyword="software+cluj"):
    """ejobs.ro – Romania's largest job board."""
    jobs = []
    url = f"https://www.ejobs.ro/locuri-de-munca/{keyword}/"
    html = fetch(url)
    if not html:
        return jobs

    # ejobs job links pattern
    link_pat = re.compile(
        r'href="(https://www\.ejobs\.ro/user/locuri-de-munca/[^"]+)"[^>]*title="([^"]+)"'
    )
    company_pat = re.compile(r'alt="([^"]+)"[^>]*class="[^"]*company[^"]*"')

    companies = [m.group(1) for m in company_pat.finditer(html)]
    for i, m in enumerate(link_pat.finditer(html)):
        jobs.append({
            "title": normalize_title(m.group(2)),
            "company": companies[i] if i < len(companies) else "N/A",
            "url": m.group(1),
            "source": "ejobs.ro",
            "location": "Cluj-Napoca",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })

    return jobs[:50]


def scrape_bestjobs(keyword="software", city="cluj-napoca"):
    """bestjobs.ro"""
    jobs = []
    url = f"https://www.bestjobs.eu/ro/locuri-de-munca?q={keyword}&county=Cluj&city={city}"
    html = fetch(url)
    if not html:
        return jobs

    # bestjobs job card pattern
    link_pat = re.compile(
        r'href="(https://www\.bestjobs\.eu/ro/locuri-de-munca/[^"]+)"[^>]*>\s*<[^>]+>\s*([^<]{5,100})'
    )
    for m in link_pat.finditer(html):
        title = normalize_title(m.group(2))
        if len(title) > 4 and len(title) < 120:
            jobs.append({
                "title": title,
                "company": "N/A",
                "url": m.group(1),
                "source": "bestjobs.eu",
                "location": "Cluj-Napoca",
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })

    return jobs[:50]


def scrape_linkedin_jobs(keyword="software engineer", location="Cluj-Napoca"):
    """LinkedIn public job search (no login)."""
    jobs = []
    encoded_kw = quote_plus(keyword)
    encoded_loc = quote_plus(location)
    url = (
        f"https://www.linkedin.com/jobs/search?"
        f"keywords={encoded_kw}&location={encoded_loc}&f_TPR=r86400"
    )
    html = fetch(url)
    if not html:
        return jobs

    # LinkedIn job card pattern
    link_pat = re.compile(
        r'href="(https://[^"]*linkedin\.com/jobs/view/[^"]+)"[^>]*>\s*([^<]{5,120})\s*<'
    )
    company_pat = re.compile(r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>\s*([^<]+)\s*<')

    companies = [normalize_title(m.group(1)) for m in company_pat.finditer(html)]
    for i, m in enumerate(link_pat.finditer(html)):
        title = normalize_title(m.group(2))
        if len(title) > 4:
            jobs.append({
                "title": title,
                "company": companies[i] if i < len(companies) else "N/A",
                "url": m.group(1).split("?")[0],
                "source": "linkedin.com",
                "location": "Cluj-Napoca",
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })

    return jobs[:50]


# ─── Company career page scrapers ────────────────────────────────────────────

def scrape_company_careers(company_name, careers_url, link_pattern, title_group=1, company_group=None):
    """Generic company career page scraper."""
    jobs = []
    html = fetch(careers_url)
    if not html:
        return jobs

    pat = re.compile(link_pattern, re.DOTALL | re.IGNORECASE)
    for m in pat.finditer(html):
        href = m.group(1) if m.lastindex >= 1 else ""
        title = normalize_title(m.group(title_group)) if m.lastindex >= title_group else ""
        if not title or len(title) < 3:
            continue
        full_url = href if href.startswith("http") else urljoin(careers_url, href)
        jobs.append({
            "title": title,
            "company": company_name,
            "url": full_url,
            "source": "careers page",
            "location": "Cluj-Napoca",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })

    return jobs[:30]


COMPANY_SCRAPERS = [
    # UiPath – major RPA/SW company in Cluj
    {
        "name": "UiPath",
        "url": "https://www.uipath.com/company/careers/jobs",
        "pattern": r'href="(/company/careers/jobs/[^"]+)"[^>]*>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Endava – IT services
    {
        "name": "Endava",
        "url": "https://www.endava.com/en/careers/all-jobs?location=Cluj-Napoca",
        "pattern": r'href="([^"]*careers[^"]*)"[^>]*>\s*<[^>]+>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # NTT DATA
    {
        "name": "NTT DATA",
        "url": "https://ro.nttdata.com/ro/cariere",
        "pattern": r'href="([^"]*job[^"]*)"[^>]*>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Bosch Cluj
    {
        "name": "Bosch",
        "url": "https://www.bosch.com/careers/job-search/?country=RO&city=Cluj-Napoca",
        "pattern": r'href="([^"]*job-opening[^"]*)"[^>]*>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Continental
    {
        "name": "Continental",
        "url": "https://www.continental.com/en/career/jobs/?country=RO&city=Cluj-Napoca",
        "pattern": r'href="([^"]*position[^"]*)"[^>]*title="([^"]{5,100})"',
        "title_group": 2,
    },
    # Cognizant Softvision (big presence in Cluj)
    {
        "name": "Cognizant Softvision",
        "url": "https://careers.cognizant.com/global/en/search-results?qcountry=Romania",
        "pattern": r'href="([^"]*job/[^"]+)"[^>]*>\s*<[^>]+>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Betfair (now Flutter)
    {
        "name": "Flutter/Betfair",
        "url": "https://www.flutter.com/careers/all-jobs/",
        "pattern": r'href="([^"]*job[^"]*)"[^>]*>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # METRO Digital
    {
        "name": "METRO Digital",
        "url": "https://metrodigital.de/en/career/jobs/",
        "pattern": r'href="([^"]*stellenangebote[^"]*|[^"]*job[^"]*)"[^>]*>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Yonder
    {
        "name": "Yonder",
        "url": "https://www.yonder.ro/careers",
        "pattern": r'href="(/careers/[^"]+)"[^>]*>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Fortech
    {
        "name": "Fortech",
        "url": "https://www.fortech.ro/careers/",
        "pattern": r'href="([^"]*career[^"]*)"[^>]*>\s*<[^>]+>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Siemens Cluj
    {
        "name": "Siemens",
        "url": "https://jobs.siemens.com/careers?query=&location=Cluj-Napoca%2C+Romania",
        "pattern": r'href="([^"]*careers/[^"]+)"[^>]*>\s*<[^>]+>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Ericsson
    {
        "name": "Ericsson",
        "url": "https://jobs.ericsson.com/careers?query=&location=Cluj-Napoca",
        "pattern": r'href="([^"]*careers/[^"]+)"[^>]*>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Accenture Romania
    {
        "name": "Accenture",
        "url": "https://www.accenture.com/ro-en/careers/jobsearch?jk=&sb=0&vw=0&is_rj=0&ct=Romania",
        "pattern": r'href="([^"]*accenture\.com[^"]*job[^"]*)"[^>]*>\s*([^<]{5,100})',
        "title_group": 2,
    },
    # Globant
    {
        "name": "Globant",
        "url": "https://jobs.globant.com/jobs?location=Cluj-Napoca",
        "pattern": r'href="([^"]*job[^"]+)"[^>]*>\s*<[^>]+>\s*([^<]{5,100})',
        "title_group": 2,
    },
]


def scrape_all_companies():
    all_jobs = []
    for cfg in COMPANY_SCRAPERS:
        print(f"  Scraping {cfg['name']}...")
        jobs = scrape_company_careers(
            cfg["name"],
            cfg["url"],
            cfg["pattern"],
            cfg.get("title_group", 1),
        )
        # Filter for Cluj-Napoca relevance if the page isn't location-specific
        print(f"    → {len(jobs)} jobs found")
        all_jobs.extend(jobs)
        time.sleep(random.uniform(0.5, 1.5))  # polite crawl delay
    return all_jobs


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Cluj-Napoca Tech Jobs Scraper")
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    all_jobs = []

    # Job boards
    print("\n[1/5] Scraping hipo.ro...")
    all_jobs.extend(scrape_hipo("software cluj"))
    all_jobs.extend(scrape_hipo("hardware cluj"))
    all_jobs.extend(scrape_hipo("engineer cluj-napoca"))
    time.sleep(1)

    print("\n[2/5] Scraping ejobs.ro...")
    all_jobs.extend(scrape_ejobs("software+cluj-napoca"))
    all_jobs.extend(scrape_ejobs("hardware+cluj-napoca"))
    time.sleep(1)

    print("\n[3/5] Scraping bestjobs.eu...")
    all_jobs.extend(scrape_bestjobs("software", "cluj-napoca"))
    all_jobs.extend(scrape_bestjobs("hardware", "cluj-napoca"))
    time.sleep(1)

    print("\n[4/5] Scraping LinkedIn (public)...")
    all_jobs.extend(scrape_linkedin_jobs("software engineer", "Cluj-Napoca, Romania"))
    all_jobs.extend(scrape_linkedin_jobs("hardware engineer", "Cluj-Napoca, Romania"))
    time.sleep(1)

    print("\n[5/5] Scraping company career pages...")
    all_jobs.extend(scrape_all_companies())

    # Deduplicate
    all_jobs = dedupe(all_jobs)
    print(f"\n✓ Total unique jobs collected: {len(all_jobs)}")

    # Sort by date desc, then company
    all_jobs.sort(key=lambda j: (j.get("date", ""), j.get("company", "")), reverse=True)

    # Save JSON
    os.makedirs("docs", exist_ok=True)
    with open("docs/jobs.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "updated": datetime.now(timezone.utc).isoformat(),
                "count": len(all_jobs),
                "jobs": all_jobs,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("✓ Saved docs/jobs.json")

    # Generate HTML
    generate_html(all_jobs)
    print("✓ Saved docs/index.html")


def generate_html(jobs):
    companies = sorted(set(j["company"] for j in jobs))
    sources = sorted(set(j["source"] for j in jobs))

    rows = ""
    for j in jobs:
        rows += f"""
        <tr data-company="{j['company']}" data-source="{j['source']}">
          <td class="date">{j['date']}</td>
          <td><a href="{j['url']}" target="_blank" rel="noopener">{j['title']}</a></td>
          <td>{j['company']}</td>
          <td><span class="badge">{j['source']}</span></td>
          <td>{j.get('location','Cluj-Napoca')}</td>
        </tr>"""

    company_opts = "\n".join(
        f'<option value="{c}">{c}</option>' for c in companies
    )
    source_opts = "\n".join(
        f'<option value="{s}">{s}</option>' for s in sources
    )

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Cluj-Napoca Tech Jobs</title>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d2e; --border: #2a2d3e;
    --accent: #6366f1; --accent2: #22d3ee;
    --text: #e2e8f0; --muted: #94a3b8;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}
  header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 1.5rem 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }}
  header h1 {{ font-size: 1.5rem; background: linear-gradient(135deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .meta {{ color: var(--muted); font-size: 0.85rem; }}
  .meta strong {{ color: var(--accent2); }}
  .controls {{ padding: 1.5rem 2rem; display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; background: var(--surface); border-bottom: 1px solid var(--border); }}
  input, select {{ background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 0.5rem 0.75rem; border-radius: 8px; font-size: 0.9rem; outline: none; transition: border-color .2s; }}
  input:focus, select:focus {{ border-color: var(--accent); }}
  input {{ min-width: 240px; }}
  #count {{ color: var(--muted); font-size: 0.85rem; margin-left: auto; }}
  .table-wrap {{ overflow-x: auto; padding: 0 2rem 2rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; }}
  th {{ text-align: left; padding: 0.75rem 1rem; font-size: 0.75rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg); }}
  td {{ padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); font-size: 0.9rem; vertical-align: middle; }}
  td.date {{ color: var(--muted); white-space: nowrap; font-size: 0.8rem; }}
  tr:hover td {{ background: var(--surface); }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ color: var(--accent2); text-decoration: underline; }}
  .badge {{ background: rgba(99,102,241,.15); color: var(--accent); border: 1px solid rgba(99,102,241,.3); padding: .2rem .6rem; border-radius: 999px; font-size: 0.75rem; white-space: nowrap; }}
  .hidden {{ display: none !important; }}
  @media (max-width: 600px) {{ .controls {{ flex-direction: column; }} input {{ min-width: 100%; }} }}
  .footer {{ text-align: center; padding: 2rem; color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--border); }}
  .pill {{ display: inline-block; background: rgba(34,211,238,.1); color: var(--accent2); padding: .15rem .5rem; border-radius: 999px; font-size: .75rem; margin-left: .5rem; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>🏔️ Cluj-Napoca Tech Jobs</h1>
    <p class="meta">Last updated: <strong>{updated}</strong> · <strong>{len(jobs)}</strong> positions</p>
  </div>
  <div class="meta">Auto-refreshed daily via GitHub Actions</div>
</header>

<div class="controls">
  <input id="search" type="search" placeholder="🔍 Filter by title, company, keyword…" oninput="filter()"/>
  <select id="companyFilter" onchange="filter()">
    <option value="">All companies</option>
    {company_opts}
  </select>
  <select id="sourceFilter" onchange="filter()">
    <option value="">All sources</option>
    {source_opts}
  </select>
  <span id="count"></span>
</div>

<div class="table-wrap">
<table id="jobTable">
  <thead>
    <tr>
      <th>Date</th>
      <th>Job Title</th>
      <th>Company</th>
      <th>Source</th>
      <th>Location</th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
<p id="noResults" class="hidden" style="text-align:center;padding:3rem;color:var(--muted);">No jobs match your filters.</p>
</div>

<div class="footer">
  Data scraped from public job boards and company career pages. · 
  <a href="jobs.json" target="_blank">Raw JSON</a> ·
  Built with ❤️ for the Cluj tech community
</div>

<script>
  function filter() {{
    const q = document.getElementById('search').value.toLowerCase();
    const co = document.getElementById('companyFilter').value;
    const src = document.getElementById('sourceFilter').value;
    const rows = document.querySelectorAll('#jobTable tbody tr');
    let visible = 0;
    rows.forEach(row => {{
      const text = row.textContent.toLowerCase();
      const company = row.dataset.company;
      const source = row.dataset.source;
      const show = (!q || text.includes(q))
                && (!co || company === co)
                && (!src || source === src);
      row.classList.toggle('hidden', !show);
      if (show) visible++;
    }});
    document.getElementById('count').textContent = visible + ' jobs shown';
    document.getElementById('noResults').classList.toggle('hidden', visible > 0);
  }}
  filter();
</script>
</body>
</html>"""

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
