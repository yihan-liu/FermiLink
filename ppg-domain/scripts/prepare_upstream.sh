#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="${ROOT}/upstream"
ensure_checkout() {
  local name="$1" url="$2" commit="$3"
  local path="${UPSTREAM}/${name}"
  if [[ -e "${path}" ]]; then
    if ! git -C "${path}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      echo "Refusing existing non-git path: ${path}" >&2; return 2
    fi
    local actual
    actual="$(git -C "${path}" rev-parse HEAD)"
    if [[ "${actual}" != "${commit}" ]]; then
      echo "Refusing to change ${path}: expected ${commit}, found ${actual}" >&2; return 2
    fi
    echo "already pinned: ${name} ${actual}"; return 0
  fi
  mkdir -p "${UPSTREAM}"
  git clone --no-checkout "${url}" "${path}"
  git -C "${path}" checkout --detach "${commit}"
  echo "checked out: ${name} ${commit}"
}
ensure_checkout pulse https://gitlab.kitware.com/physiology/engine.git 5e29e5b13710a08cec90874be7d36ecb192ebcda
ensure_checkout mcx https://github.com/fangq/mcx.git 49ec9f155107b7b54dece66d24e3c77a208cf2e8

verify_source_link() {
  local package="$1" link_name="$2" source_name="$3"
  local link_path="${ROOT}/packages/${package}/${link_name}"
  local expected="../../upstream/${source_name}"
  local actual
  actual="$(readlink "${link_path}")"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "Refusing unexpected source link ${link_path}: expected ${expected}, found ${actual}" >&2
    return 2
  fi
  if [[ "$(realpath "${link_path}")" != "$(realpath "${UPSTREAM}/${source_name}")" ]]; then
    echo "Source link does not resolve to the pinned checkout: ${link_path}" >&2
    return 2
  fi
  echo "source link verified: ${link_path} -> ${expected}"
}
verify_source_link pulse-physiology pulse_source pulse
verify_source_link mcx-optics mcx_source mcx
