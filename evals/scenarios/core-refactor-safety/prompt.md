# Pricing module change plan

We need to support a new “partner discount band” in pricing within a few sprints. The current module has grown awkwardly:

- Similar discount calculations appear in more than one function.
- Callers rely on subtle behavior such as rounding and free-shipping thresholds that are not obvious from names alone.
- Automated coverage is thin; most confidence comes from manual checks before release.
- Product will not accept freezing feature delivery while we “clean everything.”

Constraints:

- Public pricing results used by checkout and invoices should remain compatible for existing catalog items unless a documented intentional change is approved.
- Prefer an incremental rollout over a single replacement.
- The team still has to ship the partner discount band on schedule.

Please review the excerpt and propose a pragmatic plan to introduce the new variation safely. Include what you would stabilize first, how you would sequence changes, and how you would know behavior stayed compatible.
