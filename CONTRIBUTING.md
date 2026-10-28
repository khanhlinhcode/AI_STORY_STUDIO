# Contributing

Use immutable revisions, server-generated identifiers, workspace-scoped queries, and adapters for every external AI service. Never commit credentials, model weights, private voice samples, or unlicensed assets.

Before opening a change, run `make check`. Database changes require an additive Alembic migration and a rollback note. Any new AI backend must implement the adapter contract and pass the fake-adapter contract tests.

