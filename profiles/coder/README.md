# coder profile

Full-stack development assistant. Sonnet-class. CLI only.

## What this profile is good at
- Writing and reviewing code in TypeScript-heavy stacks (Next.js, React, Convex, Tailwind)
- Debugging with file context
- Suggesting library/tool choices with tradeoffs

## What this profile is NOT for
- Daily scheduling, reminders → use `assistant`
- Deep web research → use `research`
- Public chat bots → use `community-bot` template

## Customization

### Change the default working directory
```yaml
# in ~/.hermes/profiles/coder/config.yaml
terminal:
  cwd: /Users/you/code/main-project
```

### Change the model
```bash
coder config set model.default anthropic/claude-opus-4-7
```

### Add web search providers for better tool use
```bash
echo "BRAVE_SEARCH_API_KEY=sk-..." >> ~/.hermes/profiles/coder/.env
```

## First run

```bash
coder chat
> "이 디렉터리에 README 만들어줘"
```

If the profile feels too restrictive, edit `~/.hermes/profiles/coder/SOUL.md` directly.
