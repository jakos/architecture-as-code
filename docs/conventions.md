# Model conventions

## Kubernetes properties on deployment elements

These properties are the contract between the C4 deployment model and the cluster. The
drift check (and later, object generation) reads them; diagrams ignore them.

| Property | On | Meaning |
| --- | --- | --- |
| `kubernetes.namespace` | deployment node | Namespace the instances under this node run in. Inherited by children. |
| `kubernetes.kind` | container instance | `Deployment`, `StatefulSet`, `DaemonSet`, `CronJob` |
| `kubernetes.name` | container instance | `metadata.name` of the workload |

Rules:

- A container instance without `kubernetes.name` is not checked (e.g. managed services).
- Renaming a property is a breaking change for every job that reads it: change the
  tooling and every workspace in the same PR.

## Layout

- `examples/<name>/workspace.dsl`: self-contained example workspaces, safe to break.
- `workspaces/<name>/workspace.dsl`: real workspaces (none yet).
- One workspace per directory, because Structurizr `local` mode serves a directory.
