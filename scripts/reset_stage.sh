#!/bin/bash
# Put a challenge back to its starting point so it can be run again.
#
#   scripts/reset_stage.sh 02|03|04|all
#
# Destroys what the stage's Terraform created and removes the *.auto.tfvars that
# hold the walkthrough's changes. The baseline and the seed data are untouched.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

reset_one() {
  local dir="$1"
  echo "=== resetting ${dir} ==="
  (cd "${REPO}/terraform/${dir}" && terraform destroy -auto-approve -input=false) \
    || echo "WARNING: terraform destroy failed in ${dir}; inspect before re-running"
  rm -f "${REPO}/terraform/${dir}/"*.auto.tfvars
}

stage="${1:-}"
case "${stage}" in
  02|03|04|all) ;;
  *) echo "usage: $0 02|03|04|all" >&2; exit 2 ;;
esac

if [[ "${stage}" == "02" || "${stage}" == "all" ]]; then
  # Records created through WAPI in the walkthrough are not in Terraform's state.
  (cd "${REPO}/scripts" && python3 dns_records.py delete) || true
fi

[[ "${stage}" == "04" || "${stage}" == "all" ]] && reset_one "04-privatelink"
[[ "${stage}" == "03" || "${stage}" == "all" ]] && reset_one "03-ipam"
[[ "${stage}" == "02" || "${stage}" == "all" ]] && reset_one "02-dns-records"
exit 0
