# LikeC4 trial

A LikeC4 (`.c4`) port of [`examples/shop`](../../examples/shop/workspace.dsl), made for the
trial in [ADR 0005](../../docs/decisions/0005-trial-likec4-for-the-editor-path.md). It is not
part of `just check` or CI, and the Structurizr DSL stays the source of truth until the
owner decides otherwise.

- `shop/model.c4`: same elements, relationships, `local-kind` deployment and three views as
  the DSL. Kubernetes data is under `kubernetes_namespace`, `kubernetes_kind` and
  `kubernetes_name` metadata keys, because LikeC4 metadata keys cannot contain a dot.
- Check it with `just trial-check` (runs `likec4 validate` and `likec4 format --check` in the
  pinned `docker.io/likec4/likec4:1.59.4` image).
- The measured comparison with Structurizr is in
  [docs/research/likec4-trial-poc.md](../../docs/research/likec4-trial-poc.md).

If the trial fails, this directory is deleted.
