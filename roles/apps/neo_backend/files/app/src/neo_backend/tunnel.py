from __future__ import annotations

import asyncio
import shlex
from asyncio.subprocess import Process

from .config import Settings


class SSHTunnelManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.process: Process | None = None

    def build_command(self) -> list[str]:
        settings = self.settings
        ssh_command = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "ExitOnForwardFailure=yes",
            "-N",
            "-L",
            f"{settings.ssh_bind_host}:{settings.local_rag_port}:{settings.remote_rag_host}:{settings.remote_rag_port}",
            "-L",
            f"{settings.ssh_bind_host}:{settings.local_llm_port}:{settings.remote_llm_host}:{settings.remote_llm_port}",
        ]
        if settings.ssh_key_path:
            ssh_command.extend(["-i", settings.ssh_key_path])
        ssh_command.extend([f"{settings.ssh_user}@{settings.ssh_host}", "-p", str(settings.ssh_port)])

        if settings.ssh_password:
            return ["sshpass", "-p", settings.ssh_password, *ssh_command]
        return ssh_command

    def masked_command(self) -> str:
        command = self.build_command()
        masked = []
        skip_next = False
        masked_password = False
        for item in command:
            if skip_next:
                masked.append("********")
                skip_next = False
                masked_password = True
                continue
            masked.append(item)
            if item == "-p" and masked[0] == "sshpass" and not masked_password:
                skip_next = True
        return " ".join(shlex.quote(part) for part in masked)

    async def start(self) -> None:
        if not self.settings.manage_ssh_tunnel:
            return
        if self.process and self.process.returncode is None:
            return

        command = self.build_command()
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.sleep(0.8)
        if self.process.returncode is not None:
            stderr = b""
            if self.process.stderr:
                stderr = await self.process.stderr.read()
            raise RuntimeError(f"SSH tunnel exited early: {stderr.decode(errors='replace')}")

    async def stop(self) -> None:
        if not self.process or self.process.returncode is not None:
            return
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()

    def status(self) -> dict[str, object]:
        if not self.settings.manage_ssh_tunnel:
            return {"enabled": False, "running": False}
        return {
            "enabled": True,
            "running": self.process is not None and self.process.returncode is None,
            "pid": self.process.pid if self.process else None,
        }
