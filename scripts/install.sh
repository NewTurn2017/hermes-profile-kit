#!/usr/bin/env bash
# hermes-profile-kit installer
#
# Usage:
#   ./scripts/install.sh                # install all profiles in manifest
#   ./scripts/install.sh coder research # install only specified profiles
#   ./scripts/install.sh --dry-run      # show what would happen, don't change anything
#   ./scripts/install.sh --force        # overwrite SOUL.md and config.yaml
#                                       # (.env is always preserved)
#
# Exit codes:
#   0 = success
#   1 = precondition failed (hermes not installed, etc.)
#   2 = profile creation failed
#   3 = template missing or malformed

set -euo pipefail

# --- Locate repo root regardless of where script is invoked from ---
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$( cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd )"
cd "$REPO_ROOT"

# --- Args ---
DRY_RUN=0
FORCE=0
SELECTED_PROFILES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force)   FORCE=1;   shift ;;
    -h|--help)
      sed -n '2,15p' "$0"; exit 0 ;;
    *) SELECTED_PROFILES+=("$1"); shift ;;
  esac
done

# --- Helpers ---
log()  { printf "\033[1;34m[install]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2; }
run()  {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf "  \033[2m[dry-run] %s\033[0m\n" "$*"
  else
    eval "$@"
  fi
}

# --- Preconditions ---
log "Checking preconditions..."

if ! command -v hermes >/dev/null 2>&1; then
  err "hermes not found on PATH. Install it first:"
  err "  curl -fsSL https://raw.githubusercontent.com/nousresearch/hermes-agent/main/scripts/install.sh | bash"
  exit 1
fi

HERMES_VERSION=$(hermes --version 2>/dev/null | head -n1 || echo "unknown")
log "Found: $HERMES_VERSION"

if ! echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
  warn "$HOME/.local/bin is not on your PATH. Profile aliases (e.g. 'coder chat') won't work."
  warn "Add this to your ~/.bashrc or ~/.zshrc:"
  warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

if [[ ! -f manifest.yaml ]]; then
  err "manifest.yaml not found. Are you running this from inside the repo?"
  exit 1
fi

# --- Parse profile names from manifest ---
# Minimal awk parser — avoids needing yq/python as a dependency.
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

if [[ ${#ALL_PROFILES[@]} -eq 0 ]]; then
  err "No profiles found in manifest.yaml"
  exit 3
fi

log "Profiles defined in manifest: ${ALL_PROFILES[*]}"

# --- Determine which to install ---
if [[ ${#SELECTED_PROFILES[@]} -eq 0 ]]; then
  TARGETS=("${ALL_PROFILES[@]}")
else
  # Validate every selected name is in the manifest
  for p in "${SELECTED_PROFILES[@]}"; do
    found=0
    for known in "${ALL_PROFILES[@]}"; do
      [[ "$p" == "$known" ]] && { found=1; break; }
    done
    if [[ $found -eq 0 ]]; then
      err "Profile '$p' not found in manifest. Known: ${ALL_PROFILES[*]}"
      exit 3
    fi
  done
  TARGETS=("${SELECTED_PROFILES[@]}")
fi

log "Will install: ${TARGETS[*]}"
[[ $DRY_RUN -eq 1 ]] && log "DRY RUN — no changes will be made"
[[ $FORCE   -eq 1 ]] && log "FORCE mode — SOUL.md and config.yaml will be overwritten"

# --- Track outcomes for final summary ---
CREATED=()
SKIPPED_EXISTS=()
FAILED=()
ENV_NEEDS_FILL=()

# --- Install loop ---
for profile in "${TARGETS[@]}"; do
  echo
  log "=== Profile: $profile ==="

  TEMPLATE_DIR="profiles/$profile"
  if [[ ! -d "$TEMPLATE_DIR" ]]; then
    err "Template directory missing: $TEMPLATE_DIR"
    FAILED+=("$profile")
    continue
  fi

  for required in SOUL.md config.yaml .env.example; do
    if [[ ! -f "$TEMPLATE_DIR/$required" ]]; then
      err "Template missing file: $TEMPLATE_DIR/$required"
      FAILED+=("$profile")
      continue 2
    fi
  done

  PROFILE_HOME="$HOME/.hermes/profiles/$profile"

  # 1. Create profile if needed
  if hermes profile show "$profile" >/dev/null 2>&1; then
    log "Profile '$profile' already exists — skipping create"
    SKIPPED_EXISTS+=("$profile")
  else
    log "Creating profile '$profile'..."
    run "hermes profile create '$profile'"
    CREATED+=("$profile")
  fi

  # Re-resolve home (might not exist in dry-run)
  if [[ $DRY_RUN -eq 0 ]]; then
    if [[ ! -d "$PROFILE_HOME" ]]; then
      err "Profile home not found after create: $PROFILE_HOME"
      FAILED+=("$profile")
      continue
    fi
  fi

  # 2. Apply SOUL.md and config.yaml
  for f in SOUL.md config.yaml; do
    target="$PROFILE_HOME/$f"
    if [[ -f "$target" && $FORCE -eq 0 && " ${SKIPPED_EXISTS[*]:-} " == *" $profile "* ]]; then
      warn "  $f exists; --force not given — leaving alone"
    else
      log "  Applying template: $f"
      run "cp '$TEMPLATE_DIR/$f' '$target'"
    fi
  done

  # 3. Seed .env only if absent (NEVER overwrite secrets)
  env_target="$PROFILE_HOME/.env"
  if [[ -f "$env_target" ]]; then
    log "  .env exists — preserving"
  else
    log "  Seeding .env from .env.example"
    run "cp '$TEMPLATE_DIR/.env.example' '$env_target'"
    run "chmod 600 '$env_target'"
  fi

  # 4. Check for FILL_IN placeholders
  if [[ $DRY_RUN -eq 0 ]] && grep -q "FILL_IN" "$env_target" 2>/dev/null; then
    ENV_NEEDS_FILL+=("$profile")
  fi
done

# --- Summary ---
echo
echo "=================================================="
log "Install summary"
echo "=================================================="
echo "  Created:                ${CREATED[*]:-(none)}"
echo "  Skipped (existed):      ${SKIPPED_EXISTS[*]:-(none)}"
echo "  Failed:                 ${FAILED[*]:-(none)}"
echo

if [[ ${#ENV_NEEDS_FILL[@]} -gt 0 ]]; then
  echo "==================================================="
  warn "ACTION REQUIRED — Fill in API keys"
  echo "==================================================="
  for p in "${ENV_NEEDS_FILL[@]}"; do
    env_file="$HOME/.hermes/profiles/$p/.env"
    echo "  $env_file"
    grep -n "FILL_IN" "$env_file" 2>/dev/null | sed 's/^/    /' || true
    echo
  done
  echo "Edit each .env above, replace FILL_IN with real values, then run:"
  echo "  ./scripts/verify.sh"
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  exit 2
fi

echo
log "Next steps:"
echo "  ./scripts/verify.sh           # health check all profiles"
echo "  coder chat                    # try the coder profile"
echo "  hermes profile list           # see all profiles"
