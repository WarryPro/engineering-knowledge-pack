# Restructure plan for Northline fulfillment

We ship a small commerce backend for Northline Outfitters. The current fulfillment path lives mainly in one module that has grown with every feature request. Product now wants:

- a second shipping carrier next quarter (today we only call ParcelGo)
- the same fulfillment decisions available from both the HTTP checkout path and a warehouse batch job
- business rules that can change without touching carrier-specific code every time

Constraints you must respect:

- We cannot pause customer orders for a multi-week rewrite.
- Public checkout and warehouse callers must keep the same observable outcomes for the current release train.
- Changes must be deliverable in incremental pull requests by a two-person team.
- ParcelGo remains the only live carrier for now; the second carrier is planned, not implemented yet.

Please propose a practical restructuring and change plan. Include:

1. What you would change first and why
2. How responsibilities should be separated so carrier and entry-point pressure do not keep collapsing into one place
3. How you would keep behavior compatible while the work lands
4. Trade-offs you are accepting
5. How you would verify the change is safe enough to ship incrementally
