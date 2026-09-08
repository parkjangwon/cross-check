# Enterprise Universal Invariants & Cross-Check Checklist

Cross-Check is a **diff-scoped safety gate**, not a full-project SAST. Start with changed hunks and expand context only when needed to prove impact.

Every finding must be evidence-based and assigned a confidence level:

- **HIGH** — directly demonstrated by the diff/context.
- **MEDIUM** — strong evidence, but runtime/framework behavior or an unseen path could change the outcome.
- **LOW** — plausible concern that cannot be established from available context.

LOW-confidence observations must never block a review. When framework/language semantics are unclear, lower confidence rather than guessing.

---

## 1. Resource Lifecycle & Leak Prevention (`leak:`)

- Are files, sockets, DB connections, streams, executors, goroutines/tasks, listeners, timers, and request/thread-local state cleaned up deterministically on success and failure paths?
- Do newly spawned workers/tasks have a clear owner, termination condition, timeout, or cancellation mechanism?
- Are pooled resources returned rather than merely dereferenced?
- Do component/UI subscriptions and timers unregister during teardown?
- Do not report a leak merely because explicit cleanup is absent when ownership is clearly managed by RAII, try-with-resources, a context manager, or a framework lifecycle.

## 2. Concurrency, Race Conditions & Deadlocks (`race:`)

- Is shared mutable state protected by the correct synchronization primitive?
- Are check-then-act operations atomic where required?
- Are locks acquired in a consistent order?
- Is blocking I/O or network work performed while holding a lock?
- Do singleton services (for example Spring `@Component`) introduce mutable instance state accessed by concurrent requests?
- Are async tasks, callbacks, channels, and cancellation paths correctly owned?

## 3. Pointer, Null & Boundary Safety (`npe:`, `nil:`, `crash:`)

- Can nullable/optional/external values be dereferenced without validation?
- Can implicit conversions or unboxing trigger runtime exceptions?
- Can arrays, slices, lists, or buffers be accessed outside valid bounds?
- Can unsafe/raw casts bypass a meaningful type or validation boundary?
- Is an error/panic path reachable from malformed input or an unexpected state?

## 4. Error Handling & Transaction Integrity (`swallow:`, `panic:`)

- Are errors/exceptions ignored, swallowed, or reduced to a log message without appropriate recovery or propagation?
- Is the original cause preserved when wrapping/rethrowing?
- Did the change alter exception/error behavior without updating callers?
- Are DB and distributed-operation transactions rolled back on failure according to actual framework semantics?
- Are async promise/task errors observed and handled?

## 5. Security & Trust Boundaries (`sec:`, `sqli:`, `xss:`, `priv:`)

- Are SQL/LDAP/command/template/query expressions constructed through unsafe concatenation?
- Are filesystem paths canonicalized/validated against an allowed base directory where required?
- Are credentials, tokens, secrets, or PII exposed through logs, errors, telemetry, or client bundles?
- Did the change bypass authentication, authorization, rate limits, CSRF protections, or other security middleware/interceptors?
- Did a trust boundary lose input validation or output encoding?

## 6. Over-Engineering & YAGNI (`yagni:`, `stdlib:`, `shrink:`, `delete:`)

YAGNI findings are quality suggestions, not blockers by themselves.

- Is an abstraction genuinely unused beyond one implementation, or does it represent a real DI/test/domain boundary?
- Was a dependency added for functionality already provided by the standard library/runtime?
- Were speculative configuration switches or extension points added without a current consumer?
- Are pass-through layers adding no business, security, transaction, or lifecycle behavior?
- Can the same behavior be made materially smaller without reducing safety or clarity?

**Do not call an abstraction YAGNI solely because it has one current implementation.** Consider dependency injection, testing seams, framework contracts, plugin boundaries, and domain ownership first.

## 7. Blast Radius & Caller Contract Drift (`caller:`)

- Did return nullability change?
- Did a precondition become stricter?
- Did a new exception/error status appear?
- Did side effects, mutation, transaction boundaries, thread/context assumptions, or ordering change?
- Did a bug fix protect one caller while sibling callers remain exposed?
- Is a textual search result actually an invocation, or merely a definition/reference?

Caller discovery tools such as `git grep` are **candidate discovery only**. Reflection, generated code, dynamic dispatch, DI wiring, and framework proxies may require manual reasoning or language-aware tooling.

---

## 🚦 Verdict Mapping

| Verdict | Required condition |
| :--- | :--- |
| 🔴 **BLOCKED** | At least one HIGH-confidence production-significant security, crash, leak, race/deadlock, data-corruption, or caller-contract defect. |
| 🟡 **CONDITIONAL PASS** | No HIGH blocker, but at least one MEDIUM-confidence credible safety/security/stability/contract risk remains. |
| 🟢 **PASS** | No HIGH/MEDIUM safety or security findings. LOW findings and subjective style preferences do not block. |

YAGNI, formatting, naming, and subjective refactoring preferences **must not** produce BLOCKED.

---

## 🏷️ Standard Tag Reference

| Tag | Category | Description |
| :--- | :--- | :--- |
| `crash:` / `panic:` | Stability | Process crash, uncaught exception, panic, out-of-bounds |
| `leak:` | Resource | FD, socket, DB connection, memory, listener, worker/task leak |
| `npe:` / `nil:` | Safety | Null/Nil dereference or undefined property access |
| `caller:` | Blast Radius | Caller contract drift or unhandled changed behavior |
| `race:` | Concurrency | Race condition, non-atomic operation, deadlock hazard |
| `swallow:` | Error Handling | Silently ignored error/exception, lost cause, missing rollback |
| `sec:` / `sqli:` / `xss:` | Security | Injection, path traversal, auth bypass, secret exposure |
| `yagni:` | Complexity | Speculative abstraction, unnecessary flexibility |
| `stdlib:` / `native:` | Minimalism | Hand-rolled logic replaceable by standard library/runtime |
| `shrink:` | Conciseness | Same safe logic achievable with fewer, clearer lines |
| `delete:` | Dead Code | Obsolete or redundant code/artifact |
