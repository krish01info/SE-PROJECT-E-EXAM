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

Status: steps 3 (load and validate) and 4 (schedule) are built, so right now it writes only `schedule.csv`. Seating and duties come next.

## Docs

| File | What it covers |
|---|---|
| [`docs/prototype1_expectations.md`](docs/prototype1_expectations.md) | What Ishan expects and why it is kept small. Start here. |
| [`docs/prototype1_model_spec.md`](docs/prototype1_model_spec.md) | Every rule and decision, the build steps, and what is still open. |
| [`docs/data_design_spec.md`](docs/data_design_spec.md) | Rules the input data must follow. |
