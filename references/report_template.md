# Cross-Check Review Report Format

에이전트는 사족과 불필요한 미사여구를 철저히 배제하고, 한눈에 파악할 수 있는 **태그형 1줄 요약(One-Line Tagged Findings)**과 **보수적 수정안(Conservative Fix)**으로 즉각적인 판단을 내립니다.

---

```markdown
# 🛡️ Cross-Check Security & Stability Review

- **Target Scope**: [Working Tree | Staged | Commit <hash> | Range <base>..<head>]
- **Audited Files**: N file(s)
- **Scoreboard**: 🚨 [X] Critical | ⚠️ [Y] Warning | 🧹 [Z] YAGNI | net: [-N lines possible]
- **Verdict**: [ 🔴 BLOCKED | 🟡 CONDITIONAL PASS | 🟢 PASS (Solid & Lean. Clean to ship.) ]

---

## ⚡ Quick Scan (One-Line Tagged Findings)
> 형식: `<file>:L<line>: <tag> <위험요소/문제점>. <조치방안>.`

- `L14-22: leak: FileInputStream not closed in exception path. try-with-resources, 1 line.`
- `L45: npe: unboxing Integer without null guard. Integer.intValue() guarded or Objects.requireNonNull.`
- `L88: yagni: AbstractSecurityHandler with single impl. Inline it directly, delete 40 lines.`
- `L102: swallow: catch(Exception e) ignores error. Log cause and re-throw or rollback.`
- `L150: xss: v-html renders unsanitized user profile. {{ profile.name }} or DOMPurify.`

**Tags**:
- `crash:` / `panic:` 프로세스 강제 종료, Out of bounds, 비정상 패닉
- `leak:` FD, DB/Socket 커넥션, ThreadLocal, Vue unmounted 리스너 누수
- `npe:` NullPointerException, undefined 접근 결함
- `sqli:` / `xss:` / `sec:` 보안 취약점, 주입 공격, 권한 누락
- `race:` 멀티스레드 동기화 누락, 원자성 결함, 데드락 위험
- `swallow:` 에러/예외 삼킴, 원본 원인 유실, 트랜잭션 롤백 누락
- `yagni:` 단일 구현체 인터페이스, 쓰이지 않는 추상화/파라미터
- `stdlib:` / `native:` 표준 라이브러리나 플랫폼 기능으로 1줄 대체 가능
- `shrink:` 동일 로직을 훨씬 짧고 명확하게 단순화 가능

---

## 🚨 Critical Issues (Must Fix before Merge/Release)
(발견된 결함이 없을 시: "None detected. No crash or leak risks found.")

### 1. [파일경로:라인번호] 간결한 결함 제목
- **원인 및 파급 효과**: [온프레미스 고객사 환경에서 왜 치명적인지 설명]
- **취약/위험 코드**:
```language
// 문제가 되는 기존 코드 스니펫
```
- **권장 수정 코드 (Conservative Fix)**:
```language
// 화려하지 않고 가장 안전하고 확실한 수정 코드
```

---

## ⚠️ Warning Issues (High Risk / Edge Cases)
(경계 조건 미처리, 잠재적 NPE, 불완전한 예외 처리, 비동기 순서 꼬임 등)

---

## 🧹 Over-Engineering & YAGNI Findings
(AI 바이브 코딩으로 유입된 불필요한 계층, 단일 구현체 인터페이스, 과도한 제네릭 쳐내기)

---

## 💡 Net Impact & Verdict Summary
- **Net code change**: `-<N> lines` (오버엔지니어링 제거 시)
- **Bottom line**: [최종 승인 여부 및 1줄 결론]
```

