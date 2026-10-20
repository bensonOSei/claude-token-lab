

## Ship checklist (added by token-lab; do all of it before you report DONE)
1. Every branch this task adds (deny, error, empty, not-found, failure, limit) has a test that fails without it. Prove it: break or comment out the guard, run the test, see it go red, restore it. Name each branch you checked in your report.
2. No vacuous tests. A test that would still pass with the behaviour removed, or that asserts only `ok=false` instead of the exact error, does not count.
3. If you changed a type, signature, return value or contract, grep every caller in the repo, including files outside the brief, and fix or list each one.
4. Walk the lifecycle edges and handle each one or list it as a concern: removed or cancelled mid-flight, lost or duplicate events (pointerup, retries, double submit), failure after an earlier success (stale error vs ready state), concurrent writes, restart or reload.
5. If the brief's own code or numbers look wrong, do not copy them silently. Say so under Concerns. Plan-mandated bugs are still bugs.
6. Run the task's tests, the full suite of the package you touched, the typecheck and the lint. Paste each command with its result line.
7. If any item is unsure, report DONE_WITH_CONCERNS, not DONE.
