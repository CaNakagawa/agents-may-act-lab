# ADR-001: Local runner and server-side admission dry-run

## Status

Accepted for the training package.

## Context

The existing presenter package assumes one already-provisioned GCP project and a published Agent Runtime. Training attendees need their own repeatable environment, while the exercise intentionally includes a privileged workload request.

## Decision

Run the small Python agent/panel locally with the attendee's ADC and current `kubectl` context. Use Terraform to provision a zonal GKE Standard cluster. Let the model produce a candidate, validate it against a narrow fixed schema, and submit it only to the regulated namespace with `kubectl create --dry-run=server`. The safe reference nginx pod is the only workload persisted by the panel.

## Consequences

- Attendees need local Python, `gcloud`, `kubectl`, Terraform, and Helm.
- No Cloud Run or Agent Runtime deployment is needed.
- The environment is isolated per attendee and incurs their own GCP charges.
- GKE admission controls can reject before Kyverno; the panel reports the source returned by the API.
- Dry-run gives a real admission decision but does not prove a privileged workload could run.
