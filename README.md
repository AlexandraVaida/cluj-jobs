# Cluj-Napoca Tech Jobs Board 🏔️

A **daily-updated, shareable job dashboard** for software & hardware positions in Cluj-Napoca, Romania.

**Live site:** `https://<your-github-username>.github.io/cluj-jobs/`

## What it does

- Scrapes job listings every day at 08:00 Romanian time (06:00 UTC)
- Sources: **hipo.ro**, **ejobs.ro**, **bestjobs.eu**, **LinkedIn** (public), + company career pages
- Companies tracked: UiPath, Endava, NTT Data, Bosch, Continental, Cognizant Softvision, Flutter/Betfair, METRO Digital, Yonder, Fortech, Siemens, Ericsson, Accenture, Globant
- Outputs a clean `docs/index.html` dashboard + `docs/jobs.json` raw data

## Setup (5 minutes)

### 1. Create a GitHub repository

```bash
cd cluj-jobs
git init
git add .
git commit -m "feat: initial cluj jobs board"
# Create repo on github.com, then:
git remote add origin https://github.com/<YOUR_USERNAME>/cluj-jobs.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to your repo → **Settings** → **Pages**
2. Set **Source** to `Deploy from a branch`
3. Set **Branch** to `main`, folder to `/docs`
4. Click **Save**

Your live URL will be: `https://<your-username>.github.io/cluj-jobs/`

### 3. First run

Trigger the workflow manually:
- Go to your repo → **Actions** → **Scrape Cluj-Napoca Tech Jobs** → **Run workflow**

After ~2 minutes, your site will be live and auto-updating daily! 🎉

## Run locally

```bash
python scraper.py
# Then open docs/index.html in your browser
```

## Project structure

```
cluj-jobs/
├── scraper.py              # Main scraper + HTML generator
├── docs/
│   ├── index.html          # Generated dashboard (served by GitHub Pages)
│   └── jobs.json           # Raw job data
└── .github/workflows/
    └── scrape.yml          # GitHub Actions daily schedule
```

## Adding more companies

Edit `COMPANY_SCRAPERS` in `scraper.py` and add an entry:

```python
{
    "name": "Company Name",
    "url": "https://careers.company.com/jobs?location=Cluj",
    "pattern": r'href="(/jobs/[^"]+)"[^>]*>\s*([^<]{5,100})',
    "title_group": 2,
},
```

## Raw data

The JSON feed is available at:
`https://<your-username>.github.io/cluj-jobs/jobs.json`

This can be consumed by other tools, Notion integrations, Zapier, etc.
