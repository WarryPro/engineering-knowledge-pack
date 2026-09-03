# Share quote behavior across two screens

Our TypeScript web app currently has a `QuotePanel` used on the product page. It fetches tax/shipping hints from an API, computes a payable total, manages loading/error UI, and renders the summary.

We now need a cart review screen that must show the same payable total rules and the same loading/error behavior when the quote API fails. The quote API response shape is expected to gain fields next quarter.

Constraints:

- Existing product-page UI behavior should remain for users.
- We are not rewriting the app onto a new framework.
- The shared logic must not drift into two divergent copies.
- Loading and failure states must remain visible to users on both screens.

Please recommend how to evolve the feature so both screens can share the behavior safely. Explain trade-offs and a migration sequence from the current component-centric code.
