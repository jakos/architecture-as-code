# Structurizr workflows: technical flow, browser editor, lifecycle

Status: draft research, 2026-10-10. For discussion; nothing here is decided or built unless
marked ✅. ✅ = exists in the repo at this commit, ⏳ = planned.

How claims are labelled: **from docs** (with a URL from [Sources](#sources)) or
**verified locally** (with the command run). Local probes used the pinned image
`docker.io/structurizr/structurizr:2026.09.19` with Podman 5.8.3 and a copy of
`examples/shop` in a scratch directory; nothing in the repo was written by them.

## Summary

- **Technical users** edit `workspace.dsl` on a branch and use `just up` / `just check`, then
  open a PR. Everything in that flow already exists except publishing on merge (⏳).
- **Non-technical users**: recommend the Flow B1 design from `docs/workflow.md`, one
  ephemeral container per editing session: git clone on a `model/*` branch +
  code-server (MIT) + `structurizr local` + a `submit` command (validate, commit, push,
  `gh pr create`). It is the only candidate that is free, on-prem, containerised, keeps
  the DSL in git and produces a PR. Cost: a VS Code-style text editor is still a text editor.
- **`playground` cannot replace code-server.** It has no way to open or save a file on
  disk or in a git clone (verified locally and from docs). It is useful only as a scratch pad.
- A **visual editor** would be a nicer experience for non-technical users. The only
  free candidate found, c4hero, is a browser app with no git or PR support and its own DSL
  parser, so it is a later option, not the first step.
- **LikeC4** (candidate row 7) is the one alternative examined in depth. It is somewhat
  friendlier for the editing loop (criterion 1) and ahead on tooling for AI assistants
  (criterion 3: `llms.txt`, an MCP server, a formatter), and a tie on being free
  (criterion 2). It needs a rewrite of every workspace and a rename of `kubernetes.*`.
  Outcome: trial, not a switch; the B1 recommendation below is unchanged. The comparison
  now weighs user-friendliness, then free, then AI-friendliness. See
  [likec4-comparison.md](likec4-comparison.md) and proposed
  [ADR 0005](../decisions/0005-trial-likec4-for-the-editor-path.md).
- **Lifecycle**: short-lived `model/*` branches, draft PRs for work in progress, `main`
  protected, `just check` as the only CI gate, squash merge, static site published on merge (⏳).
  Details and the decisions needed from the owner are below.

## Technical user flow

For someone comfortable with git and an editor. Steps, in order:

1. Update and branch: `git switch main && git pull && git switch -c model/<user>/<date>-<slug>`
   ✅ (plain git; the branch scheme is proposed under [Lifecycle](#lifecycle)).
2. First time only: `uv sync` and `uv run prek install` ✅ (README quick start). This installs
   the pre-commit and pre-push hooks from `prek.toml`.
3. Start live rendering: `WORKSPACE=examples/shop just up` ✅, open http://localhost:8080
   (`WORKSPACE` defaults to `examples/shop`; use the directory of your workspace).
4. Edit `workspace.dsl` in any editor and refresh the browser to see the result ✅
   (**from docs**: refresh shows changes; `STRUCTURIZR_AUTOREFRESHINTERVAL` can make it
   automatic, https://docs.structurizr.com/local/configuration).

   ⏳ Optional: set the auto-refresh env var in `docker/compose.yml` for a split-screen loop.
5. Layout: prefer `autolayout` in the DSL. `local` rewrites `workspace.json` on every load
   and it is gitignored, so dragging boxes in the browser is not kept. To keep a
   hand-made layout, commit it deliberately with `git add -f <dir>/workspace.json` ✅
   (ADR 0002, `.gitignore`).
6. Validate: `just validate` ✅ (DSL only) or `just check` ✅ (ruff, pytest, DSL for all workspaces).
7. Commit. The pre-push hook runs pytest and `structurizr validate` on all workspaces
   when `.dsl` files changed ✅ (`prek.toml`). Push the branch and open a PR
   (`gh pr create`, or the web UI). Use `--draft` if it is not ready for review.
8. CI runs `just check` on the PR ✅ (`.github/workflows/check.yml`). A reviewer approves.
9. Merge to `main`. ⏳ A CI job then publishes the static site (today: `just site` locally ✅).

Options, not built and not required:

- ⏳ VS Code extension for DSL highlighting and diagram preview. Candidates are listed in
  the Structurizr community tooling page [S3]; an Open VSX build exists for
  `ciarant.vscode-structurizr` (**verified locally**:
  `curl https://open-vsx.org/api/-/search?query=structurizr`, returned version 0.0.9).
  The `systemticks.c4-dsl-extension` named on the Structurizr page was not found on Open VSX
  (`curl https://open-vsx.org/api/systemticks/c4-dsl-extension` returned "Extension not found").
- ⏳ Devcontainer / Codespace (B3 in ADR 0002): an extra for technical users, not a
  replacement for B1.

## Non-technical user flow

Requirements (from `task.md` and ADRs 0002 and 0004):

1. Free, no SaaS, no paid Structurizr `server` licence.
2. Runs on-premises in a container.
3. Changes reach the repo only as a pull request, never as a push to `main`.
4. The DSL in git stays the single source of truth.

### Candidates

| # | Candidate | Licence / cost | Container image | On-prem | Editing experience | Live preview | Path to PR | Effort | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Structurizr `playground` | Free, open source | Same pinned image, `playground` command | Yes | Raw DSL in an Ace text area; upload a DSL file, load or save only to browser local storage | Yes, renders on "parse" | None. No disk or git access, no download button; multi-file `!include` and `!docs` cannot work from a pasted file | Not usable as the editor | **From docs** [S1]. **Verified locally**: `podman run -d --rm -p 18090:8080 docker.io/structurizr/structurizr:2026.09.19 playground`, then `curl http://localhost:18090/`: page has a `<form action="/" method="post">`, `ace.edit("sourceTextArea")`, `uploadFileInput`, and only `loadFromLocalStorageButton` / `saveToLocalStorageButton` (no download or file-save code) |
| 2 | Structurizr `local` + code-server on a git clone | `local` free [S2]; code-server MIT (**verified locally**: `curl https://raw.githubusercontent.com/coder/code-server/main/LICENSE`, "The MIT License") | `docker.io/codercom/code-server` [S5]; `local` is the pinned image | Yes | VS Code in the browser: text editing with DSL syntax highlighting from Open VSX, plus a file tree and a terminal | Yes, `local` in a second tab, refresh or auto-refresh [S2] | Our `submit` script (validate, commit, push, `gh pr create`) | Medium: image, `submit`, token handling | **From docs** [S2][S5][S6]. Extensions come from Open VSX, not Microsoft's marketplace [S6]. Password auth via `PASSWORD` / config file [S5] |
| 3 | Structurizr `local` + openvscode-server on a git clone | `local` free; openvscode-server MIT (**verified locally**: `curl https://raw.githubusercontent.com/gitpod-io/openvscode-server/main/LICENSE.txt`, "MIT License") | `gitpod/openvscode-server` [S7] | Yes | Same VS Code experience as row 2 | Yes, as row 2 | Same `submit` script | Medium, same as row 2 | **From docs** [S7]. The image runs without authentication by default; a connection token needs a custom `ENTRYPOINT` [S7], so we would need a reverse proxy or entrypoint override for access control. Row 2 has built-in password auth, hence preferred |
| 4 | Forgejo or Gitea web editor (browser "edit file" on a branch, then PR) | Gitea MIT (**verified locally**: `curl -s https://api.github.com/repos/go-gitea/gitea | jq .license.spdx_id` returns `MIT`); Forgejo GPL-3.0-or-later since v9 [S8] | Not checked; both projects document container installs [S18] | Yes | Plain text editor with preview of the file; no diagram preview | No: nothing renders the DSL in the forge | Native "edit, commit to new branch, open PR" on the forge itself | Low to run, but changes the platform | **From docs** [S8][S9][S10]. Needs Forgejo or Gitea to be the primary forge. Pull mirrors are read-only and can only be created for repositories that do not exist yet [S8], so a Forgejo mirror of the GitHub repo cannot take PRs back to GitHub. This contradicts "hosted on GitHub" (bootstrap decision) |
| 5 | c4hero (visual canvas that saves Structurizr DSL) | Apache-2.0 (**verified locally**: `curl https://raw.githubusercontent.com/c4hero/c4hero/main/LICENSE`) | None published; static SPA you build with `npm run build` and serve with nginx [S11] | Yes if self-hosted [S11] | Visual: drag and drop elements and relationships, DSL pane in sync, saves `.dsl` | Yes, it is its own renderer, not Structurizr's | None. It writes files through the browser File System Access API (Chromium only); no git, no PR [S11] | High: we would add a container with git and `submit` around it | **From docs** [S11][S12]. Own hand-written DSL parser and serializer, so unusual DSL (our `kubernetes.*` properties, `!include`, scripts) needs testing for round-trip loss. Project is young (56 GitHub stars at the time of writing, **verified locally**: `curl -s https://api.github.com/repos/c4hero/c4hero | jq .stargazers_count`) |
| 6 | Small custom form app in our container | Ours | Ours | Yes | Forms for the 80% case (add a container, a relationship, a `kubernetes.*` property) writing DSL | Via `structurizr local` on the same clone | Same `submit` script | Highest: a parser or DSL patcher plus UI to maintain | Design option only; no existing project of this kind other than row 5 was found. **From docs**: the Structurizr community tooling page lists authoring tools and DSL editors, none of them a self-hosted visual editor with git [S3] |
| 7 | LikeC4 (own language, VS Code extension, dev server) | MIT (**verified locally**: `curl -s https://api.github.com/repos/likec4/likec4 | jq .license.spdx_id` returns `MIT`) | `likec4/likec4` on Docker Hub and `ghcr.io/likec4/likec4`; a CLI image, no editor in it (**verified locally**: `podman pull docker.io/likec4/likec4:latest`) | Yes | Text in code-server plus the official extension (completion, diagnostics); dev server can adjust layouts | Yes, hot reload (**from docs** [S13]) | Same `submit` pattern as row 2 with `likec4 validate`; nothing built in | Medium, plus rewriting all workspaces | **From docs** [S13]. Own language, no Structurizr importer found. **Verified locally**: `kubernetes.*` keys cannot contain a dot (comparison row 10). AI-friendliness: `llms.txt` and `llms-full.txt` (HTTP 200), an agent skill and an MCP server, **from docs** [S22]. Full comparison in [likec4-comparison.md](likec4-comparison.md); proposed [ADR 0005](../decisions/0005-trial-likec4-for-the-editor-path.md) is a trial, not a switch |

Not a candidate: diagrams.net (draw.io) was considered and **dropped**: it has C4
shapes but a drawing is not a model [S14], so it would be a second source of truth
next to the DSL (ADR 0002). The only link found into a model goes the other way:
LikeC4 can export views to `.drawio`, its CLI has no import of edited drawings back
(**verified locally**: `podman run --rm docker.io/likec4/likec4:latest --help` lists
no `import` command), and the converter `parseDrawioToLikeC4` is a library function
in `@likec4/generators`, not in the image (**verified locally**:
`grep -rl parseDrawioToLikeC4 /usr/local/lib/node_modules/likec4` inside the image
found nothing) [S22][S23]. Structurizr's own AI page marks draw.io-style tools as
not recommended for AI workflows [S24]. A `jgraph/drawio` image exists [S19], so
hosting was not the issue.

Notes on the table:

- Structurizr `server` has a diagram editor but needs a paid licence from £300/month for
  1-20 users [S4] (ADR 0004), and it stores state outside git (rejected as B2, ADR 0002).
- Behaviour of `local` that matters here: **from docs**, it has no authentication or
  collaboration features and "access is only permitted via localhost URLs" [S2].
  **Verified locally**: with `-v <copy of examples/shop>:/usr/local/structurizr`,
  `curl -H "Host: editor.example.com" http://localhost:18091/workspace/1/diagrams`, and the
  same with `Host: 192.168.1.5:8080` and `X-Forwarded-Host`, all returned HTTP 200. So the
  restriction was not visible through a published Podman port, but this test did not come
  from a second machine. Treat it as unproven and test through the real proxy before
  relying on it. The design below keeps `local` bound to the container's loopback behind
  the editor's own proxy, so it does not depend on that answer.
- `local` auto-saves layout changes into `workspace.json` (default 5000 ms) [S2]. In the
  editor container that file is gitignored and would not reach the PR, so set
  `STRUCTURIZR_EDITABLE=false` there (**from docs** [S2]) to avoid users thinking a layout is saved.

### Recommendation

The LikeC4 comparison, now including AI-friendliness as a third criterion, does not
change this recommendation (it proposes a trial of the same B1 pattern with a
different renderer). Build row 2: **code-server + `structurizr local` on a git
clone, with a `submit` command**, as already sketched in Flow B1. It is the cheapest
option that meets all four requirements. Revisit row 5 (a visual editor) once the PR
path exists, because a visual front end can be put in front of the same clone and
`submit` later. Row 4 is the fallback only if the owner decides to move the repo off
GitHub.

Proposed journey:

1. The person opens a link (for example `https://editor.<internal-host>/`) and logs in.
2. The container starts with a fresh clone of `main` on a new branch
   `model/<user>/<date>-<slug>` ⏳. They see code-server with the workspace file open and
   the Structurizr diagram view next to it.
3. They edit the DSL. The diagram tab re-renders on refresh.
4. They run `submit` (a task button or a terminal command) ⏳: it runs `structurizr validate`
   (same check as `just validate`), commits, pushes the branch and runs `gh pr create`.
   Validation failure stops the submit and shows the error.
5. They get the PR link. A reviewer takes over in GitHub; CI runs `just check`.

Container architecture:

- **Clone**: `git clone` of the repo inside the container at start, never the user's
  working copy. `git` identity is set to the user so the PR shows who changed it.
- **Processes**: code-server on the published port; `structurizr local` on the clone
  directory (one workspace, `WORKSPACE`-style selection by the launcher); a reverse proxy
  or the launcher exposes both under one origin. `STRUCTURIZR_EDITABLE=false`,
  `STRUCTURIZR_AUTOREFRESHINTERVAL=2000`.
- **Token scope**: a GitHub fine-grained token limited to this repository with
  `contents:write` and `pull_requests:write`, passed as an env var, never in the image,
  compose file or DSL (non-negotiable 3). Better: a GitHub App installation token minted
  per session so it expires.
- **No push to `main`**, two layers: (a) `submit` creates the branch itself, refuses to
  run when the current branch is `main`, and pushes only to refs under `model/`;
  (b) branch protection or a ruleset on GitHub that requires a PR and passing checks for
  `main` [S15]. Layer (b) is the enforcement; layer (a) is a guard against mistakes.
  The token cannot bypass (b), because bypass is not granted to it. ⏳ both layers.
- **Auth** for the editor itself: code-server's password [S5] is acceptable for a pilot;
  for a real deployment put it behind the organisation's SSO proxy. This is an open
  question (see below).
- **Capabilities the user does not need**: no `kubectl`, no cloud credentials in the
  container (non-negotiable 1).

### Open questions from Flow B1

**1. One container per editing session, or long-lived per person?**
Answer: **one container per session**, disposable.
Reasons: (a) the clone is then always fresh from `main`, so no stale base and no merge
problems from a clone that is weeks old; (b) a token can be short-lived and scoped to that
session; (c) no state to back up or clean up inside the container, because work in
progress is saved as a pushed draft branch (see Lifecycle, drafts); (d) a person who
forgets to log out costs nothing once an idle timeout stops the container.
Trade-off: the user must "save draft" before leaving, which `submit --draft` (⏳) does for
them, and also on idle shutdown if the launcher calls it. If that is judged too fragile, the
fallback is a per-person named volume holding the clone, still with a fresh container each time.
Evidence: design reasoning; no local probe is possible for this question. The ADR 0002
rule "DSL in git is the single source of truth" supports keeping state out of containers.

**2. Can `playground` replace code-server?**
Answer: **no**.
Reasons: it is a stateless scratch pad. Its only persistence is upload of a file from the
computer and load/save to browser local storage [S1]. It has no mount of a data directory,
cannot read the repo's `!include`d files, and has no download, commit or PR step.
Evidence: **from docs** [S1], and **verified locally** with
`podman run -d --rm -p 18090:8080 docker.io/structurizr/structurizr:2026.09.19 playground`
and `curl http://localhost:18090/`: the page's only persistence code is
`loadFromLocalStorageButton` / `saveToLocalStorageButton` plus a file upload input; the
form posts DSL to `/`. I read the served HTML; I did not drive the page in a browser, so
this is evidence from the shipped page source, not a click-through test.
Where it can still help: a zero-install scratch pad for trying DSL syntax, or as a teaching
aid. It cannot be part of the PR path.

## Lifecycle

- **Branch naming.** Editor: `model/<user>/<date>-<slug>` (from Flow B1), for example
  `model/anna/2026-10-12-add-billing-service`. Proposed for technical users making model
  changes: the same scheme, so one branch-protection and cleanup rule covers all. Tooling
  or docs changes keep conventional prefixes such as `feat/`, `fix/`, `docs/`.
- **Drafts and work in progress.** Open a **draft PR** early (`gh pr create --draft` [S16]);
  GitHub draft PRs cannot be merged and do not request code-owner review [S17]. For a
  non-technical user, `submit --draft` ⏳ commits and pushes the branch and opens or
  updates a draft PR, so closing the browser loses nothing. "Ready for review" is a second
  action (`submit --ready` ⏳, or the button in GitHub). Long-lived personal branches are
  discouraged: they rot against `main`.
- **Concurrent edits and conflicts.** The DSL is text, so git merges non-overlapping
  edits and reports conflicts otherwise. Two people adding to the same `model { }` block
  often conflict on adjacent lines; resolving is a technical task, so the editor's
  fallback is: if `submit` finds the branch behind `main` and rebase conflicts, it
  stops and asks a technical user to resolve (`submit` does not guess). `workspace.json`
  is gitignored and so cannot conflict. If someone force-adds one (`git add -f`), treat it
  as generated: on conflict, take either side, delete it, reload in `local` and
  re-commit. Prefer `autolayout` so there is no `workspace.json` to commit.
- **Review and CI gate.** Every model change is a PR. The required check is `just check`
  (`.github/workflows/check.yml` ✅). Reviewers look at the DSL diff; ⏳ CI could also
  attach the exported static site for the PR as a build artifact so reviewers see the
  diagrams, not only the text. A model owner or `CODEOWNERS` per workspace directory (⏳)
  decides who must approve.
- **Merge strategy.** Proposed: squash merge, so `main` has one commit per model change
  with the PR title as message and the `model/*` branch is deleted on merge. Our view: a merge
  queue is not needed at this size.
- **Publishing on merge.** ⏳ CI job on push to `main`: `uv run python tools/export_site.py`
  then publish `build/site`. Where to publish is open (ADR 0004,
  `docs/workflow.md`): GitHub Pages, or an internal static host. Publishing a Pages site
  privately requires the organisation to use GitHub Enterprise Cloud [S20]; we have not
  checked which plan we have.
- **Getting the current state locally.** `git pull` then `just site` ✅ builds and serves
  the static site on http://localhost:8081 from the checked-out `main`; `just up` ✅ for
  live rendering of one workspace. Without git: ⏳ open the published site. For
  versioned snapshots ⏳ tag releases (`git tag model-2026-10-12`) and let the publish job
  also keep `build/site` for each tag as a release asset, so "what did the architecture
  look like in Q3" has an answer.
- **Cleanup.** Merged `model/*` branches are deleted by GitHub's "delete branch on merge"
  setting [S21] (⏳ to enable). Stale unmerged branches: a scheduled job (⏳) lists
  `model/*` branches with no commit for N days and comments on or closes their draft
  PRs. Editor containers stop after an idle timeout and are removed on exit (`--rm`), which
  is what per-session containers buy us.

## Open questions for the owner

1. Is **code-server + `structurizr local` + `submit`** (B1, row 2) the right first step for
   non-technical users, or is a text-based editor still too hard for them? If it is too
   hard, who are the first real users and what do they need to change (names, descriptions,
   relationships, new containers)? That decides whether to invest in a visual front end
   (row 5 or a custom form, row 6).
2. How does the editor get **authentication and access control**: code-server password for
   a pilot, or SSO via the organisation's proxy? Who can reach it (VPN, internal network)?
3. Where does it **run**: one shared host (Podman or Docker), Kubernetes, or each person's
   machine? Per-session containers need a launcher that starts and stops them.
4. Which **GitHub credential**: fine-grained personal token per person, or a GitHub App
   that mints short-lived tokens? Who owns it?
5. May we require branch protection / rulesets on `main` (required PR, required `check`,
   delete branch on merge), and who approves model PRs (CODEOWNERS)?
6. Is the repo staying on **GitHub**? Row 4 only makes sense if not.
7. **Publishing target** for the static site, and whether versioned snapshots by tag are
   wanted. Publishing a Pages site privately requires the organisation to use GitHub
   Enterprise Cloud [S20]; which plan do we have?
8. Branch naming for technical users: use `model/<user>/<date>-<slug>` too?
9. Should this become an ADR once answered? Suggested: yes, one ADR for the editor design
   and one for the lifecycle rules. The number 0005 is now taken by the proposed LikeC4
   trial ([ADR 0005](../decisions/0005-trial-likec4-for-the-editor-path.md)), so these
   would be 0006 and later.
10. Do you accept a trial of LikeC4 for the editor path before the tool choice is fixed?
    See the open questions in [likec4-comparison.md](likec4-comparison.md#open-questions-for-the-owner).

## Sources

- S1 https://docs.structurizr.com/playground (playground command, features, Docker quickstart)
- S2 https://docs.structurizr.com/local and https://docs.structurizr.com/local/configuration
  and https://docs.structurizr.com/local/workflow (local command, localhost-only, auto-save,
  auto-refresh, `STRUCTURIZR_EDITABLE`, `workspace.json`)
- S3 https://docs.structurizr.com/community (community tooling: editors, authoring tools, c4hero)
- S4 https://docs.structurizr.com/server/pricing (server licence price)
- S5 https://github.com/coder/code-server and
  https://raw.githubusercontent.com/coder/code-server/main/docs/install.md (licence, Docker, password)
- S6 https://raw.githubusercontent.com/coder/code-server/main/docs/FAQ.md (extensions and marketplace)
- S7 https://github.com/gitpod-io/openvscode-server (licence, Docker, connection token)
- S8 https://forgejo.org/docs/latest/user/repo-mirror/ (mirroring) and
  https://codeberg.org/forgejo/forgejo (GPL-3.0-or-later since v9)
- S9 https://github.com/go-gitea/gitea (Gitea, MIT)
- S10 https://docs.codeberg.org/git/clone-commit-via-web/ (forge web editor) and
  https://docs.gitea.com/usage/issues-prs/pull-request (pull requests, WIP prefix)
- S11 https://github.com/c4hero/c4hero and
  https://raw.githubusercontent.com/c4hero/c4hero/main/docs/DEPLOYMENT.md (features, self-hosting, Apache-2.0)
- S12 https://raw.githubusercontent.com/c4hero/c4hero/main/README.md (File System Access API, own DSL parser)
- S13 https://likec4.dev/ (LikeC4)
- S14 https://www.drawio.com/blog/c4-modelling (draw.io C4 shapes)
- S15 https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- S16 https://cli.github.com/manual/gh_pr_create (`--draft`)
- S17 https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests (draft PRs)
- S18 https://docs.gitea.com/installation/install-with-docker and
  https://forgejo.org/docs/latest/admin/installation/ (container installs)
- S19 https://hub.docker.com/r/jgraph/drawio (draw.io image listing)
- S20 https://docs.github.com/en/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site (private Pages sites; checked 2026-10-10 with `curl -sL <url> | grep -o "Enterprise Cloud[^<]\{0,60\}"`,
  the page says: "To publish a GitHub Pages site privately, your organization must use GitHub
  Enterprise Cloud")
- S21 https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-the-automatic-deletion-of-branches
- S22 https://likec4.dev/llms-full.txt and https://likec4.dev/tooling/drawio/ (LikeC4 AI
  tools: agent skill, MCP server; DrawIO export, no CLI import)
- S23 https://raw.githubusercontent.com/likec4/likec4/main/packages/generators/src/drawio/parse-drawio.ts
  (library function that parses `.drawio` XML into LikeC4 source)
- S24 https://docs.structurizr.com/ai (Structurizr AI page: UI-driven diagramming tools such
  as draw.io are marked "No" for AI workflows; a vendor view)
- Open VSX search: https://open-vsx.org/api/-/search?query=structurizr
- Repo: `docs/workflow.md`, `docs/decisions/0001` to `0004`, `justfile`, `prek.toml`,
  `.github/workflows/check.yml`, `docker/compose.yml`
