# hermes-profile-kit

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 를 위한 인터랙티브 멀티 프로파일 셋업 도구.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml)

> 🇺🇸 [English README](README.md)

## 빠른 시작

```bash
pipx install hermes-profile-kit
hpk setup
```

위저드가 4개 프로파일(`coder` / `assistant` / `research` / `community-bot`) 을 순서대로 안내하고, 채널별로 필요한 토큰(Anthropic, Telegram, Slack, Discord, Brave, Exa) 을 물어본 뒤, 추천 플러그인(Honcho 메모리, Brave 검색 툴) 을 선택적으로 활성화한다.

## hpk 가 하는 것 (그리고 하지 않는 것)

- ✅ 격리된 Hermes 프로파일 4개를 생성·설정한다.
- ✅ BotFather, Slack 앱, Discord devportal 흐름을 단계별로 안내한다.
- ✅ `.env` 파일을 원자적·멱등적으로 쓴다 (chmod 600). 다시 실행해도 안전하다.
- ✅ GitHub Actions 로 매일 upstream 을 동기화해 키트가 Hermes 변경사항을 따라간다.
- ❌ Hermes 자체는 설치하지 않는다 ([Hermes 설치 문서](https://github.com/NousResearch/hermes-agent#installation) 참조).
- ❌ 게이트웨이 서비스를 자동으로 띄우지 않는다.
- ❌ upstream 에서 확인되지 않은 hermes 명령은 절대 호출하지 않는다.

## 어떻게 항상 올바른 상태를 유지하나

`hpk` 는 upstream argparse 트리에서 관찰되지 않은 hermes 명령을 절대 임베드하지 않는다. CI 가 매일 `hermes_cli/main.py` 를 AST 파싱하고, `docs/commands.md` 와 `build/cmd_index.json` 을 재생성하며, 드리프트가 감지되면 PR 을 열어준다.

## 프로파일

| 프로파일 | 역할 | 모델 등급 | 채널 |
|---|---|---|---|
| `coder` | 풀스택 개발 보조 | Sonnet | CLI |
| `assistant` | 일상 개인 비서 | Sonnet | CLI + Telegram |
| `research` | 웹 검색 기반 리서치 | Opus | CLI |
| `community-bot` | 한국 개발 커뮤니티 헬퍼 | Haiku | Telegram + Discord |

## 커스터마이징

| 목표 | 편집 위치 |
|---|---|
| 모델 변경 | `~/.hermes/profiles/<name>/config.yaml` |
| 페르소나 변경 | `~/.hermes/profiles/<name>/SOUL.md` |
| 새 프로파일 추가 | `profiles/<name>/{SOUL.md,config.yaml,.env.example}` + `manifest.yaml` 에 등록 → `hpk setup` |
| 플러그인 활성화 | `manifest.yaml` 의 `plugins:` 에 추가하고 `recommended_plugins` 에서 참조 |

API 키는 `~/.hermes/profiles/<name>/.env` 에 들어간다. `chmod 600` 으로 보호된 평문 파일이고, 키트는 일부러 암호화하는 척하지 않는다.

## 명령어

```bash
hpk setup [profile...]    # 인터랙티브 위저드
hpk verify                # doctor + FILL_IN 스캔
hpk doctor                # hpk 자체 헬스체크
hpk reset [profile...]    # 키트가 만든 프로파일 제거
hpk plugin list           # recommended_plugins 보기
hpk sync --dry-run        # 로컬 드리프트 체크
```

## 라이선스

MIT. `LICENSE` 참조.
