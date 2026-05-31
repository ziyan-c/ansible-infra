import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    shutil.which("yq") is None,
    reason="yq is required for YAML contract tests",
)


def run_json(command):
    env = os.environ.copy()
    env.setdefault("ANSIBLE_HOME", str(REPO_ROOT / ".ansible"))
    env.setdefault("ANSIBLE_LOCAL_TEMP", "/tmp/ansible-local")
    env.setdefault("ANSIBLE_REMOTE_TEMP", "/tmp/ansible-remote")
    env.setdefault(
        "ANSIBLE_VAULT_PASSWORD_FILE",
        str(REPO_ROOT / ".local.example/vault_password"),
    )
    env.setdefault("ANSIBLE_PRIVATE_STATE_DIR", str(REPO_ROOT / ".local.example"))

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def inventory_context():
    inventory = run_json(
        ["ansible-inventory", "-i", ".local.example/inventory.yml", "--list"]
    )
    site = run_json(["yq", "-o=json", ".", "site.yml"])
    all_vars = run_json(["yq", "-o=json", ".", ".local.example/group_vars/all.yml"])
    wg_vars = run_json(
        ["yq", "-o=json", ".", ".local.example/role_vars/vpn_wireguard/main.yml"]
    )
    all_vars.update(wg_vars)
    hosts = set(inventory["_meta"]["hostvars"])
    groups = {
        name: set(data.get("hosts", []))
        for name, data in inventory.items()
        if isinstance(data, dict)
    }
    return {
        "inventory": inventory,
        "site": site,
        "all_vars": all_vars,
        "hosts": hosts,
        "groups": groups,
    }


def test_site_play_groups_exist_and_are_populated(inventory_context):
    missing = []
    empty = []

    for play in inventory_context["site"]:
        group = play["hosts"]
        if group not in inventory_context["groups"]:
            missing.append(group)
        elif not inventory_context["groups"][group]:
            empty.append(group)

    assert missing == []
    assert empty == []


def test_site_roles_exist(inventory_context):
    missing = []

    for play in inventory_context["site"]:
        for role in play.get("roles", []):
            role_name = role["role"] if isinstance(role, dict) else role
            role_path = REPO_ROOT / "roles" / role_name
            if not role_path.is_dir():
                missing.append(role_name)

    assert missing == []


def test_deploy_nodes_resolve_to_inventory_hosts(inventory_context):
    deploy_nodes = {
        key: value
        for key, value in inventory_context["all_vars"].items()
        if key.startswith("deploy_node_")
    }
    disabled_deploy_nodes = {
        f"deploy_node_{service.removesuffix('_enabled')}"
        for service, enabled in inventory_context["all_vars"].items()
        if service.endswith("_enabled")
        and not enabled
        and f"deploy_node_{service.removesuffix('_enabled')}" in deploy_nodes
    }
    missing = {
        key: value
        for key, value in deploy_nodes.items()
        if key not in disabled_deploy_nodes and value not in inventory_context["hosts"]
    }

    assert missing == {}


def test_deploy_nodes_match_their_service_groups(inventory_context):
    expected_groups = {
        "deploy_node_xray_under_caddy": "xray_under_caddy_nodes",
        "deploy_node_zammad": "zammad_nodes",
        "deploy_node_postgres": "db_postgres_nodes",
        "deploy_node_mailcow": "mail_nodes",
        "deploy_node_sftpgo": "sftpgo_nodes",
    }
    mismatches = {}
    disabled_deploy_nodes = {
        f"deploy_node_{service.removesuffix('_enabled')}"
        for service, enabled in inventory_context["all_vars"].items()
        if service.endswith("_enabled")
        and not enabled
        and f"deploy_node_{service.removesuffix('_enabled')}" in expected_groups
    }

    for var_name, group_name in expected_groups.items():
        if var_name in disabled_deploy_nodes:
            continue
        host = inventory_context["all_vars"][var_name]
        if host not in inventory_context["groups"][group_name]:
            mismatches[var_name] = {"host": host, "group": group_name}

    assert mismatches == {}


def test_proxy_control_plane_sync_runs_from_control_plane_node(inventory_context):
    sync_hosts = inventory_context["groups"]["proxy_control_plane_sync_nodes"]
    control_plane_hosts = inventory_context["groups"]["proxy_control_plane_nodes"]

    assert sync_hosts <= control_plane_hosts
    assert "localhost" not in sync_hosts


def test_wireguard_servers_match_inventory_and_vpn_group(inventory_context):
    wg_servers = inventory_context["all_vars"]["wg_servers"]
    vpn_hosts = inventory_context["groups"]["vpn_mesh_nodes"]
    missing = []
    outside_vpn_group = []

    for server in wg_servers.values():
        hostname = server["hostname"]
        if hostname not in inventory_context["hosts"]:
            missing.append(hostname)
        if hostname not in vpn_hosts:
            outside_vpn_group.append(hostname)

    assert missing == []
    assert outside_vpn_group == []


def test_wireguard_ip_suffixes_are_unique(inventory_context):
    suffixes = []

    for server in inventory_context["all_vars"]["wg_servers"].values():
        suffixes.append(server["ip_suffix"])
    for client in inventory_context["all_vars"]["wg_clients"].values():
        suffixes.append(client["ip_suffix"])
    for spoke in inventory_context["all_vars"].get("wg_spoke_nodes", {}).values():
        suffixes.append(spoke["ip_suffix"])

    assert len(suffixes) == len(set(suffixes))


def test_wireguard_spoke_hubs_are_explicit_public_servers(inventory_context):
    wg_servers = inventory_context["all_vars"]["wg_servers"]
    wg_spokes = inventory_context["all_vars"].get("wg_spoke_nodes", {})
    invalid = {}

    for name, spoke in wg_spokes.items():
        hub = spoke.get("hub")
        if hub not in wg_servers:
            invalid[name] = {"hub": hub, "reason": "unknown hub"}
        elif not wg_servers[hub].get("endpoint"):
            invalid[name] = {"hub": hub, "reason": "hub has no public endpoint"}

    assert invalid == {}


def test_wireguard_preshared_keys_cover_all_peer_pairs(inventory_context):
    all_vars = inventory_context["all_vars"]
    wg_servers = all_vars["wg_servers"]
    wg_clients = all_vars["wg_clients"]
    wg_spokes = all_vars.get("wg_spoke_nodes", {})
    wg_psks = all_vars.get("wg_preshared_keys", {})
    server_psks = wg_psks.get("server_pairs", {})
    client_psks = wg_psks.get("client_pairs", {})
    spoke_psks = wg_psks.get("spoke_pairs", {})

    expected_server_pairs = {
        "__".join(sorted([left, right]))
        for index, left in enumerate(wg_servers)
        for right in list(wg_servers)[index + 1 :]
    }
    expected_client_pairs = {
        f"{client}__{server}"
        for client in wg_clients
        for server in wg_servers
    }
    expected_spoke_pairs = {
        f"{spoke}__{attrs['hub']}"
        for spoke, attrs in wg_spokes.items()
    }

    assert set(server_psks) == expected_server_pairs
    assert set(client_psks) == expected_client_pairs
    assert set(spoke_psks) == expected_spoke_pairs
    assert all(value for value in server_psks.values())
    assert all(value for value in client_psks.values())
    assert all(value for value in spoke_psks.values())


def test_tunnel_hosts_have_cloudflare_tunnel_tokens(inventory_context):
    cloudflared_vars = run_json(
        ["yq", "-o=json", ".", ".local.example/role_vars/cloudflared/main.yml"]
    )

    assert inventory_context["groups"]["tunnel_nodes"]
    assert cloudflared_vars.get("cf_tunnel_token")
