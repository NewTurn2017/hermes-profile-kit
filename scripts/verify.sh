#!/usr/bin/env bash
# Verify all profiles defined in manifest.yaml are healthy.
#
# Usage:
#   ./scripts/verify.sh                # check all manifest profiles
#   ./scripts/verify.sh coder research # check specific profiles
#
# Exit codes:
#   0 = all profiles pass
#   1 = one or more profiles have issues

set -uo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$( cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd )"
cd "$REPO_ROOT"

log()  { printf "\033[1;34m[verify]\033[0m %s\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
fail() { printf "  \033[1;31m✗\033[0m %s\n" "$*"; }

if ! command -v hermes >/dev/null 2>&1; then
  fail "hermes not on PATH"
  exit 1
fi

# Parse manifest
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

# Determine targets
if [[ $# -gt 0 ]]; then
  TARGETS=("$@")
else
  TARGETS=("${ALL_PROFILES[@]}")
fi

OVERALL_PASS=1

for profile in "${TARGETS[@]}"; do
  echo
  log "=== $profile ==="

  # 1. Profile exists?
  if ! hermes profile show "$profile" >/dev/null 2>&1; then
    fail "profile does not exist (run install.sh)"
    OVERALL_PASS=0
    continue
  fi
  ok "profile exists"

  PROFILE_HOME="$HOME/.hermes/profiles/$profile"

  # 2. Required template files present?
  for f in SOUL.md config.yaml .env; do
    if [[ -f "$PROFILE_HOME/$f" ]]; then
      ok "$f present"
    else
      fail "$f missing"
      OVERALL_PASS=0
    fi
  done

  # 3. .env has no FILL_IN placeholders for required keys?
  if grep -q "^[A-Z_]*=FILL_IN" "$PROFILE_HOME/.env" 2>/dev/null; then
    fail ".env has unfilled FILL_IN placeholders:"
    grep -n "^[A-Z_]*=FILL_IN" "$PROFILE_HOME/.env" | sed 's/^/    /'
    OVERALL_PASS=0
  else
    ok ".env has no FILL_IN placeholders"
  fi

  # 4. .env has restrictive perms?
  if [[ -f "$PROFILE_HOME/.env" ]]; then
    perms=$(stat -c "%a" "$PROFILE_HOME/.env" 2>/dev/null || stat -f "%A" "$PROFILE_HOME/.env" 2>/dev/null)
    if [[ "$perms" == "600" ]]; then
      ok ".env permissions are 600"
    else
      fail ".env permissions are $perms (should be 600)"
      OVERALL_PASS=0
    fi
  fi

  # 5. hermes doctor for this profile
  log "Running hermes -p $profile doctor..."
  if hermes -p "$profile" doctor 2>&1 | tee /tmp/hermes-doctor-$profile.log | grep -qi "error\|missing\|fail"; then
    fail "hermes doctor reports issues — see /tmp/hermes-doctor-$profile.log"
    OVERALL_PASS=0
  else
    ok "hermes doctor passed"
  fi
done

echo
if [[ $OVERALL_PASS -eq 1 ]]; then
  log "All profiles passed verification."
  exit 0
else
  log "One or more profiles have issues. Fix above and re-run."
  exit 1
fi
