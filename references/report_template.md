# Cross-Check Review Report Format

모든 AI 에이전트는 장황한 서론이나 불필요한 미사여구를 생략하고, 다음 정형화된 보고서 템플릿에 따라 즉각적인 판단과 조치 사항을 전달합니다.

---

```markdown
# 🛡️ Cross-Check Security & Stability Review

- **Target Scope**: [예: Working Tree (staged + unstaged) / Commit abc1234 / main..feature]
- **Audited Files**: N개 파일 ([파일목록])
- **Overall Verdict**: [ 🔴 BLOCKED | 🟡 CONDITIONAL PASS | 🟢 PASS ]

---

## 🚨 Critical Issues (Must Fix before Merge/Release)
> 프로세스 크래시, 리소스/메모리 누수, 보안 취약점, 하위 호환성 파괴 등 온프레미스 배포 시 즉각적인 장애를 유발하는 항목.
> (발견된 항목이 없으면 "None detected." 로 간결히 표기)

### 1. [파일경로:라인번호] 간결하고 명확한 결함 제목
- **원인 및 파급 효과**: [장애 발생 시나리오, 왜 엔터프라이즈 환경에서 치명적인지 설명]
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
> 경계 조건(Edge case) 미처리, 잠재적 NPE, 불완전한 예외 처리, 비동기 순서 꼬임 등.

### 1. [파일경로:라인번호] 잠재적 위험 요약
- **발생 가능 상황**: [어떤 조건에서 버그가 발생하는지]
- **대응 방안**: [어떻게 보완해야 하는지 짧게 제시]

---

## 🧹 Over-Engineering & YAGNI Findings
> 바이브 코딩으로 인해 생성된 불필요한 추상화 계층, 단일 구현체용 인터페이스, 과도한 제네릭, 미사용 파라미터.

### 1. [파일경로:라인번호] 단순화 대상 항목
- **문제점**: [왜 이 코드가 불필요하게 복잡하거나 비대한지 설명]
- **단순화 권고**: [어떻게 더 짧고 가독성 있게 쳐낼 수 있는지 제시]

---

## ✅ Verified Safe Changes
- [이번 변경에서 의도대로 안전하고 견고하게 처리된 부분 1~2줄 요약]
```
