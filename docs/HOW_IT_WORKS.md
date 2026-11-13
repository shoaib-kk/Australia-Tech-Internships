# How it works

A small Python pipeline, run every day by GitHub Actions, that reads structured job data straight from employers' applicant-tracking systems. It doesn't scrape job-board HTML.

| Source | What it is |
|---|---|
| Greenhouse, Lever, Ashby, SmartRecruiters | Public job-board APIs these systems publish for each employer |
| Workday | The JSON search endpoint behind every `*.myworkdayjobs.com` careers site |
| Amazon | The JSON search behind amazon.jobs |
| Contributors | Roles added through the "Add a role" issue form, stored in `config/manual_roles.yaml` |

```
fetch (parallel, per board) -> filter -> score -> dedupe -> archive -> README + outputs
```

- **Filter** ([`config/filters.yaml`](../config/filters.yaml)): early-career title, not senior, an Australian location, posted within 60 days. Broad grad programs are kept unless the title names a non-tech stream.
- **Categorise and score:** Data/ML/AI, Software, Cloud, Cyber, IT, then general programs.
- **Dedupe:** same company + title + city counts as one role.
- **Archive** (`data/seen.json`): every role found this year. A role is "open" if it was seen on the latest run. Closed roles stay listed until the end of the year.
- **Fault tolerant:** a board that errors is logged without stopping the run.

## Outputs

- `README.md`: the public list, rebuilt every run.
- `output/new_this_week.md`: roles first seen in the last 7 days.
- `output/openings.csv` and `output/openings.json`: every open role, with run stats and errors.

## Run it yourself

```bash
pip install -e ".[dev]"
pytest                               # offline tests with mocked APIs
python -m job_radar validate         # check every configured board responds
python -m job_radar run --dry-run    # fetch and print, without writing anything
python -m job_radar run              # full run: updates README.md, data/ and output/
```

To track a different country or field, edit `config/companies.yaml` and `config/filters.yaml`.
