# hermes-profile-kit

> Hermes Agent 의 4개 프로파일(코더 / 비서 / 리서치 / 커뮤니티 봇) 을 한 번에 셋업하는 스타터 키트. 각 프로파일은 **분리된 메모리 · API 키 · 페르소나 · 게이트웨이** 로 동작합니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Hermes ≥ 0.12.0](https://img.shields.io/badge/hermes-%E2%89%A50.12.0-blue.svg)](https://hermes-agent.nousresearch.com/docs/user-guide/profiles)
[![AGENTS.md](https://img.shields.io/badge/AGENTS.md-ready-purple.svg)](AGENTS.md)

---

## 🤖 AI 에이전트로 셋업하기 (가장 쉬운 방법)

이 repo 를 Claude Code, Hermes Agent, Cursor, OpenCode 등 어떤 LLM 에이전트에든 첨부하고 다음 한 문장만 던지세요:

> **"이 repo 의 [`AGENTS.md`](AGENTS.md) 를 따라 내 머신에 Hermes 프로파일을 셋업해줘."**

에이전트는 [`AGENTS.md`](AGENTS.md) → [`manifest.yaml`](manifest.yaml) 순으로 읽고 4개 프로파일을 생성합니다. **시크릿이 필요한 단계에서는 멈추고 사용자에게 물어보도록** 설계되어 있어요.

> 💡 LLM 친화적 설계: `AGENTS.md` 는 단계별 실행 플레이북, `manifest.yaml` 은 머신 리더블 single source of truth, 각 프로파일의 `SOUL.md` 는 페르소나, `config.yaml` 은 설정. 사람용 설명은 이 README, 에이전트용 명령은 `AGENTS.md` 로 분리되어 있습니다.

---

## 사람이 직접 셋업하기

```bash
git clone https://github.com/NewTurn2017/hermes-profile-kit.git
cd hermes-profile-kit
./scripts/install.sh
```

스크립트가 끝나면 `~/.hermes/profiles/<name>/.env` 파일에 API 키만 채워 넣고 `./scripts/verify.sh` 실행하면 끝입니다.

---

## 포함된 프로파일

| 프로파일 | 역할 | 모델 등급 | 채널 | 필요 시크릿 |
|---------|------|----------|------|-------------|
| `coder` | 풀스택 개발 보조 (Next.js, TypeScript, Convex) | Sonnet | CLI | `ANTHROPIC_API_KEY` |
| `assistant` | 일정 · 노트 · 일상 비서 | Sonnet | CLI + Telegram | `ANTHROPIC_API_KEY` (+ Telegram 토큰 선택) |
| `research` | 웹 검색 기반 리서치 (인용 포함) | Opus | CLI | `ANTHROPIC_API_KEY` (+ Brave/Exa 선택) |
| `community-bot` | 한국 개발 커뮤니티 헬퍼 봇 | Haiku (저렴) | Telegram + Discord | `ANTHROPIC_API_KEY` (+ Telegram/Discord 토큰) |

설치 후 각 프로파일은 자기 이름으로 alias 가 잡혀 즉시 호출 가능:

```bash
coder chat                    # 코딩 보조와 대화
assistant gateway start       # 텔레그램 비서 봇 띄우기
research chat -q "Convex 와 Supabase 비교"
community-bot doctor          # 커뮤니티 봇 헬스체크
```

---

## 격리 보장

각 프로파일은 다음을 **완전히 따로** 가집니다:

- `config.yaml`, `.env` (API 키 · 게이트웨이 토큰)
- `SOUL.md` (페르소나)
- 메모리 (MEMORY.md, USER.md, Honcho peer)
- 세션 SQLite, 스킬, 크론, 로그
- 게이트웨이 프로세스 + systemd/launchd 서비스명

같은 슬랙 봇 토큰을 두 프로파일에 실수로 넣으면 두 번째 게이트웨이가 명확한 에러로 거부합니다.

격리되지 **않는** 것: 파일시스템 권한 (모든 프로파일이 사용자 계정과 동일한 권한). 진짜 격리가 필요하면 Docker / Modal / Daytona 백엔드 사용. 자세한 내용은 [docs/concepts.md](docs/concepts.md) 참조.

---

## 디렉터리 구조 (repo map)

```
hermes-profile-kit/
├── AGENTS.md             # 🤖 LLM 에이전트 실행 플레이북 (영문, top-to-bottom)
├── README.md             # 👤 사람용 가이드 (한글)
├── manifest.yaml         # 📋 머신 리더블 single source of truth
├── LICENSE               # MIT
├── .gitignore            # .env / 백업 / OS noise 제외
├── profiles/             # 프로파일 템플릿 (4개)
│   ├── coder/            # SOUL.md + config.yaml + .env.example
│   ├── assistant/
│   ├── research/
│   └── community-bot/
├── scripts/
│   ├── install.sh        # 전체 셋업 (--dry-run, --force, 프로파일 선택 지원)
│   ├── verify.sh         # 모든 프로파일 hermes doctor 헬스체크
│   └── reset.sh          # 키트로 만든 프로파일만 안전하게 삭제
└── docs/
    ├── concepts.md       # 격리 모델, 공유 vs 분리되는 것
    ├── commands.md       # 명령어 치트시트
    ├── gateways.md       # 게이트웨이 · 멀티채널 패턴
    └── troubleshooting.md
```

---

## 커스터마이즈

| 하고 싶은 것 | 수정할 파일 |
|---|---|
| 모델 변경 | `~/.hermes/profiles/<name>/config.yaml` → `model.default` |
| 페르소나 · 톤 변경 | `~/.hermes/profiles/<name>/SOUL.md` |
| 채널 추가 (Telegram 등) | `~/.hermes/profiles/<name>/.env` 에 토큰 추가 후 게이트웨이 재시작 |
| 작업 디렉터리 지정 | `config.yaml` → `terminal.cwd: /absolute/path` |
| 새 프로파일 추가 | `profiles/<name>/` 디렉터리 생성 → `manifest.yaml` 의 `profiles[]` 에 추가 → `./scripts/install.sh` 재실행 |

⚠️ **API 키는 항상 `.env`** 에. `config.yaml` 에는 절대 넣지 마세요. (`.gitignore` 에 등록되어 있어 git 추적되지 않음)

---

## 사전 요구사항

- **Hermes Agent v0.12.0 이상** ([설치 가이드](https://github.com/nousresearch/hermes-agent#installation))
- `bash`, `git`
- `~/.local/bin` 이 `PATH` 에 포함되어 있을 것 (프로파일 alias 가 여기 생성됨)

```bash
# Hermes 미설치 시
curl -fsSL https://raw.githubusercontent.com/nousresearch/hermes-agent/main/scripts/install.sh | bash
```

---

## 자주 묻는 질문

**Q. 이미 다른 프로파일이 있는데 망가지나요?**
A. 아니요. `install.sh` 는 manifest 에 정의된 4개만 다루고, 기존 프로파일이 같은 이름으로 존재하면 `--force` 없이는 `SOUL.md`/`config.yaml` 도 덮어쓰지 않습니다. `.env` 는 절대 덮어쓰지 않습니다.

**Q. reset 하면 다른 프로파일도 삭제되나요?**
A. 아니요. `scripts/reset.sh` 는 이 키트의 manifest 에 있는 프로파일만 삭제하고, 기본 프로파일(`~/.hermes/`) 은 절대 건드리지 않습니다.

**Q. LLM 이 멋대로 시크릿을 채워 넣지 않을까요?**
A. `AGENTS.md` 의 Hard Rule 1: *"Never write secrets to git-tracked files. Only edit `.env` files inside `~/.hermes/profiles/<name>/`."* — 그리고 `.env.example` 의 모든 자리는 `FILL_IN_*` 플레이스홀더라서 에이전트가 단순 복사하면 즉시 사용자에게 채워달라고 멈추도록 설계되어 있습니다.

**Q. 실패하면 어떻게 디버깅?**
A. [`docs/troubleshooting.md`](docs/troubleshooting.md) 또는 `./scripts/verify.sh` 로 어디서 막혔는지 확인.

---

## 라이선스

[MIT](LICENSE). 자유롭게 fork · 수정 · 재배포하세요.

---

## 관련 링크

- 🤖 [AGENTS.md](AGENTS.md) — LLM 에이전트가 읽고 실행하는 플레이북
- 📋 [manifest.yaml](manifest.yaml) — 머신 리더블 메타데이터
- 📚 [docs/concepts.md](docs/concepts.md) — 격리 모델
- 🛠️ [docs/commands.md](docs/commands.md) — 명령어 치트시트
- 📡 [docs/gateways.md](docs/gateways.md) — 게이트웨이 패턴
- 🩺 [docs/troubleshooting.md](docs/troubleshooting.md) — 트러블슈팅
- 🔗 [Hermes Agent 공식 문서](https://hermes-agent.nousresearch.com/docs/user-guide/profiles)
