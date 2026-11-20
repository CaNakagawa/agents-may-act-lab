# Spec: Agents may act, policies decide — training lab

## Objective

Give workshop participants a reproducible, self-contained GCP lab they can provision in their own project. The browser panel runs locally from Python. Gemini on Vertex AI reads the included README scenario and proposes a Kubernetes Pod. The runner creates an ordinary nginx pod in `demo-unprotected` and sends the generated privileged proposal to `demo-regulated` using Kubernetes server-side dry-run so admission policies can reject it without persisting a privileged pod.

## Tech stack

- Terraform and Google provider for a zonal GKE Standard cluster.
- Helm for pinned Kyverno installation; Kubernetes `ValidatingPolicy` manifests for the exercise.
- Python, Flask, `google-genai`, and the participant's Application Default Credentials.
- HTML/CSS/JavaScript panel served on localhost.

## Commands

Full setup, execution, and teardown commands are in the root README. No command automatically applies Terraform or deploys a privileged pod.

## Project structure

- `terraform/`: participant-owned GKE cluster and VPC.
- `kyverno/`: two namespaces and two validation policies.
- `manifests/`: safe reference workload and privileged admission fixture.
- `fixtures/injected/README.md`: intentionally hostile workshop input, never a trusted configuration source.
- `panel.py`, `panel.html`: local Python backend and presentation interface.
- `scripts/`: explicit Kyverno setup and application cleanup.

## Boundaries

- The user-supplied README and model output are untrusted.
- Only a fixed nginx image and a fixed pod shape are accepted from the model.
- Model output is never passed to a shell. The only generated manifest request uses `kubectl create --dry-run=server` against `demo-regulated`.
- The only persisted workload is the fixed, unprivileged nginx pod in `demo-unprotected`.
- No service-account keys, project IDs, cluster names, or account emails are committed.
- Cloud Run, public hosting, and a shared GCP project are out of scope.
- Participants own their billing, IAM grants, cluster, and cleanup.

## Success criteria

- A participant can provision a new GKE Standard cluster, install Kyverno and apply the included namespace/policy YAMLs using the documented sequence.
- The panel can run locally after `gcloud auth application-default login` and `gcloud container clusters get-credentials`.
- A run creates/updates only the safe reference nginx pod and submits the regulated fixture only as server-side dry-run.
- The panel distinguishes Kyverno denial from another GKE admission denial and explains that dry-run creates no pod.
- Teardown instructions remove demo workloads, Kyverno, and Terraform-managed infrastructure.

## Out of scope

- Deploying or publishing Cloud Run services.
- Recreating the original presenter project or its Agent Runtime.
- Production GKE hardening or high availability.
- Applying arbitrary manifests or allowing model output to execute commands.

## Assumptions and limits

- Each participant has a disposable GCP project with billing enabled and permissions to enable APIs, provision GKE/network/IAM, and use Vertex AI.
- GKE admission ordering can vary. GKE Warden or another admission controller may reject the request before Kyverno; the UI must report the actual response and must not claim Kyverno was responsible unless the response identifies Kyverno.
- Model output is nondeterministic. If Gemini refuses or returns a different manifest, the fixed allowlist rejects it and the demo reports that the admission attempt was not sent.
- This is a training lab, not a production agent pattern.
