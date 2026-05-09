#!/usr/bin/env bash
# Safely delete profiles created by this kit.
#
# Usage:
#   ./scripts/reset.sh                # interactive: confirm each profile
#   ./scripts/reset.sh --yes          # delete all without prompting (DANGEROUS)
#   ./scripts/reset.sh coder          # delete only the coder profile
#   ./scripts/reset.sh --backup       # export profile to tar.gz before deleting
#
# This script will NEVER touch the default profile (~/.hermes itself).

set -uo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$( cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd )"
cd "$REPO_ROOT"

log()  { printf "\033[1;34m[reset]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }

YES=0
BACKUP=0
SELECTED=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)    YES=1; shift ;;
    --backup) BACKUP=1; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) SELECTED+=("$1"); shift ;;
  esac
done

# Parse manifest profiles (only delete profiles defined here, never others)
ALL_PROFILES=()
while IFS= read -r line; do
  ALL_PROFILES+=("$line")
done < <(awk '
  /^profiles:/ { in_profiles=1; next }
  in_profiles && /^[a-z_]+:/ && !/^  / { in_profiles=0 }
  in_profiles && /^  - name:/ {
    sub(/^  - name:[[:space:]]*/, "")
    print
  }
' manifest.yaml)

if [[ ${#SELECTED[@]} -eq 0 ]]; then
  TARGETS=("${ALL_PROFILES[@]}")
else
  for p in "${SELECTED[@]}"; do
    found=0
    for known in "${ALL_PROFILES[@]}"; do
      [[ "$p" == "$known" ]] && { found=1; break; }
    done
    if [[ $found -eq 0 ]]; then
      warn "'$p' is not in this kit's manifest. Refusing to delete profiles outside the kit."
      exit 1
    fi
  done
  TARGETS=("${SELECTED[@]}")
fi

warn "About to delete the following profiles:"
for p in "${TARGETS[@]}"; do
  echo "  - $p"
done
warn "This is IRREVERSIBLE. Memory, sessions, skills, and cron jobs will be gone."

if [[ $YES -eq 0 ]]; then
  read -r -p "Type 'yes' to proceed: " confirm
  if [[ "$confirm" != "yes" ]]; then
    log "Aborted."
    exit 0
  fi
fi

mkdir -p "$HOME/hermes-backups"

for profile in "${TARGETS[@]}"; do
  log "Processing: $profile"

  if ! hermes profile show "$profile" >/dev/null 2>&1; then
    warn "  '$profile' does not exist — skipping"
    continue
  fi

  if [[ $BACKUP -eq 1 ]]; then
    backup_file="$HOME/hermes-backups/${profile}-$(date +%Y%m%d-%H%M%S).tar.gz"
    log "  Backing up to $backup_file"
    hermes profile export "$profile" -o "$backup_file" || warn "  backup failed"
  fi

  log "  Deleting..."
  hermes profile delete "$profile" --yes || warn "  delete may have partially failed"
done

log "Reset complete. The default profile (~/.hermes) was not touched."
