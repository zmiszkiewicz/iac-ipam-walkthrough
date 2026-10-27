#!/bin/bash
# Run this before pushing. It catches what otherwise only surfaces several
# minutes into a track start, with the audience already watching.
#
#   scripts/preflight.sh
#
# `terraform fmt` only checks layout; `terraform validate` is the check that
# evaluates templatefile() calls and provider-side attribute validation.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

FAILED=0
step() { printf '\n=== %s ===\n' "$1"; }
ok()   { printf '  OK    %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; FAILED=1; }
warn() { printf '  WARN  %s\n' "$1"; }

# Placeholder credentials so provider blocks validate. Nothing connects.
export INFOBLOX_SERVER="192.0.2.1" INFOBLOX_USERNAME="admin" INFOBLOX_PASSWORD="preflight"
export TF_VAR_nios_admin_password="preflight"
export ARM_SUBSCRIPTION_ID="00000000-0000-0000-0000-000000000000"

step "terraform fmt"
if terraform fmt -check -recursive terraform >/dev/null 2>&1; then
  ok "formatting is canonical"
else
  bad "run: terraform fmt -recursive terraform"
fi

step "terraform init + validate"
for dir in terraform/*/; do
  name="$(basename "${dir}")"
  if ! terraform -chdir="${dir}" init -backend=false -input=false >/dev/null 2>&1; then
    bad "${name}: terraform init failed"
    continue
  fi
  if out="$(terraform -chdir="${dir}" validate 2>&1)"; then
    ok "${name}"
  else
    bad "${name}"
    echo "${out}" | sed 's/\x1b\[[0-9;]*m//g' | sed 's/^/        /'
  fi
done

step "shellcheck"
if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck scripts/*.sh; then ok "scripts/*.sh"; else bad "shellcheck reported problems"; fi
else
  warn "shellcheck not installed, skipped"
fi

step "python"
if python3 -m py_compile scripts/*.py scripts/tests/*.py; then
  ok "all scripts compile"
else
  bad "py_compile failed"
fi
if python3 -m unittest discover -s scripts/tests >/dev/null 2>&1; then
  ok "offline tests pass"
else
  bad "offline tests failed: python3 -m unittest discover -s scripts/tests -v"
fi

step "secrets and customer names"
if grep -rInE --exclude-dir=.git --exclude-dir=.terraform --exclude=preflight.sh \
     -e 'AKIA[0-9A-Z]{16}' -e 'BEGIN (RSA )?PRIVATE KEY' -e 'password *= *"[^"$]' . >/dev/null 2>&1; then
  bad "something that looks like a credential is committed"
else
  ok "no credentials found"
fi

step "git"
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  warn "uncommitted changes: the track clones the pushed branch, not your working tree"
else
  ok "working tree clean"
fi

echo
if [[ "${FAILED}" -eq 0 ]]; then echo "preflight passed"; else echo "preflight FAILED"; fi
exit "${FAILED}"
