# Customer name field evolution

Harbor CRM stores person names in `customers.full_name` as a single string. Product and localization now need structured given/family names for search and salutations. The table already has substantial production data, and writes continue throughout the day.

Deployment reality:

- We roll out with overlapping old and new application versions for at least one release cycle.
- Traffic cannot be stopped for a maintenance window long enough to rewrite everything offline.
- Rollback of the application release must remain feasible if the new version misbehaves.
- Reporting jobs still read `full_name` today and cannot all move on day one.

Current application code reads and writes only `full_name`.

Please propose a migration and deployment strategy that gets us to structured names safely. Explain sequencing, compatibility between versions, how you would handle existing rows, and how you would verify the change. Call out risks and trade-offs.
