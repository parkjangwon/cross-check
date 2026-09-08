# Enterprise Universal Invariants & Cross-Check Checklist

This checklist applies to **any programming language** (Java, Go, C/C++, Rust, Python, TypeScript/JavaScript, etc.) in enterprise on-premise environments.

Enterprise software deployed on-premise has an asymmetric risk profile: a crash, leak, or regression cannot be patched silently with a hot reload. Every defect requires emergency customer engineering, hotfixes, and audit explanations.

---

## 🧭 The 6 Universal Enterprise Invariants

Every code modification must satisfy these 6 universal invariants regardless of language or framework:

```
                  ┌──────────────────────────────────────────────┐
                  │ 1. Resource Lifecycle (Never Leak)           │
                  │ 2. Concurrency & State (Never Race/Deadlock) │
                  │ 3. Memory & Pointer Safety (Never Crash)     │
                  │ 4. Error & Transaction Integrity (No Swallow)│
                  │ 5. Trust Boundary Security (Zero Injection)  │
                  │ 6. Simplicity & YAGNI (No Over-Engineering)  │
                  └──────────────────────────────────────────────┘
```

---

### 1. Resource Lifecycle & Leak Prevention (`leak:`)
*Applies to: file descriptors, sockets, DB connections, thread/goroutine pools, memory, UI subscriptions.*

- **Deterministic Cleanup**: Are all allocatable OS resources deterministically freed in every exit path (normal return, early return, error, panic/exception)?
  - E.g., `try-with-resources` (Java), `defer close()` (Go), RAII/smart pointers (C++/Rust), `with` statements (Python), `finally`/destructor hooks (JS/TS/Vue).
- **Background Worker & Coroutine Leaks**: Do newly spawned threads, goroutines, or async background tasks have guaranteed termination triggers, timeouts, or cancellation tokens (`context.Context`, `AbortController`)?
- **Thread-Local / Context Leaks**: In pooled execution environments (e.g., HTTP worker pools), are thread-local or request-scoped stores cleanly purged in `finally`/`defer` blocks?
- **Client/UI Cleanup**: Are global event listeners, timers, web sockets, and 3rd-party library instances unregistered on component teardown/unmount?

---

### 2. Concurrency, Race Conditions & Deadlocks (`race:`)
*Applies to: multi-threaded, asynchronous, or multi-process systems.*

- **Shared Mutable State**: Is shared mutable state protected by appropriate primitives (mutex, atomic operations, channel/actor isolation)?
- **Lock Contention & Granularity**: Is I/O or network communication performed while holding a lock? Are locks acquired in a consistent global order across all call paths to prevent deadlocks?
- **Framework Singletons**: In singleton services (e.g., Spring `@Component`, NestJS, Go package singletons), are mutable instance variables introduced that multiple concurrent requests can mutate?
- **Check-Then-Act (TOCTOU)**: Are there non-atomic check-then-modify patterns (e.g., check file existence then create, check balance then withdraw)?

---

### 3. Pointer, Null & Boundary Safety (`npe:`, `crash:`)
*Applies to: all languages with nullable references, pointers, or dynamic typings.*

- **Null/Nil Dereference**: Is every optional, nullable, or external input guarded before access?
- **Implicit Conversions & Unboxing**: Can automatic unboxing (e.g., Java `Integer` to `int`) or type coercion lead to unexpected panics or runtime exceptions?
- **Boundary & Index Checks**: Are array, slice, or collection accesses (`arr[0]`, `list.get(0)`) preceded by length/emptiness checks?
- **Type Bypass Risks**: Is `any`, `unsafe`, raw pointer casting, or blind optional chaining (`?.`) used to suppress type errors, concealing invalid runtime states?

---

### 4. Error Handling & Transaction Integrity (`swallow:`, `panic:`)
*Applies to: error propagation, rollback mechanisms, and logging.*

- **No Error Swallowing**: Are catch/error blocks empty or merely logging without properly handling, rolling back, or re-throwing?
- **Root Cause Preservation**: When wrapping or re-throwing errors, is the original cause preserved in the error chain/stack trace?
- **Transaction Rollback**: If a database transaction or distributed operation fails, is rollback guaranteed (e.g., checking transaction rollback rules for checked vs unchecked exceptions)?
- **No Uncaught Async Rejections**: Are all promises, async tasks, and channels monitored for error states?

---

### 5. Security & Trust Boundaries (`sec:`, `sqli:`, `xss:`, `priv:`)
*Applies to: inputs from users, APIs, external config files, and network peers.*

- **Injection Vectors**: Are commands, SQL queries, LDAP searches, or shell calls constructed via string concatenation rather than parameterized APIs?
- **Path Traversal**: Are file paths validated, canonicalized, and restricted to an allowed base directory before filesystem operations?
- **Credential & PII Exposure**: Are secrets, tokens, passwords, or personal identifiable information (PII) printed to logs, console, or client-side bundles?
- **Authentication & Authorization Bypasses**: Does the modified path bypass any permission checks, security interceptors, or rate limiters?

---

### 6. Over-Engineering & YAGNI (`yagni:`, `stdlib:`, `shrink:`, `delete:`)
*Applies to: AI-generated code bloat, premature abstraction, and unnecessary dependencies.*

- **Single-Implementation Abstractions**: Has an interface, abstract base class, or generic factory been added when only one concrete implementation exists?
- **Dependency Bloat**: Has a new external library or package been introduced for logic that the standard library or 3 lines of native code can solve?
- **Dead Flexibility**: Are there configuration flags that no one will configure, or unused extension points built for hypothetical future needs?
- **Pass-Through Layers**: Are there redundant layers (e.g., Controller -> Facade -> Service -> Manager -> DAO) that simply forward calls without adding real business logic?

---

## 🏷️ Standard Tag Reference

Use these concise tags in the Quick Scan section:

| Tag | Category | Description |
| :--- | :--- | :--- |
| `crash:` / `panic:` | Stability | Process crash, uncaught exception, panic, out-of-bounds |
| `leak:` | Resource | FD, socket, DB connection, memory, listener leak |
| `npe:` / `nil:` | Safety | Null/Nil pointer dereference, undefined property access |
| `race:` | Concurrency | Race condition, non-atomic operation, deadlock hazard |
| `swallow:` | Error Handling | Silently ignored error/exception, lost cause, missing rollback |
| `sec:` / `sqli:` / `xss:` | Security | Injection, path traversal, auth bypass, secret in log |
| `yagni:` | Complexity | Speculative abstraction, single-impl interface, unused params |
| `stdlib:` / `native:` | Minimalism | Hand-rolled code replaceable by language standard library |
| `shrink:` | Conciseness | Same logic achievable with fewer, clearer, more idiomatic lines |
| `delete:` | Dead Code | Obsolete code, redundant check, unused artifact |
