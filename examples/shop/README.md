# Shop example: a multi-team LikeC4 model

A fictional web shop, modelled in LikeC4 by six domain teams. It exists to try the tooling
(validate, format, render, edit through a git clone) on a model big enough that several
people edit it at the same time. Every system, team and handle in it is made up.

## Teams

Example owners are in [`CODEOWNERS`](CODEOWNERS). That file has no effect on GitHub; it shows
how `.github/CODEOWNERS` would look.

| Team | Folder | System id | Example owner |
| --- | --- | --- | --- |
| Catalog | `teams/catalog/` | `catalog` | `@shop-example/team-catalog` |
| Accounts | `teams/accounts/` | `accounts` | `@shop-example/team-accounts` |
| Cart and checkout | `teams/checkout/` | `checkout` | `@shop-example/team-checkout` |
| Orders | `teams/orders/` | `orders` | `@shop-example/team-orders` |
| Payments | `teams/payments/` | `payments` | `@shop-example/team-payments` |
| Fulfilment | `teams/fulfilment/` | `fulfilment` | `@shop-example/team-fulfilment` |
| Architecture | `shared/`, `views/` | `eventBus` and all shared elements | `@shop-example/architecture` |

## Files

```
likec4.config.json
CODEOWNERS
shared/
  spec.c4          element kinds, deployment node kinds, tag external, relationship kind async
  people.c4        customer, guest, supportAgent, warehouseWorker, merchantAdmin
  external.c4      paymentProvider, shippingCarriers, erp, messaging, identityProvider, taxService
  platform.c4      eventBus (container eventBus.broker)
  deployment.c4    environments prod and staging, their clusters, the platform namespace
teams/<domain>/
  model.c4         the team's system, its containers and components, its relations
  deployment.c4    the team's namespace and instances in prod and staging
  views.c4         the team's context, container and component views
views/
  landscape.c4     Landscape
  deployment.c4    ProdDeployment, StagingDeployment
  dynamic/         one dynamic view per file: checkout, payment-retry, order-fulfilment, returns-refunds
```

### Where a relation lives

- Write every relation at the top level of a `model { }` block, with a fully qualified source
  (`checkout.checkoutApi.paymentClient -> payments.paymentApi.paymentController '...'`). Do not
  nest relations inside element bodies.
- A relation lives in `teams/<d>/model.c4` when its source is inside system `<d>`. The team
  that starts the call owns the relation.
- A relation whose source is a person, an external system or `eventBus` lives in the folder
  of its **target** (`customer -> catalog.storefront` is in `teams/catalog/`).
- A relation between shared elements only lives in `shared/` (`messaging -> customer` is in
  `shared/external.c4`).

## Views

| Level | Views |
| --- | --- |
| Landscape | `Landscape` |
| System context | `CatalogContext`, `AccountsContext`, `CheckoutContext`, `OrdersContext`, `PaymentsContext`, `FulfilmentContext` |
| Containers | `CatalogContainers`, `AccountsContainers`, `CheckoutContainers`, `OrdersContainers`, `PaymentsContainers`, `FulfilmentContainers` |
| Components | `CheckoutComponents` (of `checkout.checkoutApi`), `OrdersComponents` (of `orders.orderApi`), `PaymentsComponents` (of `payments.paymentApi`) |
| Deployment | `ProdDeployment`, `StagingDeployment` |
| Dynamic | `CheckoutFlow`, `PaymentFailureRetry` (sequence); `OrderFulfilmentFlow`, `ReturnsRefundsFlow` (diagram) |

Run `just up` to browse them live on http://127.0.0.1:8080, or `just site` for the static
site on http://127.0.0.1:8081 (`just down` stops both).

## Avoiding conflicts

- A relation lives in the team that starts the call, so a team's change stays in its folder.
- Shared files are small and hold one subject each (people, external systems, platform,
  deployment), so two edits rarely touch the same lines.
- `likec4 format --check` is part of `just check`, so everyone writes the same layout and
  diffs stay small.
- Layout files (`.likec4/*.snap`, written when you drag elements in the UI): whether to commit
  them is still open. The `likec4-editor-image` task decides it. This project commits none.

## Multi-user scenarios

Run each one in Flow A with two local branches (`git switch -c <name>` from the same commit,
edit, commit, then `git merge`), or with the editor PoC: `just editor-build`,
`just poc-remote`, then one `just editor-up likec4` (code-server, ports 8092/8093) and one
`just editor-up likec4-web` (ports 8094/8095). Set a different `MODEL_SLUG` in `.env` (see
`.env.example`) before each call, against `build/poc-remote.git`. Running the same
`just editor-up <tool>` again deletes that editor's clone and recreates its container, so
submit each editor's change first. Stop them with `just editor-down`. Check each result with
`just validate`.

### 1. Two teams editing at once

- Branches: `model/catalog/add-wishlist` and `model/fulfilment/add-label-printer`.
- Catalog adds a container `wishlist` to `catalog` in `teams/catalog/model.c4`. Fulfilment
  adds a container `labelPrinter` to `fulfilment` in `teams/fulfilment/model.c4`.
- Owners whose review CODEOWNERS requires: `@shop-example/team-catalog` for the first PR,
  `@shop-example/team-fulfilment` for the second. Nobody else.
- Expected: merging the two branches is clean and `just validate` passes. Each PR is
  owned by one team.

### 2. Changing a relation between teams

- Branch: `model/payments/checkout-calls-refund-service`.
- Payments wants checkout to call a new component, `payments.paymentApi.refundService`
  instead of `payments.paymentApi.paymentController`. The relation
  `checkout.checkoutApi.paymentClient -> payments.paymentApi.paymentController` lives in
  `teams/checkout/model.c4`, because checkout starts the call.
- Owners: the PR touches `teams/checkout/`, so `@shop-example/team-checkout` must review
  (plus `@shop-example/team-payments` if payments files change too).
- Expected: the diff is in checkout's folder and needs `team-checkout` approval. Payments
  cannot change the relation in its own folder.

### 3. Renaming an element another team uses

- Branch: `model/payments/rename-payment-api`.
- Rename `payments.paymentApi` to `payments.paymentService` in `teams/payments/*.c4` only.
- Expected: `likec4 validate` fails. It reports errors in `teams/checkout/model.c4` and
  `teams/orders/model.c4`, which reference `payments.paymentApi.*`, and in
  `views/dynamic/checkout.c4`, `views/dynamic/payment-retry.c4` and
  `views/dynamic/returns-refunds.c4`.
- Owners: the fix touches other teams' files in the same PR, so `@shop-example/team-payments`,
  `@shop-example/team-checkout`, `@shop-example/team-orders` and `@shop-example/architecture`
  must all review it.

### 4. A deliberate conflict

- Branches: `model/payments/provider-description-a` and `model/orders/provider-description-b`.
- Both change the `description` of `paymentProvider` on the same line of
  `shared/external.c4`.
- Owners: `@shop-example/architecture` for both PRs, because both edit `shared/`.
- Expected: the second merge stops with a git merge conflict in that one small file.
  Resolving it is a few lines; nothing else conflicts.
