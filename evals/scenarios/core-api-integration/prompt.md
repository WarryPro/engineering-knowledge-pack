# Settlement reliability review and redesign

LedgerBay processes customer payouts through an external provider named ClearSettle. Support has escalated recurring incidents:

- ClearSettle sometimes accepts a payout request and then times out before returning a final HTTP response.
- Transient `503` responses appear during provider maintenance windows.
- ClearSettle can deliver the same payout callback more than once.
- When the user-facing request fails after a timeout, agents cannot tell whether money movement already started.

Current code performs the provider call directly inside the HTTP request that confirms a payout to the user.

Constraints:

- ClearSettle’s API and callback behavior cannot be changed by us.
- End-user confirmation latency still matters; unbounded waits are unacceptable.
- Accidentally performing the same payout more than once has real financial cost.
- Support needs diagnosable records when something goes wrong.
- We can change our service, storage, and operational playbooks.

Please recommend how this integration should evolve. Cover the request path, failure handling, duplicate callbacks, and what operators should be able to observe. Explain trade-offs and how you would verify the design before wider rollout.
