# Model conventions

## Kubernetes metadata on deployment elements

These metadata keys are the contract between the C4 deployment model and the cluster. The
drift check (and later, object generation) reads them; diagrams ignore them.

| Key | On | Meaning |
| --- | --- | --- |
| `kubernetes_namespace` | deployment node | Namespace the instances under this node run in. Inherited by children. |
| `kubernetes_kind` | deployment instance (`instanceOf`) | `Deployment`, `StatefulSet`, `DaemonSet`, `CronJob` |
| `kubernetes_name` | deployment instance (`instanceOf`) | `metadata.name` of the workload |

```
shopNamespace = node 'shop' {
  metadata {
    kubernetes_namespace 'shop'
  }
  api = instanceOf shop.api {
    metadata {
      kubernetes_kind 'Deployment'
      kubernetes_name 'shop-api'
    }
  }
}
```

The keys use underscores because LikeC4 metadata keys cannot contain a dot
([ADR 0006](decisions/0006-likec4-is-the-tool-of-record.md)).

Rules:

- A deployment instance without `kubernetes_name` is not checked (e.g. managed services).
- Renaming a key is a breaking change for every job that reads it: change the tooling and
  every model in the same PR.

## Layout

A LikeC4 project is a directory with a `likec4.config.json`. All `.c4` files under it form
one model. Inside a project:

- `shared/`: the specification, people, shared and external systems and shared deployment nodes.
- `teams/<domain>/`: one team's model, its relations, its deployment instances and its views.
  A cross-team relation lives in the team that starts the call. A relation started by a
  person, an external system or the event bus lives in the team of its target.
- `views/`: cross-team views, among them the landscape as view `index` (the start page).
  `views/dynamic/` holds one dynamic view per file.
- View titles start with a menu folder: `<Team> / <title>` for a team's views and the dynamic
  views it leads, `Overview / <title>` for cross-team views. LikeC4 builds the menu from `/`
  in titles and shows only the last segment as the view's title, so that segment must make
  sense alone.

`.github/CODEOWNERS` assigns the folders: each `teams/<domain>/` to its team, `shared/` and
`views/` to the architecture owners. `examples/shop/README.md` describes the layout on a
six-team example, and `examples/shop/CODEOWNERS` shows example rules.

Where projects live:

- `examples/<name>/`: example projects, safe to break (`examples/shop`).
- `workspaces/<name>/`: real models (none yet).

`tools/validate_models.py` finds every directory with a `likec4.config.json` under
`examples/` and `workspaces/` (skipping `.likec4`, `node_modules` and `build`) and runs
`likec4 validate` and `likec4 format --check` on it. Run `just validate` for that alone.

## Layout files

Dragging an element in the "Edit" mode of `likec4 start` writes `.likec4/<view>.likec4.snap`
into the project. Whether to commit or ignore these files is open; it is decided in the
editor-image task.
