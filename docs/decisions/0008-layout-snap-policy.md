# 0008: Layout (`.snap`) files: automatic by default, curated ones only through a reviewed PR

Date: 2026-10-11 · Status: accepted (owner approved the plan on 2026-10-11)

## Context

LikeC4 lays diagrams out automatically. It can also keep a manual layout of a view in
`.likec4/<viewId>.likec4.snap` inside the project folder (JSON5, generated, hundreds of lines
per view). Two things write those files:

- Dragging an element in the edit mode of `likec4 start`.
- Merely viewing a model with `likec4 start`: it wrote `examples/shop/.likec4/index.likec4.snap`
  while the owner only looked at the model.

Until now `tools/submit.py` committed the whole model directory, so these generated files went
into the PR (a 586-line snapshot for one dragged node, measured in
[research/likec4-web-editing.md](../research/likec4-web-editing.md)). The repository had no
ignore rule for `.likec4/`. [ADR 0006](0006-likec4-is-the-tool-of-record.md) left the policy to
the editor-image task. The owner's three points, 2026-10-11: automatic layout by default;
curated `.snap` files may go into git; Submit skips the others.

## Decision

- **Automatic layout is the default.** `.gitignore` ignores `.likec4/`, so a new snapshot
  (including the "viewed only" `index.likec4.snap`) is never picked up by `git add`.
- **A curated layout is a deliberate commit.** Someone who wants a hand-placed view adds the
  file with `git add -f` in a normal reviewed PR (Flow A, the local workflow). Once it is
  tracked, git keeps tracking it despite the ignore rule.
- **Submit commits only `.c4` files.** `tools/submit.py` stages and commits with the pathspec
  `:(glob)<model dir>/**/*.c4` (deletions included). Every other change under the model
  directory, a modified tracked `.snap` included, is not committed and is listed in the output
  as `skipped (not committed): <path>`, and in the `skipped` list of `POST /api/submit`. If only
  such files changed, Submit says "nothing to submit". The branch and refspec rules are
  unchanged.
- **The model editor writes no `.snap` file and does not show curated ones.** From source at
  `v1.59.4`: the playground's language server runs in the browser with `NoLikeC4ManualLayouts`
  (`packages/language-server/src/filesystem/noop.ts`), the client ignores
  `save-view-snapshot` and `reset-manual-layout` changes ("ignored in Playground"), and only
  `.c4` files are loaded into the page. The diagram there is always laid out automatically.
  `likec4 start` and `likec4 build` still use a curated `.snap` that is in the model directory.

## Consequences

- A person editing in the model editor cannot change a layout, and a curated layout does not
  appear in their preview. Layout changes stay in Flow A.
- A curated `.snap` can drift from the model it was drawn for (LikeC4 reports layout drift).
  Nobody in the model editor can repair it, so curated layouts need an owner in Flow A.
- Existing tracked `.snap` files are unaffected by the ignore rule. There are none in the
  repository today.
- `skipped` files are reported rather than deleted: the editor never removes the user's files.
- Showing curated layouts in the model editor would need the language server in the page to read
  them, which is a patch larger than this task allows. It is not done.
