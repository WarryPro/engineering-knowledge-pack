# Checkout test investment plan

Our checkout module recently shipped two regressions that unit suites did not catch:

1. When the inventory reservation service returned a partial failure, checkout still marked the order as reserved.
2. A payment decline path left an inventory hold dangling because cleanup ran only on the happy path.

Today’s suite looks like this:

- Dozens of fast tests that mock nearly every collaborator and mostly assert which mocks were called.
- A small number of end-to-end style tests that are slow, flaky under parallel CI, and rarely cover failure branches.
- CI minutes are already near the team budget; leadership will not approve doubling pipeline time.

Please recommend how we should redesign the testing approach for this module and where to invest first. Explain what to keep, what to retire or rewrite, and how you would judge whether the new mix is working. Stay within a constrained CI budget.
