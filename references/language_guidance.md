# Language & Framework Guidance

Cross-Check is language-agnostic at the invariant level, but findings must respect the semantics of the language and framework being reviewed.

## Confidence

Every finding MUST have a confidence level:

- **HIGH** — directly demonstrated by the diff/context; deterministic failure, exploit, leak, or contract break is evident.
- **MEDIUM** — strong evidence exists, but runtime/framework behavior or an unseen path could change the outcome.
- **LOW** — plausible concern that cannot be established from available diff/context.

Only **HIGH** and **MEDIUM** findings may influence the verdict. LOW-confidence observations belong in warnings or should be omitted when they would create noise.

## Language-Specific Rules

### Java / JVM
- Check checked/unchecked exception behavior, try-with-resources, executor lifecycle, `ThreadLocal` cleanup, mutable singleton state, unsafe publication, nullability, autounboxing, and transaction boundaries.
- Treat Spring singleton beans with mutable instance fields as a concurrency hotspot unless access is provably immutable or synchronized.
- When a public/service method changes return nullability, exception behavior, or transaction semantics, prioritize caller analysis.

### Go
- Check `defer` placement, goroutine termination, context cancellation, channel ownership, mutex/atomic usage, loop-variable capture, and ignored error returns.
- A newly spawned goroutine without a clear lifetime/cancellation path is a resource-lifecycle concern.

### Rust
- Prefer compiler-enforced ownership guarantees over speculative leak claims.
- Focus on `unsafe`, FFI boundaries, spawned tasks, lock ordering, blocking inside async contexts, cancellation, and panic/error propagation.

### C / C++
- Check ownership, lifetime, RAII, raw pointer validity, bounds, integer conversions, use-after-free, double-free, data races, and lock ordering.
- Do not label RAII-managed resources as leaks merely because explicit `close`/`free` is absent.

### Python
- Check context managers, file/socket lifecycle, mutable global state, thread/async task lifetime, exception swallowing, unsafe deserialization, command execution, and path handling.

### TypeScript / JavaScript
- Check promise rejection, async task lifetime, event-listener/timer cleanup, `any`/unsafe casts, undefined property access, prototype-related risks, DOM XSS, and command/query construction.

## Framework Awareness

Framework-specific behavior may override generic heuristics. When the framework is identifiable, prefer its lifecycle and security conventions over generic assumptions.

Examples:

- Spring: singleton scope, proxy-based transactions/security, request scope, `@Async`, executor lifecycle.
- React/Vue: effect/listener/timer cleanup and component unmount behavior.
- Node.js: event-loop lifetime, stream ownership, promise rejection, worker lifecycle.
- Django/Flask: request lifecycle, ORM parameterization, template escaping, background task ownership.

If framework semantics cannot be established from the available context, downgrade the finding rather than guessing.

## Conservative Principle

Language-specific guidance narrows false positives; it must never be used to invent a defect. A finding should explain the concrete path from the changed code to the failure, exploit, leak, or contract break.
