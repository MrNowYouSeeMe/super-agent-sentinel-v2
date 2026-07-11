# Legacy Code Policy

The uploaded `SUST-CSE-Carnival-2026.zip` is used only to understand prior contracts, terminology, datasets, scenarios, and attempted behavior.

## Strict rules

1. No new implementation is added inside the legacy project.
2. No legacy module is imported by V2.
3. No `.env`, credential, generated dependency folder, cache, build output, or embedded Git history is copied.
4. A legacy snippet may be reimplemented only after its behavior is independently verified and covered by a new V2 test.
5. V2 architecture and naming remain independent.
6. The challenge problem statement is the source of business truth.
