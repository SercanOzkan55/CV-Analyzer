# CV Analyzer Documentation

This folder contains developer, architecture, usage, and deployment documentation for CV Analyzer.

## Start Here

- [Backend Architecture And Modularization Guide](backend-architecture.md)
- [Agent Workflow For Safe Product Changes](agent-workflow.md)
- [Usage Guide](usage.md)
- [Deployment Guide](deploy.md)

## Development Direction

The backend is being moved away from a large `main.py` file. New backend work must be modular:

```text
routes/<domain>.py
schemas/<domain>.py
services/<domain>.py
tests/test_<domain>.py
```

`main.py` should only create/configure the FastAPI app and register routers. Do not add new endpoint implementations, schemas, parser helpers, AI prompt builders, local persistence stores, or business workflows to `main.py`.

For parser, upload, recruiter, rewrite, billing, dashboard, and user-data changes, read the architecture guide before editing.

## Documentation Rules

When code ownership changes, update the matching documentation:

- Architecture changes: update [backend-architecture.md](backend-architecture.md).
- Agent/developer workflow changes: update [agent-workflow.md](agent-workflow.md) and [../AGENTS.md](../AGENTS.md).
- Local run or API usage changes: update [usage.md](usage.md).
- Deployment, CI, environment, or secret changes: update [deploy.md](deploy.md).
