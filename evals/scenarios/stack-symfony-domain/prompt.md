# Reuse membership eligibility beyond the HTTP controller

In our Symfony 6 app, “can this account open a premium workspace?” is currently decided across several places:

- the controller interprets request attributes and flashes errors
- a Doctrine entity method encodes part of the rule using persistence fields
- `PremiumWorkspaceService` talks to Doctrine and the security token storage

Product now needs the same eligibility decision from a message consumer that provisions workspaces offline. That consumer should not pretend to be an HTTP request.

Constraints:

- This is an existing Symfony application; a ground-up rewrite is out of scope.
- HTTP behavior users already rely on should remain compatible.
- The offline consumer must reuse the same business decision, not a copied variant that will drift.
- Team capacity is modest; prefer a practical evolution over a large ceremonial redesign.

Please recommend how to evolve the feature. Explain where the reusable decision should live, how HTTP and the consumer should call it, and what trade-offs you accept.
