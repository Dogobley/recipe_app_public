# Issue 32: Describe the problem, features and expected behaviour in the README

Status: closed (2026-10-23)

## Goal

Someone opening the README for the first time understands, before any
operational detail, what problem the application solves, what it does, and how
it is expected to behave. A project reviewer can also find, from one table,
where each part of the project is documented and how to check it.

## Acceptance criteria

Opening and problem:

- [x] The README's intro (between the title and **Quick start**) no longer says
      "in-progress". In a few sentences it says who the application is for (a
      small confectionery producer pricing their own recipes) and the problem:
      working out what one unit of a recipe costs, and what a batch of N units
      costs, from ingredient package prices and weights, without spreadsheets
      or unit-conversion mistakes.

Features:

- [x] A **Features** section, directly after **Quick start**, describes what a
      user can do, matching the pages the application actually serves:
  - ingredient management: list, detail, create, edit, and delete (blocked
    while a recipe uses the ingredient)
  - recipe management: list, detail, create, edit (with any number of
    ingredient rows, saved all-or-nothing) and delete (which keeps the shared
    ingredients)
  - the recipe cost calculator: pick a recipe and a whole number of units
  - the health endpoint
- [x] Every page named there exists: its URL resolves in `config/urls.py` or
      `calculator/urls.py`.

Expected behaviour:

- [x] An **Expected behaviour** section, after **Features**, states the
      calculation rules from `_docs/architecture.md` in plain language:
  - grams are the internal unit, and kilograms are converted
  - cost per gram = package price / package weight in grams
  - a recipe's quantities and costs scale linearly with the unit count
  - the result shows cost per unit, weight per unit, the adjusted weight and
    cost of every ingredient, and the totals
  - calculations use exact decimals, and rounding happens only for display
  - calculating changes no stored data
- [x] The section includes a worked example: one recipe with at least two
      ingredients, at least one of them bought in `kg` and used in `g`,
      calculated for more than one unit. It gives each ingredient's adjusted
      weight and cost, the total cost, the total weight and the cost per unit,
      formatted the way the calculator page displays them.
- [x] A test in the default suite builds that exact example, runs it through
      the application's calculation service and display formatting, and fails
      if any figure in the README differs.
- [x] The section lists the validation behaviour a user sees: weights, prices
      and unit counts must be greater than zero, units are `g` or `kg`, an
      ingredient appears at most once per recipe, invalid input is shown again
      with field messages, and a missing record returns 404.
- [x] The section states what is out of scope, consistent with the
      architecture's Overview: one user, one currency, and no authentication,
      inventory, labour, packaging, overhead or multiple currencies.

Reviewer map:

- [x] A **Project map** section, near the end of the README, has a table with
      one row for each of these topics, in this order: problem description,
      product specification and task tracker, agent team, context management,
      application, testing, containerization, deployment, CI/CD,
      observability, alerting, and on-call agent. Each row links to where the
      topic is documented or implemented, and says in a few words how to check
      it.
- [x] Every link in that table points to a file or folder that exists in the
      repository, and a default-suite test fails if one does not.
- [x] The table claims nothing the repository does not do yet. Where work is
      still open (the recorded deployment demo in [Issue 33](issue33.md), and
      structured logs correlated by trace ID), the row says so and links the
      open issue if one exists.

Clean-up:

- [x] The duplicated sentence "Create and activate a virtual environment, then
      install dependencies:" in **Direct Python setup** appears once.
- [x] Every existing README instruction, link and test assertion about the
      README still holds, and `python -m pytest` passes.

## Out of scope

- The recorded deployment demo belongs to [Issue 33](issue33.md).
- Operational and deployment documentation stays in its current sections and in
  `docs/operator-guide.md`.

## Constraints

- Change only `README.md` and tests under `tests/`.
- Do not change application behaviour. If the README and the code disagree, the
  code is right; describe what it does.
- Follow `_docs/testing-guidelines.md`.

## Engineer comment

Changed files (nothing committed; the existing worktree changes to
`.github/workflows/promote-to-production.yml` and this issue's criteria are
untouched):

- `README.md`
  - Intro: the "in-progress" line is replaced by two short paragraphs on who
    the application is for (a small confectionery producer pricing their own
    recipes), the two questions it answers (cost of one unit, cost of N
    units), how (package price and weight, kg converted to grams, no
    spreadsheet, no unit-conversion mistakes), and that prices are in COP.
  - **Features** (directly after Quick start): one table each for ingredients
    and recipes (page, URL, what you can do), then the calculator and the
    health endpoint. Every URL is taken from `config/urls.py` /
    `calculator/urls.py`. Behaviour is described from the views and
    templates: protected ingredient deletion and its exact message, any number
    of ingredient rows (**Add ingredient row** / **Remove row**), the
    all-or-nothing transaction on add and edit, recipe deletion keeping the
    ingredients, the **Calculate recipe** button (`/calculator/?recipe=<id>`),
    and `/health/` returning `OK` / 200 or `Database unavailable.` / 500.
  - **Expected behaviour**: "Calculation rules" (grams internal, kg × 1000,
    cost per gram, ingredient cost, linear scaling, what the result shows,
    exact decimals with display-only rounding as `COP $1234.56` and weights to
    3 places, no stored data changed). Two points come from the code rather
    than the architecture: weight per unit is the value saved on the recipe,
    not derived from the ingredients, and each adjusted quantity is shown in
    the unit the recipe row uses. "Worked example", "What the application
    rejects" (with the forms' own messages) and "Out of scope" (one user, one
    currency, no authentication, inventory, labour, packaging, overhead or
    multiple currencies).
  - **Project map** (last section): the 12 topics in the required order, each
    with repository links and a short "how to check". The Deployment row says
    dev and production run through a local self-hosted runner, that this
    public repository has no runner so its build and deploy jobs are skipped,
    and links the open [Issue 33](issue33.md) for the recorded demo. The
    Observability row says traces and metrics are exported when an OTLP
    endpoint is set, and that structured logs correlated by trace ID are
    planned and not built yet (no issue exists, so none is linked). The
    localhost URL in the Application row is code text, not a link, so every
    link in the table is a repository path.
  - **Direct Python setup**: "Create and activate a virtual environment, then
    install dependencies:" now appears once.
- `tests/test_readme.py` (new, 9 tests, default suite): intro wording and no
  "in-progress"; section order (Quick start, Features, Expected behaviour
  first, Project map last); the setup sentence appears once; every backticked
  path in Features resolves (with `<id>` = 1 and the query string dropped) and
  together they cover all 12 feature URL names; the worked example; the
  Project map's topics and order, a link in every row, every link target
  existing (anchors checked against the target file's headings), and the
  open/planned wording for Issue 33 and trace-ID logs.

Worked example: **Chocolate truffles**, weight per unit 19.5 g, 24 units.
Cocoa powder (250 g, COP $13500.00, 1.5 g per unit), Dark chocolate 53%
(1 kg, COP $46900.00, 12 g per unit), Heavy cream (900 g, COP $17900.00, 6 g
per unit). Results: Cocoa powder 36 g / COP $1944.00, Dark chocolate 53%
288 g / COP $13507.20, Heavy cream 144 g / COP $2864.00; cost per unit
COP $763.13, total cost COP $18315.20, total weight 468 g. The README also
notes that 24 × COP $763.13 = COP $18315.12, which shows rounding happens only
for display.

How the figures were verified: they were first produced by a throwaway script
(scratchpad, not in the repository) that created the records in an in-memory
SQLite database and ran `calculate_recipe()` and the `currency` / `weight`
filters from `calculator/templatetags/presentation.py`. The README was written
from that output. `test_worked_example_figures_match_the_calculation_service_and_display_formatting`
now builds the same records, runs the service and filters, and compares them
with the README's three tables cell by cell. It also checks the prose figures
(each cost per gram, the exact cost per unit, the COP $18315.12 product) and
posts the example to `/calculator/` to check that the page shows every figure.
Mutation check: changing one figure, a link target, a Features URL or a cost
per gram in the README each made exactly one test fail, and the README was
restored afterwards.

Tests: `.venv/Scripts/python.exe -m pytest tests/test_readme.py`: 9 passed.
`.venv/Scripts/python.exe -m pytest`: 466 passed, 1 skipped, 30 deselected
(baseline 457 passed + 9 new). The existing README assertions in
`tests/test_quickstart.py`, `tests/test_ci_workflows.py`,
`tests/test_release_workflows.py` and `tests/test_operator_guide.py` still
pass. The suite ran on the SQLite fallback locally; CI runs it on PostgreSQL.

## QA: FAIL

- [x] Intro no longer says "in-progress"; it names the audience (a small confectionery producer pricing their own recipes) and the problem (cost of one unit and of a batch of N units from package prices and weights, without spreadsheets or unit-conversion mistakes) - PASS
- [x] **Features** directly after **Quick start**, matching the served pages (ingredient list/detail/create/edit/delete with protected deletion; recipe list/detail/create/edit with any number of rows saved atomically, delete keeping ingredients; calculator; health) - PASS
      Checked each statement against `calculator/views.py`, `forms.py`, `models.py` and the templates (messages, redirects, **Add ingredient row** / **Remove row**, `transaction.atomic`, `?recipe=<id>` preselection, `/health/` `OK` 200 / `Database unavailable.` 500, `compose.yaml` health check).
- [x] Every page named in Features resolves in `config/urls.py` or `calculator/urls.py` - PASS
- [x] **Expected behaviour** after Features states the calculation rules (grams internal, kg × 1000, cost per gram, linear scaling, result contents, exact decimals with display-only rounding, no stored data changed) - PASS
- [x] Worked example (3 ingredients, dark chocolate bought in `kg` and used in `g`, 24 units) with per-ingredient adjusted weight and cost, total cost, total weight and cost per unit, formatted as the page shows them - PASS
      Independently entered the example through the real forms (`/ingredients/add/`, `/recipes/add/`) in a throwaway in-memory SQLite database and posted it to `/calculator/`. The page shows 36 g / COP $1944.00, 288 g / COP $13507.20, 144 g / COP $2864.00, cost per unit COP $763.13, weight per unit 19.5 g, total cost COP $18315.20, total weight 468 g, exactly as in the README. Hand-computed Decimal values agree (exact cost per unit 763.1333…, 24 × 763.13 = 18315.12). The currency the app displays is `COP $…` with two decimals and no thousands separator, as the README says.
- [x] A default-suite test builds the example, runs it through `calculate_recipe` and the display filters, and fails if a README figure differs - PASS
      In a scratch copy outside the repository, changing any one of: an ingredient cost, an adjusted quantity, the total weight, the cost per unit, the requested units, a quantity per unit in the input table, a cost per gram in the prose, or the 18315.12 figure each made exactly one test fail (1 failed, 8 passed); the unchanged copy passed.
- [x] Validation behaviour listed (greater than zero, `g`/`kg`, ingredient once per recipe, invalid input re-shown with field messages, missing record 404) - PASS
- [x] Out of scope consistent with the architecture's Overview - PASS
- [ ] **Project map** table claims nothing the repository does not do yet - FAIL
      Compared each row with the files it links. The "Product specification and task tracker" row says "Each issue file has a status, acceptance criteria, and the Engineer, QA and closing comments." That is not true. `issue1.md`-`issue3.md`, `issue10.md`-`issue12.md` and `issue14.md`-`issue21.md` have no Engineer, QA or closing comment. `issue4.md`-`issue9.md` and `issue13.md` have an Engineer comment but no QA comment. `issue21-qa.md` has no status and no acceptance criteria. Open `issue32.md` and `issue33.md` have no QA or closing comment.
      Also overstated: the Observability row says traces and metrics go to "Tempo and Prometheus, shown in a provisioned Grafana dashboard". The only provisioned dashboard (`recipe-business-metrics.json`) has Prometheus panels only. Traces are viewed in Grafana Explore → Tempo, not on a dashboard.
      Observation (not counted as a failure): the Deployment row links `deploy.yml` and `promote-to-production.yml` and then says "its build and deploy jobs show as skipped". Only the jobs gated by `SELF_HOSTED_RUNNER` (the build and dev deploy in `build.yml`, and Deploy observability) are skipped. The manual Deploy and Promote workflows are not gated and would wait for a runner. The README's own CI/CD section says so.
- [x] **Project map** has the 12 topics in the required order, each with a link and a short "how to check" - PASS
- [x] Every Project map link exists, and a default-suite test fails if one does not - PASS
      In the scratch copy, breaking a file link (`_docs/process.md`, `on-call-engineer/README.md`, `build.yml`), a folder link (`_docs/issues/`), a cross-file anchor (`#creation-failure-alert`) or an in-README anchor (`#expected-behaviour`) each made exactly one test fail.
- [x] Open work is marked: the Deployment row links open [Issue 33](issue33.md) for the recorded demo; the Observability row says logs correlated by trace ID are planned and not built yet (no issue exists for them, and there is no trace-ID log correlation in `config/` or `calculator/`) - PASS
- [x] "Create and activate a virtual environment, then install dependencies:" appears once in **Direct Python setup** - PASS
- [x] Existing README instructions, links and README test assertions still hold, and `python -m pytest` passes - PASS
      The diff removes only the old intro line and the duplicated setup sentence. Every relative link in the whole README resolves.

Tests:
- `.venv/Scripts/python.exe -m pytest` (SQLite fallback): 466 passed, 1 skipped, 30 deselected
- `.venv/Scripts/python.exe -m pytest` against a throwaway `postgres:17-alpine` container configured like `ci.yml`'s tests job (`DJANGO_DB_ENGINE=django.db.backends.postgresql`, `calculator`/`calculator`/`calculator`, `127.0.0.1:55432`, `CI_EXPECTED_DATABASE_VENDOR=postgresql`): 467 passed, 30 deselected. The container was removed afterwards.
- `python -m pytest tests/test_readme.py` in a scratch copy with README mutations, as described above.

Nothing in the code was changed.

## Engineer comment (after QA FAIL)

Changed `README.md` (Project map only) and `tests/test_readme.py`; nothing
committed.

- **Product specification and task tracker** row: the general claim is
  replaced by one checked against every `issueN.md`. Every `issueN.md` has a
  status line and acceptance criteria. Issues 22 to 31 and 34 also carry an
  Engineer comment and a QA verdict; Issue 25 is a live check and records live
  runs instead of a QA verdict. Issues 24 to 31 and 34 end with the
  orchestrator's closing comment. The row now links `issue29.md`,
  `issue30.md` and `issue31.md` as good examples. (`issue21-qa.md` is not an
  `issueN.md` file, so the claim does not cover it.)
- **Observability** row: traces go to Tempo and are viewed in Grafana
  **Explore**; metrics go to Prometheus and are shown on the provisioned
  business-metrics dashboard, which is now linked
  (`recipe-business-metrics.json`, Prometheus panels only).
- **Deployment** row: only the jobs gated by `SELF_HOSTED_RUNNER` (the build
  and dev deploy in **Build and push**, and **Deploy observability**) show as
  skipped. The manual **Deploy** and **Promote dev to production** workflows
  are not gated, so a run would wait for a runner.
- Tests: three new tests. One checks the tracker row's wording and verifies
  it against the issue files: status line and `## Acceptance criteria` in
  every `issueN.md`, Engineer and QA sections in 22-24, 26-31 and 34,
  Engineer and live-run sections in 25, and `## Closed by orchestrator` in
  24-31 and 34. One checks the Deployment wording, that `build.yml` uses
  `vars.SELF_HOSTED_RUNNER`, and that `deploy.yml` and
  `promote-to-production.yml` do not. One checks the Observability wording
  and that the dashboard has no Tempo panel.

Tests: `.venv/Scripts/python.exe -m pytest tests/test_readme.py`: 12 passed.
`.venv/Scripts/python.exe -m pytest`: 469 passed, 1 skipped, 30 deselected.

## QA (re-check): FAIL

- [x] Intro no longer says "in-progress"; it names the audience and the problem - PASS
- [x] **Features** directly after **Quick start**, matching the served pages - PASS
      Section unchanged since the first QA run; still matches views, forms, models and templates.
- [x] Every page named in Features resolves in `config/urls.py` or `calculator/urls.py` - PASS
- [x] **Expected behaviour** states the calculation rules - PASS
- [x] Worked example with per-ingredient adjusted weight and cost, totals and cost per unit, formatted as the page shows them - PASS
      Re-entered the example through the real forms and posted it to `/calculator/` (throwaway in-memory SQLite). The page shows 36 g / COP $1944.00, 288 g / COP $13507.20, 144 g / COP $2864.00, cost per unit COP $763.13, weight per unit 19.5 g, total cost COP $18315.20, total weight 468 g, as in the README.
- [x] A default-suite test fails if any worked-example figure in the README differs - PASS (verified by mutation in the first QA run; test unchanged)
- [x] Validation behaviour listed - PASS
- [x] Out of scope consistent with the architecture's Overview - PASS
- [ ] **Project map** table claims nothing the repository does not do yet - FAIL
      I listed every `##` section in `issue1.md`-`issue34.md`. Every file has a `Status:` line and `## Acceptance criteria`. Issues 22-24, 26-31 and 34 each have an Engineer comment and a QA verdict. Issue 25 has an Engineer comment and live runs, and no QA verdict. Those parts of the tracker sentence are true.
      "Issues 24 to 31 and 34 end with the orchestrator's closing comment" is not true for Issue 24. In `issue24.md`, `## Closed by orchestrator` is followed by `## Live check from Issue 25 (2026-10-15)`, which is the file's last section. Issues 25-31 and 34 do end with `## Closed by orchestrator`.
      The new test checks only that `## Closed by orchestrator` is present, not that it is last, so it passes on the current files.
      The Observability row now matches the code. The collector sends traces to Tempo and metrics to Prometheus (`otel-collector-config.yaml`). The provisioned `recipe-business-metrics.json` has Prometheus panels only, covering all four application metrics, and Tempo is a Grafana data source for Explore.
      The Deployment row now matches the workflows. `build.yml`'s build and dev deploy jobs and `deploy-observability.yml` are gated by `vars.SELF_HOSTED_RUNNER`; `deploy.yml` (manual) and `promote-to-production.yml` are not.
- [x] **Project map** has the 12 topics in order, each with a link and a "how to check" - PASS
- [x] Every Project map link exists, and a default-suite test fails if one does not - PASS
      Every relative link in the README resolves, including the new `issue30.md`, `issue31.md` and `recipe-business-metrics.json` links.
- [x] Open work is marked (Issue 33 linked as open; trace-ID-correlated logs marked planned, no issue exists) - PASS
- [x] The setup sentence appears once in **Direct Python setup** - PASS
- [x] Existing README instructions, links and README test assertions still hold, and `python -m pytest` passes - PASS

New tests, mutation-checked in a scratch copy outside the repository. Each of these made exactly one test fail:
- renaming `## Closed by orchestrator` in `issue30.md`
- renaming `## QA: PASS` in `issue23.md`
- renaming `## Engineer comment` in `issue26.md`
- changing the `Status:` line in `issue5.md`
- renaming `## Acceptance criteria` in `issue12.md`
- adding a `SELF_HOSTED_RUNNER` gate to `deploy.yml`, or to `promote-to-production.yml`
- adding a Tempo data source to the dashboard JSON
- rewording the Observability, Deployment or tracker sentences to false ones.

Not caught (gaps, not failures on their own):
- a closing comment that is not the last section (see Issue 24 above)
- removing the `SELF_HOSTED_RUNNER` gate from `deploy-observability.yml`. The Deployment row claims that workflow is gated, but the test checks only `build.yml`.

Tests:
- `.venv/Scripts/python.exe -m pytest` (SQLite fallback): 469 passed, 1 skipped, 30 deselected
- `.venv/Scripts/python.exe -m pytest` against a throwaway `postgres:17-alpine` container configured like `ci.yml`'s tests job (`DJANGO_DB_ENGINE=django.db.backends.postgresql`, `calculator`/`calculator`/`calculator`, `127.0.0.1:55432`, `CI_EXPECTED_DATABASE_VENDOR=postgresql`): 470 passed, 30 deselected. The container was removed afterwards.
- `python -m pytest tests/test_readme.py` in a scratch copy under the mutations above.

Nothing in the code was changed.

## Engineer comment (after QA re-check FAIL)

- `README.md`, tracker row: "Issues 24 to 31 and 34 end with the
  orchestrator's closing comment" is now "include the orchestrator's closing
  comment". The old wording was wrong for `issue24.md`, where a live-check
  section follows the closing comment. The test asserts the new wording and
  still checks that `## Closed by orchestrator` is present in each of those
  issues.
- `tests/test_readme.py`, Deployment-row test: it now asserts that the row
  names **Build and push** and **Deploy observability**, and that both
  `build.yml` and `deploy-observability.yml` contain
  `if: vars.SELF_HOSTED_RUNNER == 'true'`. Mutation check: with the gate
  temporarily removed from `deploy-observability.yml`, 1 test failed (11
  passed). The file was restored and is unchanged in the worktree.

Tests: `.venv/Scripts/python.exe -m pytest`: 469 passed, 1 skipped, 30
deselected.

## QA (re-check 2): PASS

- [x] Intro no longer says "in-progress"; it names the audience and the problem - PASS
- [x] **Features** directly after **Quick start**, matching the served pages - PASS (section unchanged since the first QA run)
- [x] Every page named in Features resolves in `config/urls.py` or `calculator/urls.py` - PASS
- [x] **Expected behaviour** states the calculation rules - PASS
- [x] Worked example formatted as the calculator page shows it - PASS (unchanged; recomputed through the real forms and `/calculator/` in the previous re-check)
- [x] A default-suite test fails if any worked-example figure differs - PASS (unchanged; mutation-checked in the first QA run)
- [x] Validation behaviour listed - PASS
- [x] Out of scope consistent with the architecture's Overview - PASS
- [x] **Project map** table claims nothing the repository does not do yet - PASS
      I re-read every row against the files it links.
      Tracker row: every `issueN.md` (1-34) has a `Status:` line and `## Acceptance criteria`. Issues 22-24, 26-31 and 34 have an Engineer comment and a QA verdict. Issue 25 has an Engineer comment and live runs, and no QA verdict. Issues 24-31 and 34 each include `## Closed by orchestrator`, which is what the row now says ("include", not "end with").
      Deployment row: `build.yml` (both jobs) and `deploy-observability.yml` have `if: vars.SELF_HOSTED_RUNNER == 'true'`; `deploy.yml` and `promote-to-production.yml` have no gate.
      Observability row: traces go to Tempo and are viewed in Explore; metrics go to Prometheus and are shown on the Prometheus-only dashboard. Trace-ID log correlation is marked as planned.
      The Agent team, Context management, Application, Testing, Containerization, CI/CD, Alerting and On-call rows are unchanged and still match the repository.
- [x] **Project map** has the 12 topics in order, each with a link and a "how to check" - PASS
- [x] Every Project map link exists, and a default-suite test fails if one does not - PASS
- [x] Open work is marked (Issue 33 linked as open; trace-ID-correlated logs marked planned, no issue exists) - PASS
- [x] The setup sentence appears once in **Direct Python setup** - PASS
- [x] Existing README instructions, links and README test assertions still hold, and `python -m pytest` passes - PASS

Previous gaps, mutation-checked in a scratch copy outside the repository:
- Removing the `SELF_HOSTED_RUNNER` gate from `deploy-observability.yml` now fails 1 test (11 passed).
- The tracker claim is now "include", and the test checks presence. Renaming `## Closed by orchestrator` in `issue24.md` fails 1 test. So does renaming it in `issue34.md`, or rewording the row back to "end with".
- Dropping **Deploy observability** from the Deployment row fails 1 test.
- The unchanged copy passed 12 of 12.

`git diff HEAD -- .github/` is empty, including with whitespace and CR-at-EOL changes ignored. `promote-to-production.yml` shows as modified only because of line endings.

Tests:
- `.venv/Scripts/python.exe -m pytest` (SQLite fallback): 469 passed, 1 skipped, 30 deselected. PostgreSQL was not re-run because this round's test changes read only README and workflow files and do not touch the database. In the previous re-check the suite passed on PostgreSQL: 470 passed, 30 deselected.
- `python -m pytest tests/test_readme.py` in a scratch copy under the mutations above.

Nothing in the code was changed.

## Closed by orchestrator

QA (re-check 2) PASS on all acceptance criteria, after two FAIL rounds on Project map accuracy.
