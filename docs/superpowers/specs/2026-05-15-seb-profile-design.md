# `seb` profile design — Second-Brain Slack Controller

| Field | Value |
|---|---|
| Date | 2026-05-15 |
| Status | Draft (pending implementation plan) |
| Owner | genie |
| Related | `2026-05-15-hermes-profile-kit-v2-design.md` (kit v2 baseline) |

## 1. Purpose

Add a fifth Hermes profile, `seb` (Second Brain), to the kit. The profile turns Slack into a control surface for the user's personal second brain: the Obsidian vault at `/Users/genie/Obsidian/second-brain/second-brain/` plus the user's NotebookLM workspace. The model is OpenAI `gpt-5.5` routed through the user's logged-in Codex CLI session via a local OpenAI-compatible proxy — no separate OpenAI billing key.

The profile is single-user, single-Slack-workspace, and depends on tools the user already operates (`notebooklm` CLI, `codex` CLI, Obsidian vault on local disk).

Non-goals:

- Multi-user / shared workspace support.
- Direct integration with Obsidian's plugin API (filesystem reads/writes only).
- Custom Obsidian or NotebookLM MCP servers (Approach B in brainstorming — explicitly out of scope, defer to future work).
- Other channels (CLI, Telegram, Discord) — Slack only.

## 2. Approach

"Thin profile" pattern matching the existing four kit profiles. Five sets of artifacts are added:

1. `profiles/seb/{SOUL.md, config.yaml, .env.example, README.md}` — the profile template.
2. `manifest.yaml` — register `seb`, extend the schema to accept the new `openai-codex` provider and `slack` channel, bump `schema_version` from 2 to 3.
3. `scripts/codex-openai-proxy/` — a kit-local helper (FastAPI proxy) that exposes `/v1/chat/completions` and shells out to `codex responses`. Optional but installed by default via the new `codex-openai-proxy` plugin entry.
4. `docs/` updates — proxy README, gateway docs note on Slack 3-token setup.
5. This spec.

Safety is enforced in three layers: SOUL.md zone rules (model-level), `gateway.approval_required` categories (Hermes-level), Slack Block Kit Approve/Cancel buttons (UX-level). MCP-level enforcement is deferred.

## 3. File additions and changes

### 3.1 `profiles/seb/SOUL.md`

```markdown
# SOUL — seb (Second Brain)

## Role
당신은 사용자의 second-brain 컨트롤 봇이다. Slack에서 @멘션으로 호출되어
Obsidian vault(`/Users/genie/Obsidian/second-brain/second-brain/`)와
NotebookLM을 양방향으로 다룬다. 검색·정리·요약·NotebookLM 산출물 생성과
저장이 주 업무다. 일반 코딩 보조나 일정 관리는 다른 profile(`coder`,
`assistant`) 영역이며, 이 채널에서 요청이 들어오면 해당 profile로 안내한다.

## Communication style
- 한국어 우선. 사용자 톤(존댓말/반말)을 미러링한다.
- 단답 기본. 풀이는 요청받을 때만.
- 이모지 사용 금지(사용자가 먼저 쓰면 그때만).
- 첫 응답은 한 줄 ack + 다음 행동 예고("vault 검색 중…" 식).

## Vault zones (HARD)
경로는 vault root 기준 상대 경로다. 매 쓰기 작업 전 zone 판정 필수.

| Zone | 경로 | 정책 |
|---|---|---|
| AUTO_WRITE | `raw/**` | 신규 파일 생성·append 자유. 기존 파일 *수정*은 diff 미리보기 1회 출력 후 자동 적용. |
| APPROVE | `wiki/**`, 루트 `*.md` (`index.md`, `log.md`) | 모든 쓰기/이동/삭제는 Slack Block Kit `Approve`/`Cancel` 클릭 필요. |
| LOCKED | `90.*/**`, `_private/**`, `private/**`, `.obsidian/**` | 읽기·쓰기 모두 거부. 사용자가 정확한 경로를 명시해도 거부하고 이유를 설명한다. |

unmatched 경로는 안전 기본값으로 APPROVE 취급.

## NotebookLM operations
- 새 notebook 생성, source 추가, artifact(briefing/audio/study guide/mindmap) 생성은 `notebooklm` skill CLI를 통해 수행한다.
- 생성된 artifact는 항상 `raw/imported/notebooklm/<YYYY-MM-DD>-<slug>/` 아래로 저장(AUTO_WRITE 영역).
- 이미 wiki에 정리된 노트를 source로 쓸 때는 사용자에게 "wiki/<path>를 source로 쓸까요?" 한 줄 확인 후 진행 (읽기지만 사용자 의도 확인).

## Slack 행동규칙
- @멘션이 없는 메시지에는 절대 반응하지 않는다. 쓰레드 내에서는 첫 멘션 이후 자유롭게 응답한다.
- 쓰레드별 컨텍스트는 격리한다. 다른 쓰레드 내용을 가져오지 않는다.
- destructive op(APPROVE zone 쓰기/이동/삭제) 직전에는 다음을 한 메시지로 출력:
  1. 무엇을 할지 한 줄 요약
  2. 영향받는 경로 목록 (≤10개, 더 많으면 처음 10개 + "외 N건")
  3. 변경 diff 또는 dry-run 결과
  4. `Approve` / `Cancel` Block Kit 버튼
- 한 번의 Approve 클릭은 한 번의 op만 실행한다. 배치 처리는 사용자가 명시적으로 "모두 적용"이라고 입력해야 활성화.

## Hard rules
- vault root 밖으로 쓰기 금지.
- LOCKED zone은 어떤 인자가 와도 거부.
- diff/dry-run을 못 만드는 op는 실행 거부하고 사용자에게 이유 설명.
- NotebookLM API 에러는 그대로 노출 (재시도 자동 금지 — 사용자 결정 사항).
- 한 쓰레드에서 동시 진행 중인 op는 1개. 새 요청이 와도 직전 op 완료/취소 후 시작.

## What to remember (MEMORY.md guidance)
- 사용자의 frontmatter 스타일(필수 키, 날짜 포맷).
- 자주 쓰는 태그 taxonomy와 폴더 매핑.
- NotebookLM artifact 선호(언어/길이/포맷).
- 자주 source로 쓰는 도메인/저자.

## What NOT to remember
- 일회성 검색 쿼리.
- 쓰레드 내 임시 결정(쓰레드 자체가 기록임).
```

### 3.2 `profiles/seb/config.yaml`

```yaml
# Hermes profile config — seb (Second Brain)
# Slack-only personal second-brain controller.
# Model: gpt-5.5 via local Codex CLI OAuth proxy (OPENAI_BASE_URL override).

model:
  default: openai/gpt-5.5

auxiliary:
  default: openai/gpt-5.4-mini      # gpt-5.5-mini가 없어 fallback

terminal:
  backend: local

tools:
  enabled:
    - file
    - shell
    - web_search
    - web_fetch
  disabled:
    - image_generation
    - voice
    - cron

gateway:
  approval_required:
    - delete
    - move           # 신규 카테고리 가능성 — 6번 open question 참고
    - mass_message   # community-bot 표기와 일치
    - send_message

concurrency:
  per_thread: 1
  per_profile: 3

rate_limit:
  per_user_per_hour: 60
  per_channel_per_hour: 120

memory:
  built_in:
    nudge_interval_turns: 20
    max_facts: 300

display:
  tool_preview_length: 100
```

### 3.3 `profiles/seb/.env.example`

```bash
# seb profile — environment variables
# Copy to ~/.hermes/profiles/seb/.env and replace FILL_IN.
# This file is gitignored at the kit level. NEVER commit a populated copy.

# --- Required: Slack (Socket Mode, 개인용 단일 워크스페이스) ---
SLACK_BOT_TOKEN=FILL_IN
SLACK_SIGNING_SECRET=FILL_IN
SLACK_APP_TOKEN=FILL_IN

# --- Required: model 경로 ---
OPENAI_BASE_URL=http://localhost:8765/v1
OPENAI_API_KEY=sk-codex-proxy-local

# --- Optional ---
# JINA_API_KEY=FILL_IN
```

### 3.4 `profiles/seb/README.md`

내용 요약 (실제 파일은 plan 단계에서 작성):

- `seb`의 한 줄 정체성, vault 경로, NotebookLM 의존성.
- Slack App 생성 단계별 가이드: scopes(`app_mentions:read`, `chat:write`, `files:read`, `commands` 없음), Socket Mode 활성화, 3종 토큰 발급 위치 스크린샷 텍스트.
- Codex CLI 로그인 확인(`codex auth status`).
- proxy 실행 확인(`curl http://localhost:8765/v1/models`).
- 첫 실행: `seb gateway start` 후 워크스페이스에서 봇 채널 invite → `@seb 안녕` 테스트.

### 3.5 `manifest.yaml` (변경분)

```yaml
schema_version: 3                    # 2 → 3

# upstream/min_hermes_version/등 기존 필드 유지

profiles:
  # ... 기존 coder, assistant, research, community-bot 유지 ...
  - name: seb
    template: profiles/seb
    role: Second-brain controller (Obsidian + NotebookLM via Slack)
    model_tier: openai-codex
    channels: [slack]
    tokens:
      required:
        - { key: SLACK_BOT_TOKEN,       provider: slack,        wizard: slack_app }
        - { key: SLACK_SIGNING_SECRET,  provider: slack,        wizard: slack_app }
        - { key: SLACK_APP_TOKEN,       provider: slack,        wizard: slack_app }
        - { key: OPENAI_BASE_URL,       provider: openai-codex, wizard: codex_proxy }
        - { key: OPENAI_API_KEY,        provider: openai-codex, wizard: codex_proxy, default: "sk-codex-proxy-local" }
      optional:
        - { key: JINA_API_KEY, provider: jina }
    recommended_plugins:
      - { id: codex-openai-proxy, default: true }

plugins:
  # ... 기존 honcho-memory, brave-search-tool 유지 ...
  codex-openai-proxy:
    description: "Local OpenAI-compatible HTTP proxy that routes /v1/chat/completions to the user's logged-in Codex CLI (gpt-5.5 / gpt-5.4-mini). Removes the need for a separate OpenAI billing key."
    upstream_command: null
    install_path: scripts/codex-openai-proxy
    launchd_template: scripts/codex-openai-proxy/launchd.plist.example
    verified_in_upstream: false
    docs: scripts/codex-openai-proxy/README.md
```

스키마 확장 항목:

- `schema_version` enum에 `3` 추가. `hpk`는 v2/v3 모두 로드.
- `model_tier` enum에 `openai-codex` 추가.
- `channels` enum에 `slack` 추가.
- `tokens[].provider` enum에 `slack`, `openai-codex`, `jina` 추가.
- `tokens[].wizard` enum에 `slack_app`, `codex_proxy` 추가.
- `tokens[]`에 `default` 필드 허용 (FILL_IN을 우회할 수 있는 기본값. 보안 민감 키에는 절대 쓰지 않음. 이 spec에서는 proxy 더미 키에만 사용).
- `plugins[].upstream_command`가 `null`일 수 있음 (kit-local 헬퍼).
- `plugins[].install_path`, `plugins[].launchd_template` 신규 키.

### 3.6 `scripts/codex-openai-proxy/`

```
scripts/codex-openai-proxy/
├── proxy.py
├── pyproject.toml
├── README.md
└── launchd.plist.example
```

**`proxy.py` 기능 요약** (구현은 plan 단계):

- FastAPI app, `uvicorn` 실행.
- `POST /v1/chat/completions`: 요청에서 `model`, `messages`, `tools`, `stream` 파싱 → `codex responses --model <name> --input-json -`에 stdin JSON으로 전달 → 응답을 OpenAI Chat Completion 스펙(streaming SSE `data: {choices:[{delta:{content:"..."}}]}` 또는 비스트리밍 단일 JSON)으로 변환해 반환.
- `GET /v1/models`: `{"data":[{"id":"gpt-5.5",...},{"id":"gpt-5.4-mini",...}]}` 정적 응답. 모델 목록은 환경변수 `CODEX_PROXY_MODELS`(콤마 구분, 기본 `gpt-5.5,gpt-5.4-mini`)로 확장 가능.
- Codex 미로그인(`codex auth status` 실패) 시 502 + `{"error":{"message":"Run \`codex auth login\` first","type":"codex_auth_required"}}`.
- 로그: `~/.hermes/profiles/seb/logs/codex-proxy.log`. 회전은 사용자가 logrotate로 처리(별도 코드 없음).
- 포트 기본 8765, `CODEX_PROXY_PORT` 환경변수로 변경 가능.

**한계 (구현에 명시)**:

- Codex CLI의 tool/function-calling 지원 정도가 OpenAI API와 다를 수 있음. v1은 응답에서 `tool_calls` 필드가 비어 있을 수 있으며, Hermes가 OpenAI tool-call에 강하게 의존하는 흐름에서는 일부 기능이 제한됨. plan 단계에서 Hermes의 OpenAI tool 호출 경로를 직접 확인.
- Codex 응답 스트림 포맷 변경 시 proxy가 깨짐. `codex --version`을 CI에서 일일 체크하고 호환 매트릭스를 README에 적시.
- macOS LaunchAgent 템플릿만 동봉. Linux/systemd는 사용자 자작.

**`launchd.plist.example`**: `KeepAlive=true`, `RunAtLoad=true`, `StandardOutPath`/`StandardErrorPath`는 위 로그 경로. 사용자가 `cp ~/Library/LaunchAgents/`로 복사 후 `launchctl load`.

## 4. Data flow

```
Slack 메시지 (@seb …)
  → Hermes Slack adapter (SLACK_APP_TOKEN Socket Mode 연결)
  → seb profile 컨텍스트(memory/tools 로드)
  → 모델 호출: OpenAI SDK가 OPENAI_BASE_URL=http://localhost:8765/v1로 요청
  → proxy.py 수신 → codex CLI subprocess → Codex API (OAuth)
  → 응답 → OpenAI SSE 포맷으로 재패키징 → Hermes → tool 호출/응답 생성
  → Slack 메시지/Block Kit 발신
```

destructive op:

```
모델이 vault write 의도 결정
  → file tool dry-run 실행 (실제 쓰기 없이 diff/계획 생성)
  → Slack에 요약 + 경로 + diff + Approve/Cancel 버튼 게시
  → 사용자 Approve 클릭 → Hermes interaction event
  → seb가 동일 op를 실모드로 1회 실행
```

## 5. Safety model (3 layers)

| Layer | Where | What it enforces |
|---|---|---|
| Model | `SOUL.md` Vault zones + Hard rules | zone 판정, LOCKED 거부, diff/dry-run 의무, 1 op/Approve |
| Hermes | `config.yaml` gateway.approval_required | `delete`, `move`, `mass_message`, `send_message` 카테고리 게이트 |
| UX | Slack Block Kit | 사용자가 클릭하지 않으면 op 실행 안 됨 |

이 세 층은 독립적으로 작동한다. 모델 층이 실수해도 Hermes 카테고리 게이트가 잡고, 둘 다 통과해도 UX 클릭이 마지막 차단막이다. 단, zone 자체는 모델 층에서만 enforced이므로 향후 사고 데이터가 쌓이면 별도 MCP로 끌어올리는 옵션을 검토(Approach B).

## 6. Open questions (plan 단계에서 결정)

1. **Hermes의 OpenAI provider가 `model_tier` 키 외에 model id를 어떻게 받는지** — `openai/gpt-5.5` 같은 슬래시 표기 vs `model.provider`+`model.id` 분리 표기. 업스트림 코드 확인 후 결정.
2. **Hermes의 Slack adapter가 Block Kit `interactivity` 이벤트(버튼 클릭)를 모델 turn으로 라우팅하는 방법** — adapter가 자동 처리하는지, `gateway` 핸들러를 따로 작성해야 하는지.
3. **`hpk setup`이 plugins 중 `install_path` 형 항목을 어떻게 처리할지** — pyproject.toml 기반 venv 생성, `launchctl` 안내 단계의 분리 정도.
4. **Codex CLI의 tool-call 지원 현황** — 현재 Codex가 OpenAI tool 스펙을 그대로 반환하는지, 텍스트 모드만 가능한지.
5. **`gateway.approval_required`에 `move` 카테고리가 실제 존재하는지** — 기존 profile 중 `move`를 쓰는 곳 없음. 업스트림에서 미지원이면 SOUL.md의 모델-층 룰로만 처리하고 config에서 제거.
6. **쓰레드 격리 메커니즘** — SOUL.md는 "쓰레드별 컨텍스트는 격리한다"고 선언하나, Hermes 세션 모델이 Slack 쓰레드 ts(thread_timestamp)와 어떻게 매핑되는지 확인 필요. adapter가 자동 처리하지 않으면 봇 측에서 명시적 세션 키잉 로직 필요.

이 6개는 spec 자체를 막지 않는다. 모두 plan 단계에서 코드 확인으로 닫는다.

## 7. Out of scope

- 별도 obsidian-mcp / notebooklm-mcp 서버 작성.
- gateway 외 채널(CLI, Telegram, Discord) 활성화.
- 다른 profile에서 codex-openai-proxy 공유 사용(이 spec은 `seb` 단독 가정. 공유는 향후 별도 spec).
- `90. Private` 같은 LOCKED zone 폴더 자동 생성(사용자 vault에 현재 없음. 정책만 선언).
- 자동 정기 다이제스트(cron) — `cron` tool은 disabled.

## 8. Acceptance

이 spec은 다음을 모두 만족할 때 구현 가능하다고 본다:

- `hpk setup seb` 실행 시 4개 토큰을 받고 proxy 설치/실행 안내 후 `seb gateway start`가 성공.
- Slack에서 `@seb 인박스에 'AI 2027 검토' 노트 하나 만들어줘` → `raw/inbox/` 또는 `raw/`에 노트 생성, AUTO_WRITE 흐름.
- `@seb wiki/concepts/transformer.md 제목을 attention.md로 바꿔줘` → Approve/Cancel 카드 게시, Approve 후 적용.
- `@seb 90.private/X 읽어줘` → 거부 + 이유 설명.
- `@seb AI 관련 wiki 노트로 NotebookLM 브리핑 만들어줘` → 후보 노트 목록 → 확인 후 NotebookLM 생성 → `raw/imported/notebooklm/<date>-ai-briefing/`에 결과 저장.
- 모든 위 흐름이 별도 OpenAI API 키 없이 Codex 구독으로만 동작.
