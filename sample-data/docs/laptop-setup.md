# Laptop Setup

Your laptop arrives before your first day. Engineers get a 16-inch MacBook Pro; everyone else gets a 14-inch MacBook Air.

## First boot checklist

1. Sign in with the temporary password on the card in the box. You must change it at first login.
2. Enable FileVault disk encryption. This is mandatory and checked nightly.
3. Install the device management agent from https://it.acme-onboarding.example/mdm.
4. Install the VPN client (see the VPN Setup Guide).
5. Sign in to Slack, email and the password manager.

## Developer tools

Run the bootstrap script from the engineering wiki:

```bash
curl -fsSL https://eng.acme-onboarding.example/bootstrap.sh | bash
```

It installs Homebrew, Git, Docker Desktop, Node 20 and Python 3.12.

## Rules

- Lock your screen when you leave it. The auto-lock timeout is **5 minutes**.
- Do not install pirated software or disable the management agent.
- Lost or stolen laptop: report it to security@acme-onboarding.example within 1 hour.

## Returning equipment

Return your laptop within 10 business days of your last day. A prepaid box is sent to you.
