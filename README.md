# 🛡️ cross-check: Enterprise Security & Stability Gatekeeper

> **엔터프라이즈 온프레미스 보안 솔루션을 위한 Diff 기반 보수적 크로스 체크 스킬**  
> Claude Code, Codex, Antigravity 등 주요 AI 코딩 에이전트에서 공통으로 사용할 수 있는 표준 규격(`SKILL.md`)을 준수합니다.

---

## 🎯 왜 이 스킬이 필요한가?

- **AI 바이브 코딩의 맹점 보완**: AI가 작성한 그럴듯한 코드 속에 숨겨진 **리소스 누수(FD/DB 커넥션/메모리), 스레드 비안전성, NPE, 권한 누락, 예외 삼킴**을 철저히 차단합니다.
- **온프레미스 배포 리스크 제로화**: 고객사 망 내에 설치되는 엔터프라이즈 보안 솔루션 특성상, 배포 후 크래시나 보안 취약점은 긴급 현장 지원 및 감사 지적으로 직결됩니다.
- **Diff 스코프 집중 (Not SAST)**: 전체 코드베이스 풀스캔이 아닌 `git diff` 범위 및 직접 영향권에만 집중하여, 토큰을 획기적으로 절약하고 빠르고 정밀한 검증을 수행합니다.
- **불필요한 오버엔지니어링(YAGNI) 척결**: 단일 목적을 위한 과도한 인터페이스, 디자인 패턴 남용, 불필요한 의존성 추가를 단호하게 걸러냅니다.

---

## 📂 프로젝트 구조

```
cross-check/
├── SKILL.md                 # 에이전트 행동 지침 및 페르소나 (표준 Agent Skills 규격)
├── scripts/
│   └── get_diff_context.py  # Git diff 추출 및 노이즈 필터링 스크립트 (Python 3 표준 라이브러리)
├── references/
│   ├── enterprise_checklist.md  # Java, JS/TS, Vue 전용 엔터프라이즈 보안/장애 체크리스트
│   └── report_template.md       # Critical / Warning / YAGNI 구조화 보고서 템플릿
└── README.md                # 설치 및 사용 가이드
```

---

## 🚀 에이전트별 설치 방법

### 1. Claude Code
글로벌 스킬 또는 프로젝트 전용 스킬로 등록할 수 있습니다.

```bash
# 글로벌 등록 (모든 프로젝트에서 사용)
mkdir -p ~/.claude/skills
ln -s /Users/pjw/dev/project/cross-check ~/.claude/skills/cross-check

# 또는 현재 프로젝트 전용 등록
mkdir -p .claude/skills
ln -s /Users/pjw/dev/project/cross-check .claude/skills/cross-check
```

### 2. Antigravity (AGY)
글로벌 스킬 디렉터리에 심볼릭 링크를 생성합니다.

```bash
mkdir -p ~/.gemini/antigravity/skills
ln -s /Users/pjw/dev/project/cross-check ~/.gemini/antigravity/skills/cross-check
```

### 3. Codex / Cursor / 기타 LLM 에이전트
작업 대상 프로젝트 루트의 `.skills/cross-check` 또는 프롬프트 지침 문서로 포함시켜 즉시 활성화할 수 있습니다.

---

## 💬 실전 활용 예시 (프롬프트)

에이전트에게 자연어로 요청하면 `cross-check` 스킬이 자동으로 트리거됩니다.

1. **작업 중인 uncommitted 코드 검증**:
   > *"방금 수정한 코드 버그 발생 가능성이랑 장애 유발 코드 없는지 크로스체크해줘."*
2. **커밋 직전 staged 코드 점검**:
   > *"staged된 변경사항 보안 취약점이랑 오버엔지니어링 여부 cross-check 해줘."*
3. **특정 커밋 검증**:
   > *"커밋 `a1b2c3d`에 대해 엔터프라이즈 관점에서 안정성/회귀 크로스체크 해줘."*
4. **브랜치 간 PR 변경분 검증**:
   > *"main 대비 현재 피처 브랜치 diff 점검해서 Critical/Warning 리포트 뽑아줘."*

---

## 🛠️ 단독 CLI 도구로 사용 (`get_diff_context.py`)

에이전트를 거치지 않고 직접 diff 요약본만 터미널에서 빠르게 확인할 수도 있습니다.

```bash
# 기본: 작업 트리 변경분 (staged + unstaged)
python3 scripts/get_diff_context.py

# Staged 변경분만
python3 scripts/get_diff_context.py --staged

# 특정 커밋
python3 scripts/get_diff_context.py --commit <COMMIT_HASH>

# 브랜치/커밋 범위
python3 scripts/get_diff_context.py --range main..HEAD

# 특정 파일 한정
python3 scripts/get_diff_context.py --file src/main/java/SecurityService.java
```
*※ `package-lock.json`, `dist/`, 바이너리 파일 등 노이즈는 자동으로 필터링되어 핵심 로직만 표시됩니다.*
