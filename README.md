# job-radar

A weekly pipeline that finds **tech internships, vacation programs and graduate roles in Australia** — software, data/ML/AI, cloud, cyber, IT — and reports only what's new since last week.

It reads structured data from sources built for this purpose rather than scraping job-board HTML:

| Source | What it is | Auth |
|---|---|---|
| Greenhouse, Lever, Ashby, SmartRecruiters | Public job-board APIs that applicant-tracking systems publish for each employer | none |
| Workday | The JSON search endpoint behind every `*.myworkdayjobs.com` careers site | none |
| [Adzuna](https://developer.adzuna.com) | Job-search API aggregating listings from many Australian boards | free key |

## Pipeline

```
fetch (parallel, per board)  ->  filter  ->  score  ->  dedupe  ->  diff vs last run  ->  outputs
```

- **Filter** (`config/filters.yaml`): early-career title (intern, vacationer, graduate, cadet, junior…), not senior, Australian location, posted within 60 days.
- **Categorise and score**: Data/ML/AI > Software > Cloud/Infra ≈ Cyber > IT/Tech > general grad programs. Bonuses for internships, Melbourne/VIC, skills mentioned (Python, SQL, ML…) and postings from this week.
- **Dedupe**: same company + title + city counts as one role, preferring the direct company link over an Adzuna redirect.
- **Diff**: `data/seen.json` remembers what has been reported before, so `new_this_week.md` only shows new roles.
- **Fault tolerant**: a board that errors is logged and listed in the report without stopping the run.

## Outputs (`output/`)

- `new_this_week.md`: digest of new roles plus the top roles that are still open
- `openings.csv`: every matching open role, sorted by score
- `openings.json`: the same data plus run stats and errors, for other tools to read

## Usage

```bash
pip install -e ".[dev]"
pytest                                # offline tests with mocked APIs
python -m job_radar validate          # check every configured board responds
python -m job_radar run               # full run (set ADZUNA_APP_ID / ADZUNA_APP_KEY for Adzuna)
python -m job_radar run --no-adzuna --dry-run
```

## Configuration

- `config/companies.yaml`: employers to check. To add one, open any of its job ads and copy the board ID from the URL (format notes are at the top of the file).
- `config/filters.yaml`: keywords, categories, weights and locations.
- `config/applied.csv`: roles you've already applied to, which are left out of the results.

## Automation

`.github/workflows/weekly.yml` runs every Sunday at 05:00 UTC on GitHub Actions. It runs the tests, then the pipeline, and commits `output/` and `data/seen.json` back to the repo. You can also start it from the Actions tab with **Run workflow**.
