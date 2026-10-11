# 0006: LikeC4 is the tool of record; Structurizr is removed

Date: 2026-10-11 · Status: accepted (owner, 2026-10-11)

Supersedes: [0001](0001-structurizr-vnext-single-image.md),
[0004](0004-static-site-instead-of-server.md) and the trial
[0005](0005-trial-likec4-for-the-editor-path.md). Amends: [0002](0002-dsl-in-git-is-source-of-truth.md)
(the model files are `.c4`, not `.dsl`) and [0003](0003-deploy-starts-as-drift-check.md) (the
Kubernetes contract keys are renamed; the read-only drift-check decision stands).

## Context

ADR 0005 trialled LikeC4 for the browser-editor path while Structurizr stayed the tool of
record. The trial is done and the owner decided on 2026-10-11 to use LikeC4 instead of
Structurizr. Evidence:

- [likec4-comparison](../research/likec4-comparison.md): LikeC4 compared with the Structurizr
  workflow.
- [likec4-trial-poc](../research/likec4-trial-poc.md): the shop example ported to `.c4`, the
  editor PoC built for both tools, with measurements.
- [likec4-web-editing](../research/likec4-web-editing.md): the in-browser editing service on a
  fresh clone, and its open questions.

Structurizr stays what it was when ADRs 0001 and 0004 were written: its prebuilt server needs
a paid license and it cannot write model changes back to git. LikeC4 is open source, has a
free static-site build, and its model files can be edited as plain text next to a live
diagram.

## Decision

- LikeC4 is the only modelling tool in this repo.
- One pinned image, `docker.io/likec4/likec4:1.59.4`, runs `validate`, `format`, `start`,
  `build` and `export`. The editor images pin the npm package `likec4@1.59.4` and the VS Code
  extension `likec4.likec4-vscode@1.59.4`.
- The `.c4` files in git are the single source of truth. ADR 0002 still holds, with ".dsl"
  read as ".c4": nothing in the UI writes back, so editing UIs work on a git clone.
- Browsing is the static site from `likec4 build`. It replaces ADR 0004's
  `structurizr export -f static`. There is still no server and nothing writable.
- The Kubernetes contract is `kubernetes_namespace`, `kubernetes_kind` and `kubernetes_name`
  metadata keys, because LikeC4 metadata keys cannot contain a dot. This renames the
  `kubernetes.namespace`, `kubernetes.kind` and `kubernetes.name` properties of ADR 0003.
  Its decision (a read-only drift check first) is unchanged.
- A LikeC4 project is a directory with a `likec4.config.json`. Inside it, the layout is
  `shared/`, `teams/<domain>/` and `views/`, and CODEOWNERS assigns the folders.
- All Structurizr files are removed. Git history keeps them.

## Consequences

- Structurizr is not used again without a new ADR.
- A LikeC4 upgrade bumps every pin together: the `justfile`, `tools/validate_models.py` and
  both editor Containerfiles.
- The policy for the layout files `.likec4/*.likec4.snap` is decided in the editor-image task,
  not here.
- Risk: LikeC4 has one main maintainer. The model stays plain text in git, so a later move is
  possible but not free.
- The image is 1.45 GB, so `just check` in CI pulls more than the 437 MB Structurizr image did.
- ADRs 0001, 0004 and 0005 stay as records; only their status lines change.

## Sources

- [likec4-comparison](../research/likec4-comparison.md)
- [likec4-trial-poc](../research/likec4-trial-poc.md)
- [likec4-web-editing](../research/likec4-web-editing.md)
