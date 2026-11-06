# On-Call Runbook

## Rotation

- Rotations last **1 week** and change on Monday at 10:00 Eastern Time.
- Each rotation has a primary and a secondary engineer.
- Swap shifts in PagerDuty and tell `#eng-oncall`.

## When you are paged

1. Acknowledge the page within **5 minutes**. If you do not, the secondary is paged.
2. Open an incident channel named `inc-YYYYMMDD-short-name`.
3. Check the dashboards: https://grafana.acme-onboarding.example/d/overview.
4. Mitigate first (rollback, scale up, disable a flag). Find the root cause afterwards.

## Useful commands

```bash
kubectl get pods -n production
kubectl logs deploy/api -n production --tail=200
./scripts/rollback.sh api --to previous
```

## Compensation

On-call engineers receive **$350 per week** plus 1.5 hours of time off for every hour worked between 22:00 and 06:00.

## Escalation

If the issue is not mitigated in 30 minutes, escalate to the engineering manager on duty. Customer-visible incidents of 1 hour or more need a written post-mortem within 5 business days.
