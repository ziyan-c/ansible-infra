import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_json(command):
    env = os.environ.copy()
    env.setdefault("ANSIBLE_HOME", str(REPO_ROOT / ".ansible"))
    env.setdefault("ANSIBLE_LOCAL_TEMP", "/tmp/ansible-local")
    env.setdefault("ANSIBLE_REMOTE_TEMP", "/tmp/ansible-remote")

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


@unittest.skipIf(shutil.which("yq") is None, "yq is required for YAML contract tests")
class InventoryContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = run_json(
            ["ansible-inventory", "-i", ".local.example/inventory.yml", "--list"]
        )
        cls.site = run_json(["yq", "-o=json", ".", "site.yml"])
        cls.all_vars = run_json(["yq", "-o=json", ".", ".local.example/group_vars/all.yml"])
        cls.hosts = set(cls.inventory["_meta"]["hostvars"])
        cls.groups = {
            name: set(data.get("hosts", []))
            for name, data in cls.inventory.items()
            if isinstance(data, dict)
        }

    def test_site_play_groups_exist_and_are_populated(self):
        missing = []
        empty = []

        for play in self.site:
            group = play["hosts"]
            if group not in self.groups:
                missing.append(group)
            elif not self.groups[group]:
                empty.append(group)

        self.assertEqual(missing, [])
        self.assertEqual(empty, [])

    def test_site_roles_exist(self):
        missing = []

        for play in self.site:
            for role in play.get("roles", []):
                role_name = role["role"] if isinstance(role, dict) else role
                role_path = REPO_ROOT / "roles" / role_name
                if not role_path.is_dir():
                    missing.append(role_name)

        self.assertEqual(missing, [])

    def test_deploy_nodes_resolve_to_inventory_hosts(self):
        deploy_nodes = {
            key: value
            for key, value in self.all_vars.items()
            if key.startswith("deploy_node_")
        }
        missing = {
            key: value for key, value in deploy_nodes.items() if value not in self.hosts
        }

        self.assertEqual(missing, {})

    def test_deploy_nodes_match_their_service_groups(self):
        expected_groups = {
            "deploy_node_neo_v2ray": "v2ray_nodes",
            "deploy_node_zammad": "zammad_nodes",
            "deploy_node_postgres": "db_postgres_nodes",
            "deploy_node_mailcow": "mail_nodes",
        }
        mismatches = {}

        for var_name, group_name in expected_groups.items():
            host = self.all_vars[var_name]
            if host not in self.groups[group_name]:
                mismatches[var_name] = {"host": host, "group": group_name}

        self.assertEqual(mismatches, {})

    def test_wireguard_servers_match_inventory_and_vpn_group(self):
        wg_servers = self.all_vars["wg_servers"]
        vpn_hosts = self.groups["vpn_mesh_nodes"]
        missing = []
        outside_vpn_group = []

        for server in wg_servers.values():
            hostname = server["hostname"]
            if hostname not in self.hosts:
                missing.append(hostname)
            if hostname not in vpn_hosts:
                outside_vpn_group.append(hostname)

        self.assertEqual(missing, [])
        self.assertEqual(outside_vpn_group, [])

    def test_wireguard_ip_suffixes_are_unique(self):
        suffixes = []

        for server in self.all_vars["wg_servers"].values():
            suffixes.append(server["ip_suffix"])
        for client in self.all_vars["wg_clients"].values():
            suffixes.append(client["ip_suffix"])

        self.assertEqual(len(suffixes), len(set(suffixes)))

    def test_tunnel_hosts_have_cloudflare_tunnel_tokens(self):
        missing = []

        for host in self.groups["tunnel_nodes"]:
            token = self.inventory["_meta"]["hostvars"][host].get("cf_tunnel_token")
            if not token:
                missing.append(host)

        self.assertEqual(missing, [])
