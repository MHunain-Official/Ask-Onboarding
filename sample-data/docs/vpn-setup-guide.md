# VPN Setup Guide

Acme Onboarding Co requires the corporate VPN for any access to internal tools (wiki, staging, database bastions) when you are outside an office.

## Install the client

1. Install OpenVPN: `sudo apt install openvpn` on Ubuntu, or `brew install openvpn` on macOS.
2. Download your personal profile `company.ovpn` from https://it.acme-onboarding.example/vpn.
3. Never share your profile. Each profile is tied to your employee ID.

## Connect

### Setup

Run this command from the folder that contains your profile:

```bash
sudo openvpn --config company.ovpn
```

Enter your company username and the 6-digit code from your authenticator app when prompted. The tunnel is up when you see `Initialization Sequence Completed`.

### Troubleshooting

- `AUTH_FAILED`: your authenticator code expired. Wait for the next code and retry.
- `TLS handshake failed`: check that UDP port 1194 is not blocked. The fallback is TCP port 443, using `company-tcp.ovpn`.
- Still stuck? Open a ticket with the IT help desk (see the IT Help Desk guide) and include the last 20 lines of the client log.

## Rules

- VPN sessions disconnect after 12 hours of use. Reconnect the next morning.
- Split tunnelling is disabled. Streaming video over the VPN is discouraged.
