# Contributing

Thanks for helping other students find roles! There are three ways to help, and none of them need any code.

## ➕ Add a role

Use the **[Add a role](../../issues/new?template=add-role.yml)** form. A bot turns it into a pull request, and once it's merged the list updates within a few minutes.

A role belongs on the list if it is:

- **Early-career:** internship, vacationer, cadetship, graduate program, or a junior/entry-level role.
- **Tech:** software, data, AI/ML, cloud, DevOps, cyber security, IT, QA, or a broad program with tech streams.
- **In Australia:** or remote and open to people living in Australia.

Please link to the employer's own job page rather than a job board when you can. Roles with a closing date move to "Closed" automatically after that date.

## 🏢 Suggest a company

Use the **[Suggest a company](../../issues/new?template=add-company.yml)** form. Companies whose job ads live on Greenhouse, Lever, Ashby, SmartRecruiters or Workday can be checked automatically every day. If you're comfortable editing YAML, add a line to [`config/companies.yaml`](config/companies.yaml) and open a pull request instead.

## 🚩 Report a problem

If a role is closed, broken, not in Australia or not a tech role, use the **[Report a role](../../issues/new?template=report-role.yml)** form.

## Code changes

See [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) to run the pipeline locally. Please run `pytest` before opening a pull request.
