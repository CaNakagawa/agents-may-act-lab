# Capability map: Agents may act, policies decide

| Module | Responsibility | Depends on |
|---|---|---|
| `gke-infra` | Provision one low-footprint GKE Standard zonal cluster and network in the participant's own project | — |
| `admission-policy` | Install Kyverno, create the reference/regulated namespaces, and enforce label and privilege rules | `gke-infra` |
| `local-demo` | Serve the panel locally, submit one ordinary nginx pod, and send the README-derived privileged proposal to regulated admission as server-side dry-run | `admission-policy` |
| `workshop-docs` | Explain prerequisites, setup, presentation flow, cost boundaries, and teardown | all |

Build order: `gke-infra` → `admission-policy` → `local-demo` → `workshop-docs`.
