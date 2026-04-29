#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/featurize/work/BS"
RUN_DELETE="${RUN_DELETE:-0}"
PYCACHE_MANIFEST="/tmp/bs_pycache_manifest.txt"
SIZE_TMP_DIR="/tmp/bs_cleanup_sizes.$$"

STATIC_CANDIDATES=(
  "/tmp/sovits-conda310"
  "${PROJECT_ROOT}/so-vits-svc/.venv"
  "${PROJECT_ROOT}/so-vits-svc/vendor"
  "${PROJECT_ROOT}/.venv"
  "${PROJECT_ROOT}/backend/.venv"
  "${PROJECT_ROOT}/frontend/.vite"
  "${PROJECT_ROOT}/frontend/dist"
  "${PROJECT_ROOT}/.pytest_cache"
  "${PROJECT_ROOT}/.ruff_cache"
  "${PROJECT_ROOT}/.mypy_cache"
)

declare -a FOUND_PATHS=()

cleanup_temp_files() {
  rm -rf "${SIZE_TMP_DIR}" "${PYCACHE_MANIFEST}"
}

safe_du_job() {
  local path="$1"
  local output_file="$2"
  timeout 10s du -sb "${path}" 2>/dev/null | awk '{print $1}' > "${output_file}" || true
}

print_header() {
  echo "cleanup_unused_env_artifacts.sh"
  if [[ "${RUN_DELETE}" == "1" ]]; then
    echo "Mode: DELETE"
  else
    echo "Mode: DRY-RUN"
  fi
  echo
}

add_if_exists() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    FOUND_PATHS+=("${path}")
  fi
}

collect_candidates() {
  local path
  for path in "${STATIC_CANDIDATES[@]}"; do
    add_if_exists "${path}"
  done
}

build_pycache_manifest() {
  find "${PROJECT_ROOT}" \
    \( -path "${PROJECT_ROOT}/so-vits-svc/.venv" -o -path "${PROJECT_ROOT}/so-vits-svc/vendor" -o -path "${PROJECT_ROOT}/.venv" -o -path "${PROJECT_ROOT}/backend/.venv" \) -prune \
    -o -type d -name "__pycache__" -print | sort > "${PYCACHE_MANIFEST}"
}

report_candidates() {
  local total_bytes=0
  local path bytes human idx

  mkdir -p "${SIZE_TMP_DIR}"

  echo "Candidates:"
  for idx in "${!FOUND_PATHS[@]}"; do
    path="${FOUND_PATHS[$idx]}"
    safe_du_job "${path}" "${SIZE_TMP_DIR}/${idx}.size" &
  done
  wait

  for idx in "${!FOUND_PATHS[@]}"; do
    path="${FOUND_PATHS[$idx]}"
    bytes="$(cat "${SIZE_TMP_DIR}/${idx}.size" 2>/dev/null || true)"
    if [[ -n "${bytes}" ]]; then
      total_bytes=$((total_bytes + bytes))
      human="$(numfmt --to=iec-i --suffix=B "${bytes}")"
    else
      human="size-check-timeout"
    fi
    printf '  - %s (%s)\n' "${path}" "${human}"
  done

  build_pycache_manifest
  local pycache_count pycache_bytes pycache_human
  pycache_count="$(wc -l < "${PYCACHE_MANIFEST}" | tr -d ' ')"
  if [[ "${pycache_count}" != "0" ]]; then
    pycache_bytes="$(timeout 10s bash -lc 'tr '\''\n'\'' '\''\0'\'' < "'"${PYCACHE_MANIFEST}"'" | xargs -0 du -sb 2>/dev/null | awk '\''{sum += $1} END {print sum+0}'\''' || true)"
    if [[ -n "${pycache_bytes}" ]]; then
      pycache_human="$(numfmt --to=iec-i --suffix=B "${pycache_bytes}")"
      total_bytes=$((total_bytes + pycache_bytes))
      echo "  - ${PROJECT_ROOT}/**/__pycache__ (${pycache_human}, ${pycache_count} dirs)"
    else
      echo "  - ${PROJECT_ROOT}/**/__pycache__ (size-check-timeout, ${pycache_count} dirs)"
    fi
    echo "    Manifest: ${PYCACHE_MANIFEST}"
  else
    echo "  - ${PROJECT_ROOT}/**/__pycache__ (none found)"
  fi

  echo
  echo "Total candidate size: $(numfmt --to=iec-i --suffix=B "${total_bytes}")"
  echo
}

delete_candidates() {
  local path
  echo "Deleting candidates..."
  for path in "${FOUND_PATHS[@]}"; do
    echo "  rm -rf ${path}"
    rm -rf "${path}"
  done

  if [[ -f "${PYCACHE_MANIFEST}" ]]; then
    while IFS= read -r path; do
      [[ -n "${path}" ]] || continue
      echo "  rm -rf ${path}"
      rm -rf "${path}"
    done < "${PYCACHE_MANIFEST}"
  fi

  echo
  echo "Deletion complete."
}

print_optional_cleanup_notes() {
  cat <<'EOF'
Optional cleanup notes:
  - frontend/node_modules is intentionally NOT deleted by this script.
    If you really need the space, remove it manually and reinstall with npm later.
  - runtime/debug is intentionally preserved.
    Optional command to remove debug directories older than 7 days:
      find /home/featurize/work/BS/runtime/debug -mindepth 1 -maxdepth 1 -type d -mtime +7 -print
      find /home/featurize/work/BS/runtime/debug -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +
EOF
}

main() {
  trap cleanup_temp_files EXIT
  print_header
  collect_candidates
  report_candidates

  if [[ "${RUN_DELETE}" == "1" ]]; then
    delete_candidates
  else
    echo "Dry-run only. Set RUN_DELETE=1 to actually remove the paths above."
    echo
  fi

  print_optional_cleanup_notes
}

main "$@"
