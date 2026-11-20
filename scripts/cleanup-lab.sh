#!/usr/bin/env bash
set -euo pipefail

command -v kubectl >/dev/null || { echo "kubectl is required." >&2; exit 1; }
command -v helm >/dev/null || { echo "Helm is required." >&2; exit 1; }
context="$(kubectl config current-context)"
[[ -n "$context" ]] || { echo "No active kubectl context." >&2; exit 1; }
printf 'This removes only the named lab pods, lab policies/namespaces, and Kyverno release from: %s\n' "$context"
read -r -p 'Continue only if this is your disposable training cluster [y/N]? ' answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Stopped without changes."; exit 1; }

kubectl delete pod demo-nginx -n demo-unprotected --ignore-not-found --wait=false
kubectl delete pod demo-privileged-check -n demo-regulated --ignore-not-found --wait=false
kubectl delete validatingpolicy estrion-nginx-require-label estrion-deny-privileged --ignore-not-found
kubectl delete namespace demo-unprotected demo-regulated --ignore-not-found --wait=false
helm uninstall kyverno -n kyverno --ignore-not-found
kubectl delete namespace kyverno --ignore-not-found --wait=false
printf '\nLab workloads and Kyverno were removed. GKE and its network still incur costs.\n'
printf 'To remove the Terraform-managed cluster and network, review terraform plan -destroy, then run terraform destroy from terraform/.\n'
