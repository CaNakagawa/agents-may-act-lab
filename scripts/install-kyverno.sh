#!/usr/bin/env bash
set -euo pipefail

command -v kubectl >/dev/null || { echo "kubectl is required." >&2; exit 1; }
command -v helm >/dev/null || { echo "Helm is required." >&2; exit 1; }
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
context="$(kubectl config current-context)"
[[ -n "$context" ]] || { echo "No active kubectl context. Connect to the lab cluster first." >&2; exit 1; }
printf 'Installing the lab policy into context: %s\n' "$context"
read -r -p 'Continue only if this is your disposable training cluster [y/N]? ' answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Stopped without changes."; exit 1; }

helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update kyverno
helm upgrade --install kyverno kyverno/kyverno \
  --version 3.10.0 \
  --namespace kyverno \
  --create-namespace \
  --wait \
  --timeout 5m

kubectl wait --for=condition=Established crd/validatingpolicies.policies.kyverno.io --timeout=120s
kubectl apply -f "$script_dir/../kyverno/namespaces.yaml"
kubectl apply -f "$script_dir/../kyverno/required-label.yaml"
kubectl apply -f "$script_dir/../kyverno/deny-privileged.yaml"
kubectl get validatingpolicies.policies.kyverno.io
printf '\nKyverno and the lab policies are installed in %s.\n' "$context"
