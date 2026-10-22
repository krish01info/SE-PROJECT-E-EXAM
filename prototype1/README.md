# Prototype 1

A command-line tool. You give it a folder of exam data, and it creates a folder with the exam plan.

```
python main.py data/<dataset>
```

```
output/<timestamp>/
├── schedule.csv                                         which paper is on which day and session
├── duties.csv                                           which teachers supervise which room
└── daywise_seating_plans/<date>/<session>/<room>.csv    picture of each room's seating
```

If no plan is possible, it says why.

Status: the current branch implements input validation, scheduling, seating and
invigilator assignment. The independent output checker and the full set of
impossible datasets remain to be built. The model-spec changes await team review.

## Run locally

Use Python 3.10 or newer with PyYAML installed. From `prototype1/`:

```sh
python3 main.py data/tiny
python3 main.py data/main --output output
python3 -m unittest discover -s tests -v
```

The scheduler uses deterministic backtracking. It checks student exam gaps and
safe capacity bounds while placing papers, then finds legal room seating and
eligible invigilators before accepting the schedule. It tries other seating
layouts if staffing fails; unstaffed candidates stay in memory for that run.
Separate-paper rooms take priority; mixing is allowed only when separate rooms
cannot seat everyone. Available duty places prefer teachers with fewer duties;
this is a best-effort choice, not a global fairness optimization.

A teacher who teaches every section writing a paper is exempt from supervising
that paper; the exemption is printed. Supervising their own students remains
forbidden, including for PhD scholars.

Exit codes: `0` writes the complete plan, `1` reports invalid input, and `2` writes
only `why.txt` explaining why no complete plan was found. Search is exhaustive
and may become slow on larger or difficult impossible datasets.

## Docs

| File | What it covers |
|---|---|
| [`docs/prototype1_expectations.md`](docs/prototype1_expectations.md) | What Ishan expects and why it is kept small. Start here. |
| [`docs/prototype1_model_spec.md`](docs/prototype1_model_spec.md) | Every rule and decision, the build steps, and what is still open. |
| [`docs/data_design_spec.md`](docs/data_design_spec.md) | Rules the input data must follow. |
