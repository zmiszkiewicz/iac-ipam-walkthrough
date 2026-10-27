#!/bin/bash
# Apply the finished solution for a challenge so the walkthrough can skip ahead.
#
#   scripts/solve.sh 02|03|04
#
# Copies the end-state *.auto.tfvars from solutions/ into the matching terraform
# folder and applies it. Safe to run over a half-finished challenge.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-}" in
  02) dir="02-dns-records"; flags=() ;;
  03) dir="03-ipam"; flags=(-parallelism=1) ;;
  04) dir="04-privatelink"; flags=() ;;
  *) echo "usage: $0 02|03|04" >&2; exit 2 ;;
esac

if [[ ! -f "${REPO}/terraform/${dir}/terraform.tfvars" ]]; then
  echo "terraform.tfvars missing, generating it"
  (cd "${REPO}/scripts" && python3 make_tfvars.py stages)
fi

cp "${REPO}/solutions/${dir}/"*.tfvars "${REPO}/terraform/${dir}/"
cd "${REPO}/terraform/${dir}"
terraform init -input=false
terraform apply -auto-approve -input=false "${flags[@]}"
