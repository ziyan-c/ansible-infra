from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


@dataclass(frozen=True)
class Settings:
    bind_host: str
    rag_proxy_port: int
    llm_proxy_port: int
    proxy_password: str
    allow_empty_password: bool
    rag_base_url: str
    llm_base_url: str
    upstream_timeout_seconds: float
    manage_ssh_tunnel: bool
    ssh_user: str
    ssh_host: str
    ssh_port: int
    ssh_password: str
    ssh_key_path: str
    ssh_bind_host: str
    local_rag_port: int
    local_llm_port: int
    remote_rag_host: str
    remote_rag_port: int
    remote_llm_host: str
    remote_llm_port: int
    log_tunnel_command: bool

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        local_rag_port = _int("NEO_LOCAL_RAG_PORT", 18000)
        local_llm_port = _int("NEO_LOCAL_LLM_PORT", 18080)
        return cls(
            bind_host=os.environ.get("NEO_BIND_HOST", os.environ.get("NEO_HOST", "0.0.0.0")),
            rag_proxy_port=_int("NEO_RAG_PROXY_PORT", 8000),
            llm_proxy_port=_int("NEO_LLM_PROXY_PORT", 8080),
            proxy_password=os.environ.get("NEO_PROXY_PASSWORD", ""),
            allow_empty_password=_bool("NEO_PROXY_PASSWORD_ALLOW_EMPTY", False),
            rag_base_url=os.environ.get("NEO_RAG_BASE_URL", f"http://127.0.0.1:{local_rag_port}").rstrip("/"),
            llm_base_url=os.environ.get("NEO_LLM_BASE_URL", f"http://127.0.0.1:{local_llm_port}").rstrip("/"),
            upstream_timeout_seconds=float(os.environ.get("NEO_UPSTREAM_TIMEOUT_SECONDS", "300")),
            manage_ssh_tunnel=_bool("NEO_MANAGE_SSH_TUNNEL", True),
            ssh_user=os.environ.get("NEO_SSH_USER", "root"),
            ssh_host=os.environ.get("NEO_SSH_HOST", ""),
            ssh_port=_int("NEO_SSH_PORT", 22),
            ssh_password=os.environ.get("NEO_SSH_PASSWORD", ""),
            ssh_key_path=os.environ.get("NEO_SSH_KEY_PATH", ""),
            ssh_bind_host=os.environ.get("NEO_SSH_BIND_HOST", "127.0.0.1"),
            local_rag_port=local_rag_port,
            local_llm_port=local_llm_port,
            remote_rag_host=os.environ.get("NEO_REMOTE_RAG_HOST", "localhost"),
            remote_rag_port=_int("NEO_REMOTE_RAG_PORT", 8000),
            remote_llm_host=os.environ.get("NEO_REMOTE_LLM_HOST", "localhost"),
            remote_llm_port=_int("NEO_REMOTE_LLM_PORT", 8080),
            log_tunnel_command=_bool("NEO_LOG_TUNNEL_COMMAND", False),
        )

    def validate(self) -> None:
        if not self.proxy_password and not self.allow_empty_password:
            raise RuntimeError("Set NEO_PROXY_PASSWORD or NEO_PROXY_PASSWORD_ALLOW_EMPTY=1.")
        if self.manage_ssh_tunnel and not self.ssh_host:
            raise RuntimeError("Set NEO_SSH_HOST or disable NEO_MANAGE_SSH_TUNNEL.")
