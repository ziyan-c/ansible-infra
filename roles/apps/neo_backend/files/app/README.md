# Neo Backend Temporary Service

This is a compact replacement for the `ansible-infra` Neo backend compose setup,
intended to run **behind Caddy**:

- Caddy reverse proxies `/api/rag*` to `neo-backend:8000`.
- Caddy reverse proxies `/api/llm*` to `neo-backend:8080`.
- `neo-backend` authenticates requests on both ports.
- Ansible can also bind the same authenticated `8000` and `8080` proxy ports to
  the host WireGuard address for private-network access.
- `neo-backend` optionally starts an SSH tunnel to the 5090 compute node.
- The tunnel maps remote `localhost:8000` and `localhost:8080` to local internal
  ports `18000` and `18080`.
- The authenticated proxy forwards port `8000 -> 18000` and `8080 -> 18080`.

The source behavior came from:

- `ansible-infra/roles/apps/neo_backend/templates/docker-compose.yml.j2`
- `ansible-infra/roles/gateway/caddy/templates/Caddyfile.j2`
- the earlier local `chatbot/ssh-tunnel.sh` pattern

## Route Map

```text
Caddy /api/rag* -> neo-backend:8000/* -> tunnel local :18000 -> 5090 :8000
Caddy /api/llm* -> neo-backend:8080/* -> tunnel local :18080 -> 5090 :8080
WireGuard http://<neo-wg-ip>:8000/* -> neo-backend:8000/* -> tunnel local :18000 -> 5090 :8000
WireGuard http://<neo-wg-ip>:8080/* -> neo-backend:8080/* -> tunnel local :18080 -> 5090 :8080
```

The `/api/rag` and `/api/llm` prefixes are stripped before proxying, matching
the Caddy `uri strip_prefix` behavior in `ansible-infra`.

Equivalent Caddy shape:

```caddyfile
handle /api/rag* {
    uri strip_prefix /api/rag
    reverse_proxy neo-backend:8000
}

handle /api/llm* {
    uri strip_prefix /api/llm
    reverse_proxy neo-backend:8080
}
```

## Auth

Set `NEO_PROXY_PASSWORD`. Clients may pass it as one of:

- `Authorization: Bearer <password>`
- `X-Proxy-Password: <password>`
- `?password=<password>`

## Run Locally

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -e .
neo-backend
```

Health checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8080/health
```

With Docker:

```bash
cp .env.example .env
docker compose up --build
```

The compose file joins the external `web-proxy` network. In production, Ansible
can additionally publish `8000` and `8080` on the host WireGuard address so
private clients still go through `neo-backend` authentication.

## Important

Do not commit real SSH passwords or proxy passwords. Put them in `.env` or your
secret manager. If password-based SSH is used in Docker, the image installs
`sshpass`; key-based auth is preferred when possible.
