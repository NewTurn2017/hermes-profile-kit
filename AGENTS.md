# AGENTS.md — Execution Playbook

> This is the canonical entry point for LLM agents reading this repository.

## Goal

Set up four isolated Hermes profiles via the kit's interactive CLI: `hpk`.

## Single command

```bash
pipx install hermes-profile-kit
hpk setup
```

That's the entire happy path. The wizard:
1. Verifies hermes presence and version (>= manifest.min_hermes_version).
2. For each profile in `manifest.yaml`:
   - Creates it (`hermes profile create <name>`) if absent.
   - Copies `SOUL.md` and `config.yaml` from `profiles/<name>/`.
   - Seeds `.env` from `.env.example` (chmod 600). NEVER overwrites an existing `.env`.
   - Prompts for required + optional tokens with provider-specific guidance.
   - Asks before enabling each recommended plugin (Honcho etc.).
3. Prints a summary listing any `FILL_IN_*` still remaining.

## Hard rules (do not violate)

1. NEVER write tokens to git-tracked files.
2. NEVER guess values. If a token prompt is empty, leave `FILL_IN_*` and report it in the summary.
3. NEVER touch the default profile (`~/.hermes/`).
4. NEVER run `gateway install` without explicit user confirmation.
5. NEVER invoke a hermes command that is not in `build/cmd_index.json`.

## When you need more

- Manifest definition: `manifest.yaml` (v2 schema)
- Spec: `docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md`
- Verified hermes commands: `docs/commands.md` (auto-generated)
- Per-profile customization: edit `profiles/<name>/SOUL.md` or `config.yaml`, then run `hpk setup --force`.
- Troubleshooting: `docs/troubleshooting.md`
