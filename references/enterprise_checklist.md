# Enterprise Security Solution Cross-Check Checklist

이 체크리스트는 **엔터프라이즈 온프레미스 보안 솔루션**의 특수성을 고려하여 작성되었습니다.  
고객사 환경에 패치가 배포된 이후 발생하는 장애, 메모리 누수, 크래시, 보안 취약점은 고객사 보안 감사 지적 및 긴급 온사이트 지원으로 이어지므로, **극도로 보수적이고 엄격한 잣대**로 코드 변경분을 검증합니다.

---

## 0. 핵심 심사 철학 (Philosophy)
1. **Never Crash, Never Leak**: 어떤 비정상 입력이나 예외 상황에서도 프로세스가 죽거나 리소스가 고갈되지 않아야 한다.
2. **Conservative & Boring**: 화려한 최신 문법이나 복잡한 추상화보다 직관적이고 단순하며 검증된 코드가 우월하다.
3. **Zero Regression**: 이번 수정이 다른 서브시스템이나 기존 설치 환경의 호환성(Config, DB, API)을 깨뜨리지 않는지 입증해야 한다.
4. **Anti-Vibe-Coding (YAGNI)**: AI가 자동 완성한 불필요한 디자인 패턴, 과도한 제네릭, 쓰이지 않는 예외 클래스는 즉시 삭제한다.

---

## 1. Java (Spring / Core) 검증 체크리스트

### 1.1 리소스 관리 및 누수 (Resource Leaks)
- [ ] **Try-with-resources 필수 적용**: `InputStream`, `OutputStream`, `Reader`, `Writer`, `Socket`, `Connection`, `PreparedStatement`, `ResultSet` 등 `AutoCloseable` 객체가 `try (...)` 블록 내에서 생성되고 해제되는가?
- [ ] **File Descriptor 누수**: 임시 파일 생성 후 삭제 보장(`deleteOnExit()` 또는 `finally` 블록 삭제), 디렉터리 스트림(`Files.list()`, `Files.walk()`) 닫힘 여부 확인.
- [ ] **스레드 풀 / 커넥션 풀 누수**: 커스텀 `ExecutorService` 종료(`shutdown()`) 보장 여부, 외부 API 호출 후 커넥션 반환 보장 여부.
- [ ] **ThreadLocal 누수**: 톰캣 등 서블릿 컨테이너 환경의 워커 스레드에서 `ThreadLocal` 사용 시 `finally` 블록에서 반드시 `remove()`를 호출하는가? (미호출 시 메모리 누수 및 다른 요청으로 데이터 오염)

### 1.2 동시성 및 스레드 안전성 (Concurrency & Thread-Safety)
- [ ] **Spring Bean 상태 공유**: 싱글톤 빈(`@Service`, `@Component`, `@Repository`)에 가변 멤버 변수(Stateful field)를 새로 추가하지 않았는가?
- [ ] **컬렉션 스레드 세이프티**: 멀티스레드 환경에서 `HashMap`, `ArrayList`를 직접 공유하고 있지 않은가? (`ConcurrentHashMap`, `CopyOnWriteArrayList` 사용 여부)
- [ ] **원자성 보장**: `count++` 같은 비원자적 연산을 멀티스레드에서 수행하지 않는가? (`AtomicInteger` 또는 적절한 동기화 사용 여부)
- [ ] **락 범위와 데드락**: `synchronized` 블록 내에서 I/O 또는 외부 네트워크 통신을 수행하지 않는가? 복수 개의 락을 획득할 때 획득 순서가 일관된가?

### 1.3 Null 안전성 및 경계 조건 (NullPointerException & Bounds)
- [ ] **Unboxing NPE**: 래퍼 객체(`Boolean`, `Integer`, `Long`)를 조건문이나 산술 연산에서 언박싱할 때 `null` 가능성을 사전 차단했는가?
- [ ] **메서드 인자/반환값 방어**: 외부 입력값이나 DB 조회 결과가 `null`일 때 NPE가 발생하지 않는가? (Apache Commons `StringUtils.isNotEmpty()` / `CollectionUtils.isEmpty()` 또는 `Objects.requireNonNull()` 활용)
- [ ] **컬렉션 인덱스 경계**: `list.get(0)` 호출 전 `!list.isEmpty()` 검증이 선행되었는가?

### 1.4 예외 처리 및 트랜잭션 무결성 (Exception & Transaction)
- [ ] **예외 삼킴(Swallowing) 금지**: `catch (Exception e) {}` 블록이 비어있거나 단순히 `e.printStackTrace()`만 찍고 정상 흐름으로 넘어가지 않는가?
- [ ] **원인 예외(Cause) 보존**: 새 예외로 래핑하여 던질 때 원본 `e`를 인자로 넘겨 스택 트레이스를 보존하는가? (`throw new BusinessException("msg", e);`)
- [ ] **`@Transactional` 롤백 정책**: `@Transactional` 적용 시 체크 예외(Checked Exception)가 발생할 경우 롤백되지 않으므로, 의도에 따라 `rollbackFor = Exception.class`가 선언되어 있는가?
- [ ] **비동기 예외 누락**: `@Async` 또는 `CompletableFuture` 내부에서 발생한 예외가 핸들링되지 않고 유실되지 않는가?

### 1.5 보안 취약점 (Security Defect)
- [ ] **SQL 인젝션**: MyBatis 매퍼에서 `${}`(문자열 치환)를 사용하지 않고 `#{}`(바인딩)를 사용했는가? 동적 SQL 생성 시 위험이 없는가?
- [ ] **경로 순회(Path Traversal)**: 사용자가 전달한 파일명/경로를 그대로 `new File(path)`에 전달하지 않고 `..` 및 정규화(`toRealPath()`) 검증을 거치는가?
- [ ] **민감정보 노출**: 비밀번호, 암호화 키, 세션 토큰, 개인정보가 로그 파일(`log.info`, `log.debug`)에 평문으로 남지 않는가?
- [ ] **안전하지 않은 역직렬화**: 검증되지 않은 소스의 객체 역직렬화(`ObjectInputStream.readObject()`)를 사용하지 않는가?

---

## 2. JavaScript / TypeScript 검증 체크리스트

### 2.1 런타임 타입 안전성 및 결함 (Runtime Safety)
- [ ] **`any` 타입 남용 차단**: 컴파일러 에러를 회피하기 위해 `any` 또는 `as unknown as T`를 남발하여 런타임 `TypeError`를 숨겨두지 않았는가?
- [ ] **Blind Optional Chaining (`?.`)**: 에러를 조사하여 해결하는 대신 `obj?.prop?.sub`로 땜질하여 하위 로직에서 엉뚱한 `undefined`가 전파되지 않는가?
- [ ] **숫자/타입 파싱 오류**: `parseInt(val, 10)` 시 기수(radix) 지정 여부 및 `NaN` 결과 처리(`Number.isNaN()`) 여부.

### 2.2 비동기 제어 및 리소스 누수 (Async & Promises)
- [ ] **Floating Promise**: `await` 또는 `.catch()`가 누락되어 백그라운드에서 `UnhandledPromiseRejection`이 발생할 소지가 없는가?
- [ ] **루프 내 비동기 처리**: `forEach` 내부에서 `async/await`를 사용하여 의도치 않게 순서가 꼬이지 않는가? (`for...of` 또는 `Promise.all()` 적절성)
- [ ] **이벤트 리스너 / 타이머 미해제**: `addEventListener`, `setInterval`, `setTimeout` 등록 후 해제 로직이 명확한가?

### 2.3 보안 결함 (Security Defect)
- [ ] **프로토타입 오염 (Prototype Pollution)**: 신뢰할 수 없는 객체를 재귀적으로 병합(`deepMerge`, `Object.assign`)할 때 `__proto__`, `constructor` 검증이 있는가?
- [ ] **ReDoS (정규식 서비스 거부)**: 복잡한 정규식에 악의적 입력이 들어왔을 때 백트래킹으로 인한 이벤트 루프 블로킹 위험이 없는가?
- [ ] **프론트엔드 환경변수 유출**: 브라우저에 번들링되는 코드에 백엔드 시크릿 키나 마스터 패스워드가 하드코딩되어 있지 않은가?

---

## 3. Vue (Vue 2 / Vue 3) 검증 체크리스트

### 3.1 컴포넌트 생명주기 및 메모리 누수
- [ ] **정리(Cleanup) 훅 구현**: `onUnmounted` (Vue 3) 또는 `beforeDestroy` (Vue 2)에서 컴포넌트가 소멸할 때 다음 항목들을 완벽히 정리하는가?
  - 글로벌 이벤트 버스/이벤트 리스너 (`window.addEventListener`, `document.addEventListener`)
  - 타이머 (`clearInterval`, `clearTimeout`)
  - 웹소켓 연결, SSE, 외부 라이브러리 인스턴스 (Chart.js, Grid, Editor 등 `instance.destroy()`)
- [ ] **전역 스토어 오염**: 컴포넌트 진입 시 초기화하지 않아 이전 방문자의 데이터나 필터 조건이 남아있는 버그가 없는가?

### 3.2 템플릿 보안 및 반응성 (Template & Reactivity)
- [ ] **`v-html` XSS 취약점**: 사용자 입력값, API 응답 데이터를 DOM Purify 같은 새니타이저(Sanitizer) 없이 `v-html`로 출력하고 있지 않은가?
- [ ] **Prop 직접 변조(Mutation)**: 부모로부터 전달받은 `props`를 자식 컴포넌트에서 직접 변경하여 단방향 데이터 흐름을 깨뜨리지 않는가?
- [ ] **반응성 소실 / 무한 루프**:
  - `reactive` 객체를 단순 구조분해 할당하여 반응성을 잃지 않았는가? (`toRefs` 사용)
  - `watch` 또는 `computed` 내부에서 감시 대상 상태를 다시 변경하여 무한 재렌더링을 유발하지 않는가?

---

## 4. 오버엔지니어링 & YAGNI 검증 체크리스트

- [ ] **단일 사용처 추상화 금지**: 단 하나의 구현체만 존재하는 클래스를 위해 불필요한 Interface, Abstract Factory, Strategy 패턴을 덧대지 않았는가?
- [ ] **의존성 낭비**: 2~3줄의 표준 API(예: `Array.prototype.flat`, `Object.fromEntries`, Java `Stream`/`Optional`)로 구현 가능한 로직을 위해 외부 라이브러리를 새로 추가하지 않았는가?
- [ ] **불필요한 범용성 배격**: "나중에 확장될 수도 있으니까"라는 가정하에 작성된 미사용 파라미터, 쓰이지 않는 설정 옵션, 과도한 제네릭 타입 파라미터가 있는가?
- [ ] **과도한 계층화(Over-layering)**: 단순한 데이터 전달 메서드를 위해 Controller -> Facade -> Service -> Manager -> Repository 같은 무의미한 통과 계층(Pass-through)을 신설하지 않았는가?
