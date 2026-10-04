# Repository agent instructions

- Never read from or write to `docs/scratchpad.md`. The user copies relevant requirements into the conversation.
- Graphify is an optional local development aid. For architecture, dependency, or change-impact questions, run `graphify query "<question>"` when a local graph is available.
- Set up Graphify from the active development environment with `./bin/setup_graphify`; use `graphify update .` only when refreshing a local graph is useful.
