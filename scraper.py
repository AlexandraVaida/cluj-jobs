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

    # Build job cards
    cards = ""
    for j in jobs:
        initials = "".join(w[0] for w in j["company"].split()[:2] if w).upper() or "?"
        cards += f"""
        <div class="card" data-company="{j['company']}" data-source="{j['source']}" data-text="{j['title'].lower()} {j['company'].lower()}">
          <div class="card-left">
            <div class="avatar">{initials}</div>
          </div>
          <div class="card-body">
            <a class="job-title" href="{j['url']}" target="_blank" rel="noopener">{j['title']}</a>
            <div class="job-meta">
              <span class="company-name">{j['company']}</span>
              <span class="dot">·</span>
              <span class="location">📍 {j.get('location','Cluj-Napoca')}</span>
            </div>
          </div>
          <div class="card-right">
            <span class="badge">{j['source']}</span>
            <span class="date">{j['date']}</span>
          </div>
        </div>"""

    company_opts = "\n".join(
        f'<option value="{c}">{c}</option>' for c in companies
    )
    source_opts = "\n".join(
        f'<option value="{s}">{s}</option>' for s in sources
    )

    updated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Cluj Tech Jobs</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<style>
  :root {{
    --burgundy:   #6B1F2A;
    --burgundy-d: #4E1620;
    --burgundy-l: #8B3040;
    --cream:      #F5EFE6;
    --cream-d:    #EDE4D6;
    --cream-dd:   #D9CEBD;
    --text:       #2C1810;
    --text-soft:  #6B5B52;
    --white:      #FDFAF6;
    --shadow:     rgba(44,24,16,.10);
    --radius:     14px;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--cream);
    color: var(--text);
    font-family: 'Inter', system-ui, sans-serif;
    min-height: 100vh;
  }}

  /* ── Header ── */
  header {{
    background: var(--burgundy-d);
    padding: 2.5rem 3rem 2rem;
    position: relative;
    overflow: hidden;
  }}
  header::after {{
    content: '';
    position: absolute;
    bottom: -1px; left: 0; right: 0;
    height: 32px;
    background: var(--cream);
    clip-path: ellipse(55% 100% at 50% 100%);
  }}
  .header-inner {{
    max-width: 1100px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 1rem;
  }}
  header h1 {{
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 2.4rem;
    font-weight: 700;
    color: var(--cream);
    letter-spacing: -0.02em;
    line-height: 1.1;
  }}
  header h1 span {{
    color: var(--cream-dd);
    font-weight: 400;
    display: block;
    font-size: 1rem;
    font-family: 'Inter', sans-serif;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
  }}
  .header-meta {{
    text-align: right;
    color: rgba(245,239,230,.6);
    font-size: 0.8rem;
    line-height: 1.6;
  }}
  .header-meta strong {{ color: var(--cream); }}

  /* ── Controls ── */
  .controls-wrap {{
    background: var(--white);
    border-bottom: 1px solid var(--cream-dd);
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 12px var(--shadow);
  }}
  .controls {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 1rem 3rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }}
  .search-wrap {{
    position: relative;
    flex: 1;
    min-width: 220px;
  }}
  .search-wrap svg {{
    position: absolute;
    left: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-soft);
    pointer-events: none;
  }}
  input[type=search] {{
    width: 100%;
    padding: 0.6rem 0.75rem 0.6rem 2.3rem;
    border: 1.5px solid var(--cream-dd);
    border-radius: 999px;
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    color: var(--text);
    background: var(--cream);
    outline: none;
    transition: border-color .2s, box-shadow .2s;
    -webkit-appearance: none;
  }}
  input[type=search]:focus {{
    border-color: var(--burgundy);
    box-shadow: 0 0 0 3px rgba(107,31,42,.12);
  }}
  select {{
    padding: 0.6rem 2rem 0.6rem 0.9rem;
    border: 1.5px solid var(--cream-dd);
    border-radius: 999px;
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    color: var(--text);
    background: var(--cream) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B5B52' stroke-width='2.5'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E") no-repeat right 0.7rem center;
    -webkit-appearance: none;
    appearance: none;
    outline: none;
    cursor: pointer;
    transition: border-color .2s;
  }}
  select:focus {{ border-color: var(--burgundy); }}
  #count {{
    margin-left: auto;
    font-size: 0.8rem;
    color: var(--text-soft);
    white-space: nowrap;
    font-weight: 500;
  }}

  /* ── Cards ── */
  .cards-wrap {{
    max-width: 1100px;
    margin: 2rem auto;
    padding: 0 3rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }}

  .card {{
    background: var(--white);
    border: 1px solid var(--cream-dd);
    border-radius: var(--radius);
    padding: 1.1rem 1.4rem;
    display: flex;
    align-items: center;
    gap: 1.1rem;
    transition: box-shadow .2s, border-color .2s, transform .15s;
    cursor: default;
  }}
  .card:hover {{
    box-shadow: 0 4px 20px var(--shadow);
    border-color: var(--burgundy-l);
    transform: translateY(-1px);
  }}

  .avatar {{
    width: 42px;
    height: 42px;
    min-width: 42px;
    border-radius: 10px;
    background: linear-gradient(135deg, var(--burgundy), var(--burgundy-l));
    color: var(--cream);
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 1rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    letter-spacing: 0.03em;
  }}

  .card-body {{
    flex: 1;
    min-width: 0;
  }}
  .job-title {{
    display: block;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 0.25rem;
    transition: color .15s;
  }}
  .job-title:hover {{
    color: var(--burgundy);
    text-decoration: underline;
    text-decoration-color: var(--burgundy-l);
  }}
  .job-meta {{
    font-size: 0.8rem;
    color: var(--text-soft);
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
  }}
  .company-name {{ font-weight: 500; }}
  .dot {{ color: var(--cream-dd); }}

  .card-right {{
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.4rem;
    flex-shrink: 0;
  }}
  .badge {{
    background: rgba(107,31,42,.08);
    color: var(--burgundy);
    border: 1px solid rgba(107,31,42,.18);
    padding: .2rem .65rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 500;
    white-space: nowrap;
  }}
  .date {{
    font-size: 0.75rem;
    color: var(--text-soft);
    white-space: nowrap;
  }}

  .hidden {{ display: none !important; }}

  #noResults {{
    text-align: center;
    padding: 4rem 2rem;
    color: var(--text-soft);
    font-size: 0.95rem;
  }}

  /* ── Footer ── */
  footer {{
    text-align: center;
    padding: 2rem;
    color: var(--text-soft);
    font-size: 0.78rem;
    border-top: 1px solid var(--cream-dd);
  }}
  footer a {{ color: var(--burgundy); text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}

  /* ── Responsive ── */
  @media (max-width: 700px) {{
    header {{ padding: 2rem 1.5rem 1.75rem; }}
    header h1 {{ font-size: 1.8rem; }}
    .header-meta {{ display: none; }}
    .controls {{ padding: 0.75rem 1.5rem; }}
    .cards-wrap {{ padding: 1rem 1.5rem 2rem; }}
    .card-right .badge {{ display: none; }}
  }}
</style>
</head>
<body>

<header>
  <div class="header-inner">
    <h1>
      <span>Cluj-Napoca</span>
      Tech Jobs Board
    </h1>
    <div class="header-meta">
      Updated <strong>{updated}</strong><br/>
      <strong>{len(jobs)}</strong> open positions · auto-refreshed daily
    </div>
  </div>
</header>

<div class="controls-wrap">
  <div class="controls">
    <div class="search-wrap">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input id="search" type="search" placeholder="Search by title, company, keyword…" oninput="filter()"/>
    </div>
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
</div>

<div class="cards-wrap" id="cardGrid">
  {cards}
  <p id="noResults" class="hidden">No jobs match your filters — try a different keyword.</p>
</div>

<footer>
  Data sourced from public job boards &amp; company career pages &nbsp;·&nbsp;
  <a href="jobs.json" target="_blank">Raw JSON</a> &nbsp;·&nbsp;
  Built for the Cluj tech community
</footer>

<script>
  function filter() {{
    const q = document.getElementById('search').value.toLowerCase();
    const co = document.getElementById('companyFilter').value;
    const src = document.getElementById('sourceFilter').value;
    const cards = document.querySelectorAll('.card');
    let visible = 0;
    cards.forEach(card => {{
      const text = card.dataset.text || card.textContent.toLowerCase();
      const company = card.dataset.company;
      const source = card.dataset.source;
      const show = (!q || text.includes(q))
                && (!co || company === co)
                && (!src || source === src);
      card.classList.toggle('hidden', !show);
      if (show) visible++;
    }});
    document.getElementById('count').textContent = visible + ' positions';
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
