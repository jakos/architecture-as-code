# LikeC4 compared with the Structurizr workflow

Status: draft research, 2026-10-10. For discussion; nothing here is decided or built.
Companion to [structurizr-workflows.md](structurizr-workflows.md); the proposed decision is
[ADR 0005](../decisions/0005-trial-likec4-for-the-editor-path.md) (proposed, not accepted).

How claims are labelled: **from docs** (with an `[Ln]` from [Sources](#sources)) or
**verified locally** (with the command run). Local probes used Podman 5.8.3, the images
`docker.io/likec4/likec4:latest` (LikeC4 1.59.4, pulled 2026-10-10) and
`docker.io/structurizr/structurizr:2026.09.19`, and models written in a scratch directory
outside the repo (a LikeC4 port of `examples/shop` and a copy of the DSL). Nothing in the
repo was written by them. "Structurizr" means the current B1 design: the pinned vNext image
plus code-server and a `submit` command (see the other doc, which numbers its sources
`S1`-`S24`).

## Summary

The tools are compared on three criteria, in this order: user-friendly for non-technical
users, free, and AI-friendly (people working on the model together with AI models such as
Claude Code).

- **User-friendliness first.** For a non-technical person, both tools are still text
  editing in a browser VS Code. LikeC4 is somewhat better at that one job: its VS Code
  extension has live preview, completion and diagnostics, it runs in the browser, and its
  dev server can move boxes (layout only) and keep the result in git. Structurizr `local`
  needs a refresh or the auto-refresh setting, and does not keep layout. This is from docs
  and unproven in code-server.
- **Free second.** A tie on licence. Both are open source (MIT for LikeC4, Apache-2.0 for
  the Structurizr vNext repo), both have a container image, and neither needs a paid licence
  for what we use. LikeC4 has no licensed `server` tier at all. LikeC4's image is more than
  three times larger (1.45 GB against 437 MB), which costs CI time, not money.
- **AI-friendliness third.** LikeC4 is ahead on tooling made for agents: `llms.txt` and
  `llms-full.txt` (HTTP 200; Structurizr 404), an installable agent skill, a model-querying
  MCP server, and a formatter with a check mode. Structurizr answers with its own free MCP
  server (validate, parse, inspect, export) and an `inspect` command, and its DSL is far
  more common in public code. Validation speed and error messages are a tie. Whether an
  AI produces better models in one tool is not measured; the one probe is anecdotal.
- **Trade-off.** LikeC4 is ahead, on paper, on criteria 1 and 3. The price is migration:
  every workspace rewritten, the validator, site export, compose file and CI replaced, and
  the dotted `kubernetes.*` property names given up (LikeC4 metadata keys cannot contain a
  dot, verified locally). Both tools have one main maintainer.
- **Recommendation: a time-boxed trial, not a switch.** Port `examples/shop` to LikeC4 in a
  separate directory, run the B1 editor with the LikeC4 extension for one or two real
  non-technical users, give an AI assistant the same edits in both tools, and decide with
  evidence. Until then Structurizr stays the tool of record. Proposed as
  [ADR 0005](../decisions/0005-trial-likec4-for-the-editor-path.md).

## Criteria

In this order. The earlier a criterion, the more it counts.

1. **User-friendliness for non-technical users**: open editor, edit, see the diagram,
   submit, get a PR link.
2. **Free, self-hosted, containerised**: no SaaS, no paid licence, runs in a container on
   our infrastructure.
3. **AI-friendliness**: how well people and AI models such as Claude Code can work on the
   model together. Judged on eight points:
   (a) docs made for LLMs (`llms.txt`, plain Markdown); (b) an MCP server or API for agents;
   (c) validation an agent can run, and how fast; (d) error messages an agent can act on
   (file, line, what is wrong); (e) a formatter or canonical form, to keep diffs from an AI
   quiet; (f) how well models already know the language; (g) reviewable diffs; (h) typed or
   programmatic access to the model.
4. **Technical user experience**: editor tooling, diagnostics, local loop.
5. **Browsing and publishing**: a static site we can host, plus exports.
6. **Fit with our model and tooling**: modelling fit for C4, CI validation, the
   `kubernetes.*` properties for the drift check (ADR 0003).
7. **Maturity and risk**: release cadence, maintainers, size of community.
8. **Migration cost**: what a switch would touch.

## Comparison

"Crit." is the number of the criterion the row belongs to. "Winner" is for that row only.
Structurizr cells repeat facts from [structurizr-workflows.md](structurizr-workflows.md)
and cite the same pages. Rows 15-22 are the AI-friendliness items (a)-(h).

| # | Crit. | Criterion | Structurizr (current B1 design) | LikeC4 | Winner |
| --- | --- | --- | --- | --- | --- |
| 1 | 2 | Licence and cost | `local`, `validate`, `export` are free; prebuilt `server` needs a paid licence from about £300/month [L20][L22]. Vendor repo is Apache-2.0 (**verified locally**: `python j.py https://api.github.com/repos/structurizr/structurizr "d['license']['spdx_id']"` printed `Apache-2.0`; `j.py` is a throwaway urllib helper in the scratch dir that prints one JSON field, not part of the repo) | MIT, CLI, VS Code extension, playground source and Docker image all free [L1][L2][L16]. **Verified locally**: `curl -s https://raw.githubusercontent.com/likec4/likec4/main/LICENSE` begins "MIT License". The "For Teams" page is voluntary sponsorship (Backer, Team, Enterprise support tiers) and states the core stays MIT [L23]; nothing found that gates a feature behind payment | Tie (LikeC4 has no licensed server to avoid) |
| 2 | 2 | Container image | `docker.io/structurizr/structurizr`, modes local / validate / export / playground [L20] (ADR 0001). **Verified locally**: `podman images --format '{{.Repository}}:{{.Tag}} {{.Size}}'` printed `docker.io/structurizr/structurizr:2026.09.19 437 MB` | `likec4/likec4` on Docker Hub and `ghcr.io/likec4/likec4`; bundles Node 22, Graphviz, Playwright; mount sources at `/data` [L4]. **Verified locally**: `podman pull docker.io/likec4/likec4:latest` worked; the same `podman images` command printed `docker.io/likec4/likec4:latest 1.45 GB`. Docker Hub last updated 2026-09-21 [L13]. The npm package requires Node >= 22.22.3 [L14] | Structurizr (much smaller; LikeC4 bundles a browser) |
| 3 | 1 | Non-technical editing experience | Text DSL in code-server; DSL highlighting from a community Open VSX extension (0.0.9) [L21]. No completion or diagnostics claimed there | Same text editing, but the official extension gives validation, completion, go-to-definition, hover and "safe" renames [L5]; it is on Open VSX (1.59.4, MIT, **verified locally**: `python j.py https://open-vsx.org/api/likec4/likec4-vscode "(d['version'],d['license'])"`) so code-server can install it. The docs say the extension "can run in the browser" (github.dev, vscode.dev) [L5]. **Not verified**: the extension's preview panel inside code-server | LikeC4 (on docs; unproven in code-server) |
| 4 | 1 | Live preview | `structurizr local` in a second tab; refresh, or `STRUCTURIZR_AUTOREFRESHINTERVAL` [L20] | `likec4 start` dev server hot-updates on every source change [L3]; the extension also has live preview [L5]. **Verified locally**: `podman run -d --rm -v <probe>:/data -p 15173:5173 docker.io/likec4/likec4:latest start`, then from inside the container `fetch('http://127.0.0.1:5173/')` returned 200 and the page HTML. A host-side `curl http://localhost:15173/` returned no response in this probe (published port `0.0.0.0:15173` per `podman port`), cause not found, so I could not check hot reload from the host | LikeC4 (on docs) |
| 5 | 1 | Path to PR | Our `submit`: validate, commit, push `model/*`, `gh pr create` (ADR 0002, not built) | The same `submit` pattern applies: LikeC4 reads and writes plain files in a clone, so no part of it needs to change except the validate command. No built-in PR feature found in the docs [L3][L5] | Tie |
| 6 | 1 | Visual editing | Dragging boxes in `local` writes `workspace.json`, which is gitignored; not kept unless force-added (ADR 0002). No element or text editing in `local` [L20] | Dev server "edit mode" lets you adjust view layouts in the browser with undo [L12]; layouts persist as `<view-id>.likec4.snap` files in `.likec4/` which can be committed [L12]. Elements, relationships and text are still edited as source; the docs call manual layout in the extension "limited" [L8]. `likec4 validate` flags "layout drift" (outdated manual layout) [L3] | LikeC4 (layout only) |
| 7 | 4 | Technical user tooling | `structurizr validate`, `structurizr inspect`, `just up`, community VS Code extension [L21] | Language server, official VS Code extension, standalone LSP for Neovim, Emacs, Zed, JetBrains [L5], `likec4 format` with `--check` [L3]. Agent-specific tooling is in rows 15-16 and 19 | LikeC4 |
| 8 | 5 | Static site / browsing | `export -f static` per workspace (ADR 0004) | `likec4 build -o dist` makes a static site; `--base` for sub-paths; `--output-single-file` for one HTML file [L3][L9]. **Verified locally**: `podman run --rm -v <probe>:/data docker.io/likec4/likec4:latest build -o /data/dist` exited 0 and produced `index.html`, `assets/`, `likec4-views.js`. Deploy guide for GitHub Pages exists [L10]. Other exports: JSON, PNG/JPEG, Mermaid, Dot, D2, PlantUML, DrawIO [L3][L19] | Tie |
| 9 | 6 | CI validation | `structurizr validate` over all `workspace.dsl` (`tools/validate_workspaces.py`) | `likec4 validate` checks syntax and layout drift and exits non-zero on errors [L3]. **Verified locally**: a file with an error exited 1 (`podman run --rm -v <bad>:/data docker.io/likec4/likec4:latest validate; echo $?` printed 1); the fixed file exited 0 and printed "Valid (1 files)". Custom rules via Vitest and the model API [L11] | Tie |
| 10 | 6 | Element properties for `kubernetes.*` | Free-form `properties { "kubernetes.name" "x" }` with dotted keys; the contract in `docs/conventions.md` | `metadata { key 'value' }` with string, array or boolean values [L6]; deployment nodes and instances can carry metadata [L7]. **Verified locally**: a key written `kubernetes.name` failed `validate` with "Expecting: one of these possible Token sequences" at that line; after renaming the keys to `kubernetes_name` the file validated, and `likec4 export json` showed `{'kubernetes_kind': 'Deployment', 'kubernetes_name': 'shop-api'}` on the deployed instance. So the data is carried but the property names must change | Structurizr (no rename needed) |
| 11 | 6 | Modelling fit | Fixed C4 kinds and levels, with the hierarchy and the rules of each diagram type enforced; deployment model with container instances. Our summary of the DSL docs; the vendor states the same and says LikeC4 needs a "specification" to avoid wrong levels [L24] | Own language "inspired by C4 and Structurizr DSL" with user-defined element kinds and any nesting depth [L2]; deployment model with `instanceOf` [L7]; multi-project workspaces via `likec4.config.json` [L18] | Tie (LikeC4 more flexible, Structurizr closer to plain C4) |
| 12 | 8 | Migration from Structurizr DSL | n/a | No importer or converter for Structurizr DSL found: `curl -sL https://likec4.dev/llms-full.txt \| grep -ni structurizr` matches only a syntax comparison; a GitHub issue search for `structurizr import` in the likec4 repo returned no results. So `examples/` would be rewritten by hand | Structurizr |
| 13 | 7 | Maturity | Repo `structurizr/structurizr` created 2025-11-30, 449 stars, latest release `v2026.09.19` (2026-09-19), one contributor listed (468 contributions) (**verified locally** with the `j.py` helper on `repos/structurizr/structurizr`, `/releases`, `/contributors`). Older history of the DSL tool was not measured here | Repo created 2023-03-24, 5841 stars, 62 contributors, releases 1.59.0 (2026-07-19) to 1.59.4 (2026-09-21) (**verified locally**: same helper on `repos/likec4/likec4`, `/releases`, `/contributors`). One person (`davydkov`) has 4151 of the contributions; the next human has 202 (`/contributors?per_page=5`) [L15] | Tie (both depend on one main maintainer; LikeC4 has the larger community) |
| 14 | 8 | Migration cost | None | See [Migration cost](#migration-cost): every workspace, the validator, the site export, compose, CI and docs | Structurizr |
| 15 | 3a | LLM-oriented docs | `llms.txt` and `llms-full.txt` are missing. **Verified locally**: `curl -sL -o /dev/null -w "%{http_code}" https://docs.structurizr.com/llms.txt` printed 404, `.../llms-full.txt` printed 404. There is an "AI + MCP" docs section [L24], and the docs source is Markdown in a public repo [L25] | **Verified locally**: `curl -sL -o /dev/null -w "%{http_code}" https://likec4.dev/llms.txt` printed 200 (an index of doc pages) and `https://likec4.dev/llms-full.txt` printed 200 (323,679 bytes, all docs in one Markdown file). The docs also offer an installable agent skill, `npx skills add https://likec4.dev/` (not run here) [L26] | LikeC4 |
| 16 | 3b | MCP server or agent tooling | Official, free, open-source MCP server (Apache-2.0 repo, `structurizr-mcp`), runs standalone with stateless HTTP; README calls it "experimental" [L27][L28]. Its model tools take DSL text as a parameter: `validate` ("OK" or the error), `parse` (JSON workspace), `inspect` (violations), export to Mermaid, PlantUML, C4-PlantUML; separate profiles talk to a Structurizr server (create, read, update, delete) [L27]. Image `structurizr/mcp` on Docker Hub, last updated 2026-04-20 (**verified locally**: `curl -sL https://hub.docker.com/v2/repositories/structurizr/mcp/tags`). Search used: docs.structurizr.com/ai, the repo tree via `gh api repos/structurizr/structurizr/contents`, and `gh search repos structurizr mcp` (several community servers, all under 50 stars). Not run here | `likec4 mcp` (stdio, or `--http`; also `@likec4/mcp` on npm, and built into the VS Code extension) [L26]. **Verified locally**: `podman run --rm docker.io/likec4/likec4:latest --help` lists `likec4 mcp [path]  Start MCP server`. Query tools over the model on disk: list projects, search and read elements, deployments and views, relationships and paths, tag and metadata queries, element diff, and `preview-view` from DSL text without saving [L26]. Free (MIT) and local. Not run here; capabilities are from docs | LikeC4 (reads the model on disk; Structurizr adds `inspect`) |
| 17 | 3c | Validation an agent can run, and its time | `validate -w <file>` exits 1 on error. **Verified locally**: `podman run --rm -v <dir>:/repo docker.io/structurizr/structurizr:2026.09.19 validate -w /repo/workspace.dsl` on a copy of `examples/shop`, three timed runs (wall clock, warm image): 2702, 2653, 2427 ms. Also `inspect -w` lists quality violations (missing descriptions, disconnected elements) | `likec4 validate` exits 1 on error. **Verified locally**: `podman run --rm -v <dir>:/data docker.io/likec4/likec4:latest validate` on an equivalent `.c4` port of `examples/shop` (2.2 KB against 3.8 KB, the port has no styles), three timed runs: 1889, 1789, 1856 ms. Both include container start-up: `podman run --rm docker.io/library/nginx:alpine true` took 597 ms (one run). Times are from this machine, not a benchmark | Tie (LikeC4 about 0.8 s faster; not decisive for an edit loop) |
| 18 | 3d | Error messages | **Verified locally**, same two mistakes in a copy of `examples/shop`. Unknown identifier: `ERROR com.structurizr.command.ValidateCommand -- The destination element "paymnts" does not exist at line 23 of /repo/workspace.dsl: shop.api -> paymnts "Charges cards via" "HTTPS"`. Missing `}`: `Unexpected tokens (expected: !docs, !decisions, group, container, description, tags, url, properties, perspectives, ->) at line 16 of /repo/workspace.dsl: payments = softwareSystem ...` (the next statement, not the missing brace). Line is 1-based and the source line is quoted; no column; stops at the first error | **Verified locally**, same two mistakes in the `.c4` port. Unknown identifier: `Line 27: Could not resolve reference to Referenceable named 'paymnts'.` and `Line 27: Target not resolved`. Missing `}`: `Line 29: Expecting: one of these possible Token sequences: 1. [extend] 2. [Dot] ...` and ``Line 29: Expecting token of type '}' but found `deployment`.`` The file line was 28 and 30, so the numbers are 0-based; no column; reports all errors in the file in one run, and ends with `Invalid (1 files, 2 errors)` | Tie (Structurizr: right line and quoted source; LikeC4: all errors at once, but off-by-one lines) |
| 19 | 3e | Formatter / canonical form | No DSL formatter in the docs or the CLI: `podman run --rm docker.io/structurizr/structurizr:2026.09.19 help` lists `playground\|local\|server\|push\|pull\|lock\|unlock\|branches\|create\|delete\|regenerate-apikey\|export\|generate\|merge\|validate\|inspect\|list\|version\|help`. `gh search repos "structurizr dsl formatter"` found one repository with 0 stars. So an AI's whitespace and ordering choices show up in the diff unless a reviewer or a prompt rule stops them | `likec4 format` rewrites files; `--check` exits non-zero when a file needs formatting [L3]. **Verified locally**: after changing `customer -> shop.web` to `customer   ->   shop.web` with extra indent, `format --check` printed `1 of 1 file(s) need formatting` and exited 1; `format` restored `  customer -> shop.web ...`. So CI or `submit` can enforce one canonical form | LikeC4 |
| 20 | 3f | How well models know the language | **Anecdotal, biased, not a benchmark**: the writer is an AI model that had met both languages earlier in this task. From a prose description (three containers, two relationships, one deployment node with a `kubernetes.namespace` property) the Structurizr model was written without docs. First attempt: 1 error (`The container "shop.api" does not exist`, because `!identifiers hierarchical` was missing so `shop.api` was not a valid reference). Public usage proxy, **verified locally** with `gh api "search/code?q=softwareSystem+extension:dsl&per_page=1" --jq .total_count`: 3664 code files; `gh api "search/repositories?q=topic:structurizr&per_page=1" --jq .total_count`: 96 repositories | Same description, same writer. First attempt: 2 errors in two places: the dotted metadata key `kubernetes.namespace` (not allowed) and `autolayout` instead of `autoLayout` (LikeC4 reported ``Expecting token of type '}' but found `autolayout`.``). Public usage proxy: `specification+extension:c4`: 750 files and `specification+extension:likec4`: 124 files (the `.c4` extension is also used by other tools, so the first number is rough); `topic:likec4`: 20 repositories | Structurizr (weak evidence: one probe, plus more public text to learn from) |
| 21 | 3g | Diff reviewability | Plain-text DSL. The layout file `workspace.json` is gitignored, so with `autolayout` the diff holds only DSL lines (ADR 0002). Styles live in the same file, so a style change shares a diff with a model change | Plain-text `.c4`. Manual layouts, if committed, are generated `.likec4/*.likec4.snap` files [L12], so they add machine-written lines to a PR diff; with auto-layout only there are none. The docs list a guide "Preview changes in PR" [L26], but its page is empty in `llms-full.txt` and `curl -sL -o /dev/null -w "%{http_code}" https://likec4.dev/guides/preview-changes-in-pr` printed 404 (**verified locally**), so no PR-preview feature is documented | Tie |
| 22 | 3h | Typed or programmatic access | `structurizr export -f json`. **Verified locally**: `podman run --rm -v <dir>:/repo docker.io/structurizr/structurizr:2026.09.19 export -w /repo/workspace.dsl -f json -o /repo/out` wrote `workspace.json` (16,435 bytes, 406 lines, keys `model`, `views`, `properties`, ...). Java library and community libraries for other languages [L21] | `likec4 export json`. **Verified locally**: `podman run --rm -v <dir>:/data docker.io/likec4/likec4:latest export json -o /data/model.json` wrote 16,677 bytes on one line (keys `elements`, `relations`, `deployments`, `views`, ...). A TypeScript model API and typed code generation for tests and tools [L11][L26] | Tie (our Python tools read JSON from either; LikeC4 adds a typed TypeScript API) |

Count by row, LikeC4 wins rows 3, 4, 6, 7, 15, 16 and 19; Structurizr wins rows 2, 10, 12,
14 and 20 (row 20 on weak evidence); the rest tie. By criterion: LikeC4 is ahead on 1 (rows
3, 4, 6) and on 3 (rows 15, 16, 19 against row 20, with four ties); criterion 2 is a tie on
licence and Structurizr wins on image size; Structurizr wins on fit (row 10) and migration
(rows 12, 14).

## Non-technical user flow with LikeC4

This is [Flow B1](../workflow.md) with LikeC4 in place of Structurizr `local`. It is
free, on-prem and container-based, and the text model in git stays the single source of
truth.

Journey:

1. The person opens a link and logs in (code-server password, or SSO in front of it).
2. The container starts with a fresh clone of `main` on a new branch
   `model/<user>/<date>-<slug>`. They see code-server with the model files and the LikeC4
   preview next to them (extension preview, or the dev server in a second tab).
3. They edit the `.c4` text. The preview updates without a refresh [L3][L5]. They can
   nudge boxes in the dev server's layout editor [L12].
4. They run `submit`: `likec4 validate` (and `likec4 format --check`), commit including
   any `.likec4/*.snap` layout files, push the `model/*` branch, `gh pr create`.
   Validation failure stops the submit.
5. They get the PR link. A reviewer takes over in GitHub; CI runs the check job.

Container architecture, with what is reused from B1:

| Part | Same as B1 | Differs with LikeC4 |
| --- | --- | --- |
| One container per session, fresh clone of `main` | Yes | n/a |
| Branch `model/<user>/<date>-<slug>`, git identity of the user | Yes | n/a |
| code-server (MIT) with extensions from Open VSX | Yes | Installs the `likec4.likec4-vscode` extension [L16] instead of the DSL highlighter |
| Renderer | n/a | `likec4 start` (dev server, port 5173 inside the container) from the `likec4/likec4` image [L4], or the extension's own preview. **Not run together with code-server here.** The image would need code-server added (a custom image), because `likec4/likec4` is a CLI image |
| `submit` | Yes: validate, commit, push, `gh pr create` | Calls `likec4 validate` and `likec4 format --check` instead of `structurizr validate` [L3] |
| Refusal to push `main` | Yes: `submit` creates the branch, refuses on `main`, pushes only to `model/*` | n/a |
| Branch protection on `main` (required PR and checks) | Yes: this is the enforcement layer; the token has no bypass | n/a |
| Token handling | Yes: fine-grained token or GitHub App token from an env var, never in the image or repo | n/a |
| Auth for the dev server | Structurizr `local` is documented as localhost-only [L20] | Not documented for `likec4 start` [L3][L4]. **Verified locally** only that a request from inside the container with `Host: editor.example.com` returned 200 (`podman exec ... node -e "fetch(...)"`). So keep it behind the editor's proxy on the container loopback, as in B1 |

The public LikeC4 playground is described as a Cloudflare Worker and its README has no
self-hosting instructions [L17], so it is not part of this flow (the same conclusion as
for the Structurizr `playground`).

What the person still cannot do without text editing: add an element, a relationship or
a description. LikeC4's visual editing covers layout only [L12]. So the audience question
in the other doc (is a text editor too hard?) is not removed by LikeC4; it is reduced by
completion and live preview, which only a trial can measure. Drawing tools do not close
the gap either: LikeC4 can export views to draw.io, but the CLI has no import of edited
drawings back into the model (see the dropped draw.io line in the other doc).

## Working with AI models

This section applies the third criterion. It describes what each tool gives an AI
assistant such as Claude Code, for a technical and a non-technical user. Nothing here is
built; which assistant the users get is an open question (see
[Open questions](#open-questions-for-the-owner)).

**Technical user (Flow A, a clone on a `model/*` branch).** The assistant edits the text
file, runs the validator, reads the first errors, fixes them and repeats; the human reviews
the diff and opens the PR.

- Structurizr: edit `workspace.dsl`, a bare `podman run` validate (about 2.6 s here,
  row 17), read one error at a time with a right line number and the quoted source line
  (row 18), run `structurizr inspect` for missing descriptions and disconnected elements
  (row 17). The free MCP server can validate, parse and inspect DSL text and export views
  (row 16). There is no formatter, so style rules must be in the prompt or in `CLAUDE.md`
  (row 19).
- LikeC4: edit `.c4`, `likec4 validate` (about 1.8 s, row 17) and `likec4 format --check`
  (row 19), read all errors in one run with 0-based lines (row 18). The assistant can load
  the LikeC4 syntax from `llms-full.txt` or the agent skill (row 15), and query the existing
  model through `likec4 mcp` instead of reading every file (row 16).

**Non-technical user (Flow B1, a code-server session).** The assistant would run beside the
editor in the same container: the person describes a change in plain words ("add a billing
service that the API calls"), the assistant edits the text, runs the validator, fixes
errors, and the person checks the preview and runs `submit`. The tool gaps above matter more
here, because the person cannot fix a syntax error themselves. LikeC4's all-errors-at-once
output and formatter help the assistant converge; Structurizr's models are better known to
AI models (row 20, anecdotal). Neither claim is measured with real users.

What the assistant may and may not do, under the non-negotiables:

- It works only in the clone, on the session's `model/*` branch. Changes reach `main` only
  through the PR from `submit`; `submit` refuses `main` and branch protection enforces it.
- It never receives or writes a token. Tokens are env vars of the container, outside the
  model files, the compose file and the image (non-negotiable 3); the assistant must not
  print them or write them into any file.
- It has no cluster or cloud access: no `kubectl`, no cloud credentials in the container
  (non-negotiable 1). The `kubernetes.*` data in the model is text only.
- MCP servers in the container are read-only on the model. For LikeC4, the documented tools
  are query tools plus view previews [L26]. For Structurizr, enable only the DSL, Mermaid
  and PlantUML profiles; the server-create, -update and -delete profiles act on a Structurizr
  server and are not needed [L27].
- A human reviews every PR. An AI-written change is not merged without that review.

**Friendlier for AI work: LikeC4, by a modest margin.** It wins rows 15, 16 and 19
(LLM docs, a model-querying MCP server, a formatter); rows 17, 18, 21 and 22 tie; and
Structurizr wins row 20 on weak evidence. The vendor of Structurizr argues the other way,
that its model-based DSL and MCP server make it the best choice for AI-generated C4 [L24];
that is a claim, not a measurement, and the page compares tools by feature, not by results.
The one number that would settle it is how many edits an assistant gets right on the
first try in each tool; the trial in the Recommendation is where to measure that.

## Migration cost

Nothing is migrated in this task. This lists what a switch would touch. Effort is our
rough estimate, not measured.

| Path | What changes | Effort |
| --- | --- | --- |
| `examples/` | Rewrite `examples/shop/workspace.dsl` (and any other example) as `.c4`; no importer, see row 12 | Small for one example; grows with real workspaces |
| `tools/validate_workspaces.py` | Pinned Structurizr image and `workspace.dsl` discovery replaced by `likec4 validate` per project and a pinned `likec4/likec4` tag; its tests change too | Medium |
| `tools/export_site.py` | Calls `structurizr export -f static` per workspace; would call `likec4 build` per project (or one multi-project build [L18]) | Medium |
| `tools/tests/` | `test_validate_workspaces.py` and `test_export_site.py` check `workspace.dsl` discovery and the `-w /repo/.../workspace.dsl` argument (`test_validate_workspaces.py`) and site naming from a `workspace.dsl` path (`test_export_site.py`); both are rewritten with the tools | Small |
| `docker/compose.yml` | `local` and static-site services replaced by `likec4 start` and a static preview; Windows file watching needs `CHOKIDAR_USEPOLLING` [L4] | Small |
| `justfile` | Recipes `check`, `validate`, `up`, `site`, `down` call new commands | Small |
| `prek.toml` | Hook `structurizr-validate` (`entry = "uv run --locked python tools/validate_workspaces.py"`, `files = '\.dsl$'`) must match `.c4` files instead, and could add `likec4 format --check` | Small |
| `.gitignore` | The `**/.structurizr/` and `workspace.json` rules go; LikeC4 build output (`dist/`) needs a rule, and committed `.likec4/*.snap` layouts must not be ignored | Small |
| `README.md` | The quick start says `just up` "renders examples/shop live" and the intro says "Structurizr DSL" | Small |
| `.github/workflows/check.yml` | Runs `just check`, so mostly follows the `justfile`; image pull and caching change (1.45 GB image) | Small |
| `docs/conventions.md` | The `kubernetes.*` table: dotted names must become another convention such as `kubernetes_name` (non-negotiable 4: tooling and every workspace change in the same PR). The "one workspace per directory because `local` serves a directory" rule goes away | Small, but it is a contract change |
| `CLAUDE.md` | Constraints, commands, conventions and layout all state Structurizr facts; they would be rewritten | Small |
| `docs/workflow.md`, `docs/decisions/` | Flow wording; ADRs 0001 and 0004 superseded, 0002 and 0003 amended (see [ADR impact](#adr-impact)) | Small |
| Drift check (not built) | Would read LikeC4 metadata (for example from `likec4 export json`) instead of Structurizr properties | None until built |

`CLAUDE.md` says real workspaces will live in `workspaces/`. That directory does not exist
yet, so today only `examples/` would be ported. A switch before real workspaces exist is
the cheapest it will ever be.

## Recommendation

**Run a time-boxed trial of LikeC4 for the editor path, with an AI-assisted task in it;
keep Structurizr as the tool of record until the trial has a result.**

By the criteria, in order:

1. **User-friendliness.** LikeC4 is better on paper: completion, diagnostics, live
   preview, and layout editing that survives in git (rows 3, 4, 6). But the person is still
   typing a modelling language, so the gain is unmeasured. That is exactly what a trial can
   answer, and nothing in the docs does.
2. **Free.** Both qualify (row 1), so this criterion does not decide. LikeC4's larger image
   (row 2) is a cost in CI time and disk, not in money.
3. **AI-friendliness.** LikeC4 is ahead on agent tooling (rows 15, 16, 19) and the rest is
   a tie, except that models know Structurizr's DSL better (row 20, anecdotal). The
   advantage is real but moderate: Structurizr already has an MCP server, `inspect` and
   validation an assistant can use today.
4. **Everything else** (`kubernetes.*` rename, no importer, migration across the whole
   repo) points to staying until criteria 1 and 3 show a clear gain.

The trial: port `examples/shop` to a `.c4` model in a separate directory, build the
code-server image with the LikeC4 extension, and let one or two intended users make three
real edits (add a container, add a relationship, change a description). Compare against the
Structurizr B1 setup on time to a valid PR and number of times they ask for help. Repeat the
same three edits with an AI assistant doing the typing in each tool, and count validation
errors before the first clean pass. The B1 PR path (`submit`, `model/*`, branch protection)
is the same for both, so the trial costs the editor image plus a rewritten example.

What would change the answer, including the trade-offs between the three criteria:

- LikeC4 wins on criteria 1 and 3 on paper but costs a migration and the `kubernetes.*`
  rename. If users manage the edits in LikeC4 clearly faster or more independently, or the
  assistant converges in fewer rounds, switch (a new ADR would supersede 0001 and 0004 and
  amend 0002 and 0003). Because `workspaces/` is still empty, the owner may reasonably
  weigh criteria 1 and 3 above the migration cost and switch now; the trial is the cheaper
  way to check the first.
- If AI-friendliness mattered most, Structurizr plus its MCP server, `inspect` and a
  rule file in `CLAUDE.md` closes part of the gap without a migration (no formatter, row 19).
  This is the option that favours criterion 3 over the migration cost without choosing
  LikeC4.
- The extension preview does not work in code-server, or the dev server cannot be put
  behind our proxy safely: stay with Structurizr (criterion 1 gain disappears).
- The owner decides a visual editor for elements is needed: neither tool provides one
  (row 6); revisit candidates 5 and 6 in the other doc.
- Real workspaces turn out to need Structurizr-only features, or the `kubernetes.*` rename
  is unacceptable to the drift-check design: stay.

Protections in the recommended flow: the text model in git stays the single source of
truth, changes arrive only as a PR on a `model/*` branch, `submit` refuses `main`, and
branch protection enforces it. No SaaS and no paid licence is involved.

## ADR impact

Accepted ADRs are not edited. The trial conflicts with two of them in wording: ADR 0001,
because it says one Structurizr image covers validation, local authoring and static-site
export, and ADR 0002, because it says every model change is a change to `.dsl` files and
the B1 wrapper is Structurizr `local`. Proposed ADR 0005 amends both for the trial only. If
the trial later succeeds and the owner wants a switch, a new ADR would be written then; it
is not written now.

| ADR | Accepted decision | Conflict with the recommendation | Proposed action |
| --- | --- | --- | --- |
| 0001 | One Structurizr vNext image, pinned `2026.09.19`, "for validation, local authoring and static-site export"; legacy images not used | Yes, in one sentence. The trial validates and authors the trial directory with a second image (`likec4/likec4`), so "one image for validation, local authoring and export" is no longer true for that directory. It stays true for every real workspace. No legacy Structurizr image comes back. If LikeC4 is adopted later, this ADR is superseded | amended by 0005 (proposed) |
| 0002 | Every model change is a change to `.dsl` files; DSL in git is the source of truth; B1 editor is a git clone + Structurizr `local` + submit | Yes, in two sentences: trial model files are `.c4`, not `.dsl`, and the B1 wrapper uses the LikeC4 renderer and validator. The principle (text in git, PR only) is kept | amended by 0005 (proposed) |
| 0003 | Read-only drift check using our `kubernetes.*` properties | No during the trial; the check is not built, and the trial model is not read by it. A full switch would need a renamed contract | unchanged |
| 0004 | Static `export -f static` site instead of the licensed `server` | No. The trial does not publish; `likec4 build` would also be a free static site (row 8) | unchanged |

Proposed file: [0005-trial-likec4-for-the-editor-path.md](../decisions/0005-trial-likec4-for-the-editor-path.md).

## Open questions for the owner

1. Do you accept a trial (one or two real users, one example ported) before deciding on
   the tool? Who are the users, and what edits must they be able to make?
2. How would you judge the trial: time to a valid PR, number of help requests, the
   user's own preference, or validation errors an AI assistant makes before a clean pass?
3. If LikeC4 wins, is renaming the `kubernetes.*` properties (for example to
   `kubernetes_name`) acceptable for the drift-check contract, given non-negotiable 4?
4. Is a 1.45 GB tool image acceptable for CI and the editor container, or do we need a
   slimmer custom image with Node and `likec4` only?
5. Is a single main maintainer acceptable risk for LikeC4, as it already is for
   Structurizr (see row 13)?
6. Should LikeC4 manual layouts (`.likec4/*.snap`) be committed, or should we rely on
   automatic layout only, as we do with `autolayout` today?
7. Which AI assistant do the users get (Claude Code in the editor container, or another),
   and who pays for and approves that? Is sending model text to an external AI service
   acceptable for the real workspaces?
8. May an MCP server run in the editor container (LikeC4 `likec4 mcp`, or the Structurizr
   MCP image), and may the assistant's changes be limited to what `submit` pushes?

## Sources

- L1 https://likec4.dev/ (home page: MIT, features, MCP, playground link)
- L2 https://raw.githubusercontent.com/likec4/likec4/main/README.md (what LikeC4 is; MIT)
- L3 https://likec4.dev/tooling/cli/ (serve, build, export, validate, format, LSP)
- L4 https://likec4.dev/tooling/docker/ (image names, contents, `/data`, ports, Windows polling)
- L5 https://likec4.dev/tooling/editors/ (VS Code extension features, browser use, other editors)
- L6 https://likec4.dev/dsl/model/ (element metadata, value types)
- L7 https://likec4.dev/dsl/deployment/model/ (deployment nodes, `instanceOf`, properties)
- L8 https://likec4.dev/dsl/views/ (auto-layout; manual changes limited in the extension)
- L9 https://likec4.dev/guides/static-website/ (build options)
- L10 https://likec4.dev/guides/deploy-github-pages/ (Pages workflow)
- L11 https://likec4.dev/guides/validate-your-model/ (custom rules with Vitest)
- L12 https://raw.githubusercontent.com/likec4/likec4/main/CHANGELOG.md (dev server edit mode,
  1.46.1; manual layouts saved as `.likec4/<view-id>.likec4.snap`)
- L13 https://hub.docker.com/v2/repositories/likec4/likec4/ (pull count, last updated, tags)
- L14 https://registry.npmjs.org/likec4/latest (version 1.59.4, MIT, Node >= 22.22.3)
- L15 https://api.github.com/repos/likec4/likec4 and `/releases` and `/contributors`
  (stars, dates, contributors)
- L16 https://open-vsx.org/api/likec4/likec4-vscode (extension on Open VSX)
- L17 https://raw.githubusercontent.com/likec4/likec4/main/apps/playground/README.md (the public
  playground is a Cloudflare Worker; no self-hosting instructions; not used here)
- L18 https://likec4.dev/dsl/config/multi-projects/ (multiple projects, `likec4.config.json`)
- L19 https://likec4.dev/tooling/drawio/ (DrawIO export and round-trip)
- L20 https://docs.structurizr.com/local and https://docs.structurizr.com/local/configuration
  (same as S2 in the other doc)
- L21 https://docs.structurizr.com/community (same as S3 in the other doc)
- L22 https://docs.structurizr.com/server/pricing (same as S4 in the other doc)
- L23 https://likec4.dev/sponsor ("For Teams": voluntary sponsorship tiers, core stays MIT)
- L24 https://docs.structurizr.com/ai (Structurizr's own AI page: why it recommends
  Structurizr for AI workflows, comparison with LikeC4; a vendor view)
- L25 https://github.com/structurizr/structurizr.github.io (source of docs.structurizr.com;
  Markdown pages, for example `ai/mcp.md`)
- L26 https://likec4.dev/llms-full.txt (the "AI Tools" section: agent skill, MCP server and
  its tools; also the empty "Preview changes in PR" heading) and https://likec4.dev/llms.txt
- L27 https://raw.githubusercontent.com/structurizr/structurizr.github.io/main/ai/mcp.md
  (Structurizr MCP server: tools and profiles; the rendered page
  https://docs.structurizr.com/ai/mcp returned HTTP 200 with an empty body in three tries)
- L28 https://github.com/structurizr/structurizr/tree/main/structurizr-mcp (the MCP server
  source and README, "An experimental MCP server")
- Repo: `docs/workflow.md`, `docs/conventions.md`, `docs/decisions/0001` to `0004`,
  `tools/validate_workspaces.py`, `tools/export_site.py`, `docker/compose.yml`, `justfile`,
  `prek.toml`, `.gitignore`, `.github/workflows/check.yml`, `examples/shop/workspace.dsl`,
  `CLAUDE.md`
