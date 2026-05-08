# proxy-control-plane private env link

Create this file in your private `.local/` tree as a symlink to the real
`proxy-control-plane` app env file:

```bash
mkdir -p .local/role_vars/proxy_control_plane
ln -s /path/to/proxy-control-plane/.local/app.env .local/role_vars/proxy_control_plane/app.env
```

The Ansible role copies only this `app.env` file to the target host. Do not
copy the entire `proxy-control-plane/.local/` directory.
