# Ansible Infra

[English](README.md)

这是我的个人 Ansible 基础设施项目，用来初始化 VPS 节点、组建
WireGuard 内网、部署网关服务，并运行 Caddy、Postgres、Mailcow、
Zammad、Xray、Cloudflared 等应用栈。

## 项目结构

- `site.yml`：主 playbook，按基础层、网关层、应用层、控制面登记的顺序执行。
- `roles/base`：系统初始化、Docker 安装、WireGuard mesh。
- `roles/gateway`：Certbot 证书分发和 Caddy 反向代理。
- `roles/apps`：应用服务栈和备份任务。
- `.local/`：真实私有状态，包括 inventory、vault password、私有变量、证书和生成的客户端文件。这个目录被 Git 忽略。
- `.local.example/`：提交到仓库的私有状态骨架，不包含真实密钥。
- `.local_encrypted.vault`：`.local` 的加密恢复包。

## 初始化

从示例目录创建真实私有状态：

```bash
cp -R .local.example .local
chmod 600 .local/vault_password
```

然后把 `.local/` 里的所有 `REPLACE_ME` 占位符替换成真实值。

安装需要的 Ansible collections：

```bash
ansible-galaxy collection install -r collections/requirements.yml
```

默认 inventory 和 vault password 在 `ansible.cfg` 里配置：

```ini
inventory = .local/inventory.yml
vault_password_file = .local/vault_password
```

运行 playbook 前，确保 `.local/` 里已经包含各 role 需要的私有
inventory 和变量，例如 SSH key、WireGuard key、Cloudflare token、
数据库密码、Rclone 配置和应用 `.env` 模板。

## 常用命令

只检查语法，不连接主机：

```bash
ansible-playbook site.yml --syntax-check
```

运行轻量 lint：

```bash
python3 -m pip install -r requirements-dev.txt
ansible-lint site.yml
```

当前 `.ansible-lint` 从 `min` profile 起步，方便逐步接入 lint，而不会让个人
infra 风格一下子变成一堆噪音。

运行本地测试：

```bash
make test
```

这会检查 Python 辅助脚本、已提交 Bash 脚本、渲染后的 Bash 模板、JSON 和
Docker Compose 模板、inventory contract、格式、Ansible inventory、playbook
syntax 和 `ansible-lint`。

运行包含 Molecule 的完整测试：

```bash
make test-all
```

## Release

GitHub Actions 会在 push tag 时自动创建 release。Release job 会先跑
`make test`，然后从对应 tag 的源码树生成 source archive 和 `SHA256SUMS`。

```bash
git tag -a v0.2 -m "v0.2"
git push origin v0.2
```

tag 名包含 `-alpha`、`-beta`、`-rc` 或 `-pre` 时，会被标记为 pre-release。

运行全部 play：

```bash
ansible-playbook site.yml
```

只运行某一层或某个服务：

```bash
ansible-playbook site.yml --tags base
ansible-playbook site.yml --tags wireguard
ansible-playbook site.yml --tags caddy
ansible-playbook site.yml --tags postgres
ansible-playbook site.yml --tags zammad
```

## 私有状态备份

创建或刷新 `.local` 的加密备份包：

```bash
./encrypt_.local_folder.sh
```

`.local_encrypted.vault` 设计为可以提交到仓库的加密密文。真实 `.local/` 和
`.local/vault_password` 必须留在 Git 外面。建议使用唯一强密码，例如：

```bash
openssl rand -base64 32
```

不要把 `.local/` 里渲染出的文件粘贴到 issue、日志或上下文导出里。

## Proxy Control Plane 部署

这个仓库也可以部署 Go 写的 `proxy-control-plane` 服务本体。对应 role 会在目标
主机上拉取指定版本的 GHCR 镜像，写入 `/opt/proxy-control-plane` 运行文件，
执行 SQL migration，然后用 Docker Compose 启动 API。

示例私有变量：

```yaml
proxy_control_plane_enabled: true
proxy_control_plane_image: "ghcr.io/ziyan-c/proxy-control-plane:0.2"
proxy_control_plane_bind_host: "10.66.0.10"
proxy_control_plane_host_port: 9710
proxy_control_plane_env_file_src: "{{ playbook_dir }}/.local/role_vars/proxy_control_plane/app.env"
```

把 `.local/role_vars/proxy_control_plane/app.env` 创建成指向真实
`../proxy-control-plane/.local/app.env` 的 symlink。role 只会复制这个 env 文件到
目标主机的 `/opt/proxy-control-plane/app.env`，权限为 `0600`，Docker Compose
通过 `env_file` 加载它。

所有 `PCP_*` 运行参数都应该放在这个 env 文件里，包括
`PCP_LISTEN_ADDR=0.0.0.0:9710`、runtime sync、traffic sync 和 maintenance
retention。不要把整个 `proxy-control-plane/.local/` 目录 symlink 或复制进
Ansible，Compose 只需要这一个 env 文件。

如果使用私有 GHCR 镜像，可以设置 `proxy_control_plane_ghcr_username` 和
`proxy_control_plane_ghcr_token`。公开 GHCR 镜像不需要登录。

## Proxy Control Plane 节点同步

这个仓库可以把已经部署好的 Xray 节点登记到 Go `proxy-control-plane` 服务里。
同步默认关闭。开启后，Ansible 会从 `xray_under_caddy_nodes` 和 `xray_nodes`
收集主机，组装客户端视角的节点 payload，然后调用：

```text
POST /admin/nodes/sync
```

Ansible 不直接写 PostgreSQL。

这个 play 应该从能通过 WireGuard 访问 control-plane API 的主机上运行。示例
inventory 里，`proxy_control_plane_sync_nodes` 和 `proxy_control_plane_nodes`
是同一台主机，所以 node sync 不依赖本地笔记本是否接入私有 mesh。

`.local/group_vars/all.yml` 里需要的私有变量示例：

```yaml
proxy_control_plane_node_sync_enabled: true
proxy_control_plane_api_url: "https://control-plane.example.com"
proxy_control_plane_admin_email: "admin@example.com"
proxy_control_plane_admin_password: "..."
xray_public_key: "..."
```

如果已经有可用 bearer token，也可以用 `proxy_control_plane_access_token` 替代
admin email/password。对 Xray Reality 来说，`xray_private_key` 仍然只用于
服务器端 Xray 配置；`xray_public_key` 是发给 control plane、用于生成订阅的
客户端值。

支持在 inventory 或 host vars 里按主机覆盖：

```yaml
proxy_control_plane_node_name: xray-fr-1
proxy_control_plane_region: fr
proxy_control_plane_node_enabled: true
xray_public_host: node.example.com
xray_under_caddy_public_host: xray-under-caddy.example.com
```

如果省略 `proxy_control_plane_node_enabled`，Ansible 会在 `/admin/nodes/sync`
payload 里完全不发送 `enabled` 字段，让 control plane 保留数据库里已有的启停
状态。只有当你明确希望 inventory 管理节点可用性时，才设置这个变量。

Runtime API 管理也是可选的，默认关闭。开启后，Xray Reality 和 Xray under
Caddy 只在配置的 WireGuard 地址上暴露 gRPC 管理 API。静态 clients 默认是空
列表，托管用户由 `proxy-control-plane` 通过 runtime API 添加。两个 role 默认
都使用 `10085` 端口，每个节点把这个端口绑定到自己的 WireGuard IP。

这个 API 会启用：

- `HandlerService`：用于用户增删同步。
- `StatsService`：用于流量统计。
- `stats: {}` 和用户上下行统计 policy：让 control plane 可以通过 Xray stats API 汇总 VLESS 流量。

```yaml
proxy_control_plane_runtime_api_enabled: true
proxy_control_plane_runtime_api_host: "10.66.0.1"
proxy_control_plane_runtime_api_tag: proxy-control-plane-api
proxy_control_plane_runtime_inbound_tag: proxy-control-plane-vless-in
proxy_control_plane_xray_runtime_api_port: 10085
proxy_control_plane_xray_under_caddy_runtime_api_port: 10085
```

不同节点有不同 WireGuard IP 时，要按 host 设置
`proxy_control_plane_runtime_api_host`。Ansible 会把这些 runtime API 字段登记到
control plane；用户增删 reconciliation 仍然由 `proxy-control-plane` 自己负责。

订阅发布也可以交给 control plane。Caddy 只在主 `base_domain` 站点上代理公开
订阅路径 `/xray/sub/{token}`；Xray under Caddy 域名只负责代理流量和静态文件兜底。
长期事实来源仍然是 PostgreSQL，Caddy 会把公开路径重写回 control-plane 上游真实
路径 `/sub/{token}`，只转发托管订阅 token 请求。

```yaml
proxy_control_plane_subscription_proxy_enabled: true
proxy_control_plane_subscription_proxy_upstream: "http://10.66.0.10:9710"
proxy_control_plane_subscription_public_path: /xray/sub
```

旧公开订阅文件应先导入 control plane，然后在客户端迁移完成前继续作为静态文件
保留。当前 control-plane API 只服务 `/sub/{token}` 形式的托管订阅；Caddy 对外
暴露 `/xray/sub/{token}`，再重写回上游 `/sub/{token}`。旧静态路径应该继续由
Caddy 的 file server 处理，不要代理。

## 安全说明

- 多个 role 会管理 root 级别主机状态，例如 SSH、firewalld、swap、Docker、cron 和 service 文件。
- `roles/base/system_init/defaults/main.yml` 暴露了几个高影响开关：
  - `system_dist_upgrade_enabled`
  - `system_disable_ufw_apparmor`
  - `root_authorized_keys_exclusive`
- 包含密钥的渲染文件应该保持 owner-only 可读，也就是 `0600`；脚本需要执行时再给 root 执行权限。
- `collect_all_files.py` 会跳过 `.local/`，避免调试 bundle 包含私有 inventory、token 或 key material。
