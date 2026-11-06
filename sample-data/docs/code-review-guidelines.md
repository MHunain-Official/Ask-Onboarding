# Code Review Guidelines

## For authors

- Keep pull requests under **400 changed lines** where possible. Split bigger changes.
- Write a description: what changed, why, and how you tested it.
- Link the ticket, for example `PLAT-482`.
- Self-review your diff before requesting review.

## For reviewers

- Respond within **1 business day**.
- Be kind and specific. Prefix nits with `nit:` so the author knows they are optional.
- Check tests, naming, error handling and security. Do not only look at style; linters do that.

## Approval rules

- Every pull request needs **2 approvals**, at least one from a code owner.
- Changes to authentication, billing or infrastructure need a review from the security team too.
- Authors never merge their own pull request without approval.

## Merging

Use "Squash and merge". The squash title must follow Conventional Commits.

## Disagreements

If you cannot agree after two rounds of comments, talk in a call. If it is still unresolved, the tech lead decides.
