# hermes-profile-kit

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 를 위한 인터랙티브 멀티 프로파일 셋업 도구.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/hermes-profile-kit.svg)](https://pypi.org/project/hermes-profile-kit/)
[![CI](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml)

> 🇺🇸 [English README](README.md)

## ⚡ 2분 설치 (Claude Code / Codex)

Claude Code 또는 `codex`에 그대로 붙여넣으세요. 토큰 한 번 입력하면 끝.

> 이 머신에 `hermes-profile-kit`으로 Hermes **`<PROFILE>`** 프로파일을 설치해.
> 이건 결정론적 CLI 설치 작업이지 소프트웨어 설계 작업이 아니야.
> `brainstorming`, `writing-plans`, `test-driven-development`,
> `requesting-code-review` skill을 호출하지 마 — 사용자가 명시적으로
> 그렇게 지시했어. 필요한 토큰을 한 번에 물어보고, 그다음에 다음을 실행해:
>
>     pipx install --upgrade hermes-profile-kit
>     hpk setup <PROFILE> --non-interactive \
>       --token KEY1=VALUE1 --token KEY2=VALUE2 ... \
>       --accept-plugin <plugin-id>
>     hpk verify <PROFILE>
>
> 프로파일별 필수 토큰과 플러그인 id는
> https://github.com/NewTurn2017/hermes-profile-kit/blob/main/manifest.yaml
> 에 있어. verify 출력을 보고해.

**라이브 예시 — `seb` (Codex 경유 Slack 세컨드브레인):** [AGENTS.md → seb fast-path](AGENTS.md#fast-path-seb) 참고.

## TL;DR — 어디서부터 읽어야 하나

| 당신은… | 여기로 |
|---|---|
| 👤 키트를 처음 써보는 사람 | ↓ [사람은 이렇게](#사람은-이렇게) |
| 🤖 LLM 에이전트 (Claude / Cursor / Hermes 자신) | ↓ [LLM은 이렇게](#llm은-이렇게) + 정본 [AGENTS.md](AGENTS.md) |
| 🔧 레포 메인테이너 | ↓ [이 레포 운영하기](#이-레포-운영하기) |

## Repository facts (machine-readable)

```yaml
package: hermes-profile-kit
version: 3.1.0
schema_version: 3
language: python>=3.10
cli_entrypoint: hpk
manifest_path: manifest.yaml
profiles_path: profiles/
verified_commands_index: build/cmd_index.json   # CI-managed
verified_commands_doc:   docs/commands.md       # CI-managed
upstream:
  repo: https://github.com/NousResearch/hermes-agent
  pinned_commit: 5621fc44     # current; see manifest.yaml for live value
hard_rules_doc: AGENTS.md     # canonical playbook for LLM agents
```

## 사람은 이렇게

### 사전 준비
- Python ≥ 3.10
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) 설치 (바이너리가 PATH 에 있고, 버전 ≥ 0.12.0)
- `~/.local/bin` 이 PATH 에 포함되어 있을 것 (프로파일 alias 용)

### 설치 + 실행
```bash
pipx install hermes-profile-kit
hpk setup
```

위저드는 `manifest.yaml` 에 정의된 각 프로파일을 순서대로 안내한다.
1. Hermes 가 설치되어 있고 충분히 최신 버전인지 확인한다.
2. 프로파일이 없으면 생성한다.
3. 키트 템플릿에서 `SOUL.md` 와 `config.yaml` 을 복사한다.
4. `.env.example` 을 바탕으로 `.env` 를 시드한다 (mode `0600`, 기존 파일은 절대 덮어쓰지 않음).
5. 필수·선택 토큰을 프로바이더별 가이드와 함께 묻는다 (BotFather URL, Slack 앱 문서 등).
6. 추천 플러그인(Honcho 메모리, Brave 검색 등)을 활성화할지 항목별로 묻는다.

### 다시 실행해도 안전
`hpk setup` 은 멱등적이다. 기존 `.env` 파일은 보존되고, 이미 만들어진 프로파일은 다시 생성되지 않는다.

### 프로파일 커스터마이징
| 목표 | 편집 위치 |
|---|---|
| 모델 변경 | `~/.hermes/profiles/<name>/config.yaml` |
| 페르소나 변경 | `~/.hermes/profiles/<name>/SOUL.md` |
| 새 프로파일 추가 | `profiles/<name>/{SOUL.md,config.yaml,.env.example}` + `manifest.yaml` 에 항목 추가 → `hpk setup` |
| 템플릿 강제 덮어쓰기 | `hpk setup --force` |

API 키는 `~/.hermes/profiles/<name>/.env` 에 들어간다 (`chmod 600` 의 평문 파일). 키트는 일부러 암호화하는 척하지 않는다.

## LLM은 이렇게

**정본 플레이북:** [AGENTS.md](AGENTS.md). 이것부터 읽는다.

### 어디를 봐야 하나 (순서대로)
1. `AGENTS.md` — 하드 룰, 단일 명령 해피 패스.
2. `manifest.yaml` — 프로파일·토큰·플러그인의 선언적 진실 공급원.
3. `docs/commands.md` (자동 생성) — 키트가 호출할 수 있는 모든 Hermes 명령.
4. `build/cmd_index.json` — 같은 데이터의 프로그래매틱 매칭용 구조 버전.
5. `src/hpk/` — 구현체. 레이아웃은 `docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md` 에 있다.

### 하드 룰 (위반 금지)
1. git 추적 파일에 시크릿을 절대 쓰지 않는다. 토큰은 `~/.hermes/profiles/<name>/.env` (mode 0600, `.env` 로 gitignore) 에만 들어간다.
2. 토큰 값을 절대 추측하지 않는다. 빈 입력 → `FILL_IN_*` 그대로 두고 요약에 표시한다.
3. 기본 Hermes 프로파일(`~/.hermes/profiles/` 가 아닌 `~/.hermes/` 루트) 은 절대 건드리지 않는다.
4. `build/cmd_index.json` 에 없는 Hermes 명령은 절대 호출하지 않는다.
5. `gateway install` 같은 사이드이펙트 명령은 사람의 명시적 승인 없이 절대 실행하지 않는다.

### 자주 쓰는 호출
```bash
hpk doctor                 # hpk 자체 상태 점검 (hermes 존재, manifest 유효성)
hpk verify [profile...]    # 프로파일별 `hermes doctor` + FILL_IN 스캔
hpk plugin list            # 프로파일별 recommended_plugins 보기
hpk setup --skip-tokens    # base + 플러그인만, 토큰 입력은 건너뛴다
hpk setup --skip-plugins   # base + 토큰만, 플러그인 질문은 건너뛴다
```

### 종료 코드 맵 (`hpk setup` / preflight)
| Exit | 의미 |
|---|---|
| 0 | 성공 |
| 10 | hermes 가 설치되어 있지 않음 |
| 11 | hermes 버전이 `min_hermes_version` 보다 낮음 |
| 30 | 그 외 preflight 오류 / verify 에서 FILL_IN 또는 doctor 실패 발견 |
| 40 | manifest 가 유효하지 않거나 알 수 없는 plugin id |

## 프로파일

| 프로파일 | 역할 | 모델 등급 | 채널 | 추천 플러그인 |
|---|---|---|---|---|
| `coder` | 풀스택 개발 보조 | Sonnet | CLI | — |
| `assistant` | 일상 개인 비서 | Sonnet | CLI + Telegram | Honcho |
| `research` | 웹 검색 기반 리서치 | Opus | CLI | Honcho, Brave search |
| `community-bot` | 한국 개발 커뮤니티 헬퍼 | Haiku | Telegram + Discord | — |
| `seb` | 세컨드 브레인 컨트롤러 (Slack 통해 Obsidian + NotebookLM) | openai-codex | Slack | codex-openai-proxy |

## 플러그인

| 플러그인 | 종류 | 하는 일 |
|---|---|---|
| `honcho-memory` | Hermes-upstream | Honcho(Plastic Labs) 기반 외부 장기 메모리. |
| `brave-search-tool` | Hermes-upstream | Brave Search API 기반 웹 검색 툴. |
| `codex-openai-proxy` | **Kit-local** (`install_path`) | `codex` CLI 에 대한 로컬 OpenAI 호환 HTTP 브리지 — `seb`(그리고 다른 openai-codex 등급 프로파일)이 Codex 를 OpenAI 호환 백엔드처럼 쓸 수 있게 해준다. |

Hermes-upstream 플러그인은 `build/cmd_index.json` 으로 검증된 `hermes` 서브커맨드를 통해 동작한다. Kit-local 플러그인은 `scripts/<plugin-id>/` 에 있고 `plugin.install_path` 를 통해 위저드에 연결된다.

## 명령어 치트시트

```bash
hpk setup [profile...]                # 인터랙티브 위저드
hpk verify [profile...]               # hermes doctor + FILL_IN 스캔
hpk doctor                            # hpk 자체 헬스체크
hpk reset [profile...] --yes          # 키트가 만든 프로파일 제거
hpk plugin list                       # 추천 플러그인 목록
hpk plugin enable PROFILE PLUGIN_ID
hpk plugin disable PROFILE PLUGIN_ID  # 현재는 수동 가이드 스텁
hpk sync --upstream PATH [--dry-run]  # 로컬 드리프트 체크 (CI 가 매일 수행)
```

## 이 레포 운영하기

메인테이너용 — 다음 상황에서 무엇을 해야 하는가.

### …upstream Hermes 가 새 커밋을 올렸다
- 매일 자동: CI 가 처리한다 (`.github/workflows/upstream-sync.yml` 이 매일 06:00 UTC 에 돌면서 upstream 을 클론하고, `build/cmd_index.json` + `docs/commands.md` 를 재생성하고, `manifest.yaml` 의 `upstream.pinned_*` 를 갱신하고, 드리프트가 있으면 PR 을 연다).
- 수동:
  ```bash
  git clone https://github.com/NousResearch/hermes-agent /tmp/hermes
  hpk sync --upstream /tmp/hermes               # 체크
  python scripts/regen_docs.py --upstream /tmp/hermes \
    --out build/cmd_index.json --docs docs/commands.md --pinned-commit "$(git -C /tmp/hermes rev-parse --short HEAD)"
  python scripts/update_manifest_pin.py \
    --commit ... --version ... --verified-at ...
  ```

### …새 버전을 릴리스하고 싶다
1. `pyproject.toml` 과 `src/hpk/__init__.py` 의 `version` 을 올린다 (반드시 일치).
2. `CHANGELOG.md` 를 갱신한다 (Keep-a-Changelog 포맷).
3. 커밋 후 `main` 에 푸시한다.
4. 태깅: `git tag -a v<ver> -m "..." && git push origin v<ver>`.
5. `.github/workflows/release.yml` 이 Trusted Publisher 로 PyPI 에 빌드·발행한다 (이미 설정되어 있음).

### …CI 가 실패한다
- 매트릭스: Linux 의 Python 3.10 / 3.11 / 3.12. 단계: `pip install -e ".[dev]"` → `ruff check` → `mypy` → `pytest`.
- 로컬 재현:
  ```bash
  python -m venv .venv && source .venv/bin/activate
  pip install -e ".[dev]"
  ruff check src tests scripts
  mypy src/hpk
  pytest -v
  ```

### …새 프로파일 / 플러그인 / 토큰 프로바이더를 추가한다
| 추가 항목 | 손대야 할 파일 |
|---|---|
| 프로파일 | `profiles/<name>/{SOUL.md,config.yaml,.env.example}` + `manifest.yaml` 의 `profiles:` 항목 |
| Hermes-upstream 플러그인 | `manifest.yaml` 의 `plugins:` 에 추가하고, `upstream_command` 가 `build/cmd_index.json` 의 항목과 일치해야 한다 |
| Kit-local 플러그인 | `scripts/<plugin-id>/` 추가 + manifest 항목에서 `upstream_command` 대신 `install_path` 사용 |
| 토큰 프로바이더 | `src/hpk/tokens/<provider>.py` 에 `Handler` 를 두고 `src/hpk/tokens/__init__.py` 에 등록 |

### 로컬 프리커밋 게이트
기본 git 훅은 설치되지 않는다. 푸시 전에 실행한다:
```bash
ruff check src tests scripts && ruff format --check src tests scripts && mypy src/hpk && pytest
```

## 트러블슈팅

| 증상 | 가능한 원인 | 해결 |
|---|---|---|
| preflight 에서 `HermesNotInstalledError` | `hermes` 가 PATH 에 없음 | hermes-agent 설치 후 PATH 등록 |
| `HermesVersionTooOldError` | 설치된 Hermes 가 `manifest.min_hermes_version` 보다 낮음 | Hermes 업그레이드 |
| `~/.local/bin not on PATH` 경고 | 셸 PATH 에 빠져 있음 | 셸 rc 에 `export PATH="$HOME/.local/bin:$PATH"` 추가 |
| `hpk verify` 에서 `FILL_IN` 보고 | 토큰이 아직 플레이스홀더 | `~/.hermes/profiles/<n>/.env` 편집하거나 `hpk setup` 재실행 |
| `manifest invalid` | YAML / 스키마 불일치 | `schema_version: 3` 확인, `python -c "from hpk.manifest import load_manifest; from pathlib import Path; load_manifest(Path('manifest.yaml'))"` 실행 |
| `release.yml` 이 `invalid-publisher` 로 실패 | 이 레포에 대해 PyPI Trusted Publisher 가 등록되어 있지 않음 | https://pypi.org/manage/account/publishing/ 에서 설정 |

## 아키텍처

```text
                          ┌─────────────────────────┐
                          │     manifest.yaml       │  (declarative source of truth)
                          │   schema_version: 3     │
                          └────────────┬────────────┘
                                       │ parses
                                       ▼
┌─────────────────┐         ┌────────────────────────┐         ┌──────────────────┐
│  hpk (Click)    │ ──────▶ │ hpk.wizard / verify    │ ──────▶ │ hpk.hermes       │ ─▶ hermes (subprocess)
│  setup/verify/  │         │ phase A (base)         │         │ run_profile_*    │
│  doctor/plugin/ │         │ phase B (tokens)       │         │ run_doctor       │
│  reset/sync     │         │ phase C (plugins)      │         │ run_raw          │
└─────────────────┘         └────────────────────────┘         └──────────────────┘
                                       │
                                       │ asks
                                       ▼
                          ┌─────────────────────────┐
                          │  hpk.tokens.<provider>  │ (anthropic, slack, telegram, discord, brave, exa, openai-codex)
                          └─────────────────────────┘

CI loop (daily):
  upstream-sync.yml → clone hermes-agent → scripts/regen_docs.py (AST-walks hermes_cli/main.py via hpk.codegen.argparse_walker)
                  → build/cmd_index.json + docs/commands.md → drift PR
```

## 링크

- 📖 [AGENTS.md](AGENTS.md) — 정본 LLM 플레이북
- 📋 [CHANGELOG.md](CHANGELOG.md) — 버전 히스토리 (Keep-a-Changelog)
- 🧱 [docs/concepts.md](docs/concepts.md) — Hermes 프로파일 격리 모델
- 🔧 [docs/commands.md](docs/commands.md) — 자동 생성된 검증된 Hermes 명령
- 🛠️ [docs/troubleshooting.md](docs/troubleshooting.md) — 확장 트러블슈팅
- 📐 [docs/superpowers/specs/](docs/superpowers/specs/) — 설계 스펙 (v2 + seb 프로파일)
- 📝 [docs/superpowers/plans/](docs/superpowers/plans/) — 구현 계획
- 🐍 [PyPI: hermes-profile-kit](https://pypi.org/project/hermes-profile-kit/)
- 🏠 [Hermes Agent (upstream)](https://github.com/NousResearch/hermes-agent)

## 라이선스

MIT. [LICENSE](LICENSE) 참조.
