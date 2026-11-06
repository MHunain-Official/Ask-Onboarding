# Engineering Wiki: Deploys

## Release train

Production deploys happen **Tuesday and Thursday at 14:00 UTC**. There is a deploy freeze every Friday and from December 20 to January 3.

## How to deploy

1. Merge your pull request to `main`. CI must be green.
2. Staging deploys automatically. Verify at https://staging.acme-onboarding.example.
3. In `#deploys`, post the command:

```
/deploy api production
```

4. Watch the dashboard https://grafana.acme-onboarding.example/d/deploys for 15 minutes.

## Rollback

```bash
./scripts/rollback.sh api --to previous
```

Announce the rollback in `#eng-oncall`.

## Feature flags

New features ship behind a flag. Flags are managed in the flag dashboard and must be removed within 30 days of full rollout.

## Database migrations

Migrations must be backwards-compatible with the previous release. Never drop a column in the same release that stops using it.
