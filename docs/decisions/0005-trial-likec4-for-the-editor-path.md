# 0005: Trial LikeC4 for the browser editor path, keep Structurizr as the tool of record

Date: 2026-10-10 · Status: superseded by 0006 (trial concluded: LikeC4 adopted)

Amends, for the trial editor only: 0001, in its sentence "One image ... for
validation, local authoring and static-site export"; 0002, in its sentences "Every model
change is a change to `.dsl` files" and "Structurizr `local` renders the DSL". 0003 and
0004 stay unchanged.

## Context

The workflow is judged on three criteria, in this order: (1) user-friendly for
non-technical people who edit the model and reach a PR, (2) free (self-hosted,
containerised, no paid licence), (3) AI-friendly (people work on the model together with AI
models such as Claude Code). We compared LikeC4 with the Structurizr-based design (see the
linked comparison).

- Both tools are free and have container images. Neither needs a paid licence for what we
  use. LikeC4's image is larger (1.45 GB against 437 MB).
- LikeC4 looks better for the editing loop: official VS Code extension with completion and
  diagnostics, hot-reload preview, and browser layout editing saved as files in git. This is
  from its docs and has not been tried with our users or inside code-server.
- On AI-friendliness LikeC4 is moderately ahead on tooling: `llms.txt` and `llms-full.txt`
  (Structurizr's docs return 404 for both), an agent skill, an MCP server that queries the
  model, and `format --check`. Structurizr has its own free MCP server (validate, parse,
  inspect, export) and an `inspect` command. Validation time and error messages are a tie
  (about 1.8 s against 2.6 s per run on one machine). Models probably know Structurizr's DSL
  better; the one probe was anecdotal. Nothing measures the quality of AI-written models.
- Switching is expensive: no importer from Structurizr DSL, every workspace and tool would
  change, and LikeC4 metadata keys cannot contain a dot, so the `kubernetes.*` contract
  (`docs/conventions.md`, ADR 0003) would have to be renamed.
- Both tools depend on one main maintainer.

## Decision

Run a time-boxed trial of LikeC4 for the non-technical editor path (Flow B1) and keep
Structurizr as the tool of record for everything else.

- The trial uses a separate directory with a `.c4` port of `examples/shop` and a code-server
  image with the LikeC4 extension. The B1 rules stay unchanged: a fresh clone, a `model/*`
  branch, `submit` refuses `main`, branch protection on `main`, tokens from env vars.
- The trial includes an AI-assisted task: the same three edits made by an AI assistant in
  each tool, counting validation errors before the first clean pass. The assistant works
  only in the clone, never holds a token in a file, and reaches `main` only through the PR.
- Real workspaces stay in Structurizr DSL during the trial. `workspace.dsl` and the
  `kubernetes.*` properties are not renamed.
- At the end of the trial, the owner decides. A switch needs a new ADR that supersedes 0001
  and 0004 and amends 0002 and 0003. Not written now.

## Consequences

- Follow-up work, not done by this ADR: write the `.c4` port, build the editor image,
  write `submit` for both validators, and run the trial with one or two real users.
- `just check` discovers `workspace.dsl` only, so trial `.c4` files need their own check
  command (`likec4 validate`, and `likec4 format --check`) until a decision is made.
- ADR 0001's "one image for validation, local authoring and static-site export" becomes
  "one image for every real workspace; the trial directory also uses `likec4/likec4`" if
  this ADR is accepted.
- ADR 0002's "every model change is a change to `.dsl` files" becomes "every model change
  is a change to model text files (`.dsl`, and `.c4` in the trial directory)", and its
  statement that the B1 wrapper is Structurizr `local` becomes "Structurizr `local` or, in
  the trial, LikeC4".
- If the trial fails, delete the trial directory and record the result here; no accepted
  ADR was changed.
- A trial adds a second modelling language to maintain for its duration.
- Which AI assistant the users get, and whether an MCP server runs in the editor container,
  are open questions for the owner (see the comparison).

Sources: see [the comparison](../research/likec4-comparison.md) (L1-L28), in particular
https://likec4.dev/tooling/cli/, https://likec4.dev/tooling/editors/ and
https://likec4.dev/llms-full.txt
