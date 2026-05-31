# Known Issues

## mailcow Generic-OIDC logout does not end the IdP session

### Status

Open.

### Context

mailcow is configured to use Logto through Generic-OIDC for mailbox UI login.
The current Generic-OIDC configuration stores only the authorization, token, and
userinfo endpoints:

- `https://auth.ibbi.cc/oidc/auth`
- `https://auth.ibbi.cc/oidc/token`
- `https://auth.ibbi.cc/oidc/me`

mailcow does not store or call Logto's OIDC end-session endpoint:

- `https://auth.ibbi.cc/oidc/session/end`

### Current Behavior

When a user clicks logout in mailcow, mailcow only clears its local PHP session
and redirects back to `/`.

Logto's centralized browser session under `auth.ibbi.cc` remains active. If the
user clicks the Logto / OIDC login button again, Logto may immediately SSO the
same user back into mailcow without showing a fresh login prompt.

### Impact

This makes account switching confusing and can mislead users into thinking they
fully signed out of the shared identity provider when only the mailcow session
was cleared.

This is not currently a confirmed mailcow security vulnerability, but it is an
SSO logout completeness and UX issue.

### Upstream Reference

mailcow upstream tracks the same behavior as an enhancement:

- https://github.com/mailcow/mailcow-dockerized/issues/5774

### Preferred Fix

Implement an Ansible-managed patch for mailcow until upstream supports this
natively:

1. Add a Logto post-logout redirect URI for the mailcow application:
   - `https://mail.ibbi.cc`
2. Patch mailcow logout handling so Generic-OIDC user logout redirects to:
   - `https://auth.ibbi.cc/oidc/session/end`
3. Include an appropriate post-logout redirect back to:
   - `https://mail.ibbi.cc`
4. Reapply the patch after mailcow source updates, because the mailcow role uses
   a forced git checkout.

### Alternatives

- Add `prompt=login` to the Generic-OIDC authorization request. This forces a
  fresh login prompt but does not actually end the Logto session.
- Wait for upstream support.
- Submit a proper upstream PR adding configurable OIDC logout support.

## Caddy public Cloudflare-facing routes trust CF-Connecting-IP without origin source validation

### Status

Open.

### Context

Caddy currently forwards `CF-Connecting-IP` as the real client IP on some public
Cloudflare-facing reverse proxy routes:

- `X-Real-IP: {http.request.header.CF-Connecting-IP}`
- `X-Forwarded-For: {http.request.header.CF-Connecting-IP}`

This is intended for the normal Cloudflare path:

1. Visitor connects to Cloudflare.
2. Cloudflare connects to the origin Caddy gateway.
3. Cloudflare adds `CF-Connecting-IP`.
4. Caddy passes that IP to the upstream service.

Currently affected deployed routes:

- `auth.ibbi.cc` -> Logto public core
- `xray-under-caddy.ibbi.cc` -> Xray under Caddy websocket upstream

Potential future affected route from the template:

- `support.ibbi.cc` -> Zammad, when Zammad is enabled

Routes not affected by this specific issue:

- `logto-admin.ibbi.cc` uses Caddy's direct `remote_host` and is guarded by the
  WireGuard CIDR before proxying.
- The base-domain subscription proxy route uses Caddy's direct `remote_host`.

### Current Behavior

Caddy trusts the `CF-Connecting-IP` header value directly. It does not currently
verify that the immediate peer connecting to the origin is actually a Cloudflare
edge IP.

### Impact

If an attacker can bypass Cloudflare and connect directly to the origin, they
may be able to forge `CF-Connecting-IP`. Logto and other upstream services could
then receive an incorrect client IP.

This can weaken audit logs, rate-limiting decisions, abuse investigation, and
any future access-control logic that relies on the apparent client IP.

Impact by route:

- Logto: inaccurate audit logs, sign-in risk signals, rate-limiting inputs, and
  future IP-based policy decisions.
- Xray under Caddy: inaccurate upstream source logging and abuse investigation.
- Zammad, if enabled later: inaccurate helpdesk audit logs, throttling inputs,
  and incident investigation context.

### Preferred Fix

Restrict origin access so only Cloudflare can reach public HTTP/HTTPS entry
points:

1. At the firewall layer, allow inbound `80/tcp` and `443/tcp` only from
   Cloudflare IP ranges.
2. Keep internal WireGuard-only services bound to WireGuard addresses.
3. Continue passing `CF-Connecting-IP` only after origin access is restricted.

### Alternatives

- Add Caddy matchers for Cloudflare IP ranges and only trust
  `CF-Connecting-IP` when the remote peer is a Cloudflare edge IP.
- Stop trusting `CF-Connecting-IP` and pass Caddy's direct `remote_ip` instead.
  This avoids spoofing but loses the original visitor IP behind Cloudflare.
