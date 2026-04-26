ANSIBLE_ENV = ANSIBLE_HOME=$(CURDIR)/.ansible ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote ANSIBLE_COLLECTIONS_PATH=$(CURDIR)/.ansible/collections
MOLECULE_ENV = $(ANSIBLE_ENV)

.PHONY: test test-all test-python test-pytest test-bash test-format test-templates test-ansible test-molecule lint syntax inventory

test: test-python test-bash test-format test-templates test-ansible

test-all: test test-molecule

test-python:
	pytest tests

test-pytest: test-python

test-bash:
	tests/test_shell_static.sh

test-format:
	tests/test_format_static.sh

test-templates:
	tests/test_templates_static.sh

test-ansible:
	tests/test_ansible_static.sh

test-molecule:
	$(MOLECULE_ENV) molecule reset -s default >/dev/null 2>&1 || true
	$(MOLECULE_ENV) molecule test -s default
	cd roles/apps/v2ray && $(MOLECULE_ENV) molecule reset -s default >/dev/null 2>&1 || true
	cd roles/apps/v2ray && $(MOLECULE_ENV) molecule test -s default
	cd roles/apps/xray && $(MOLECULE_ENV) molecule reset -s default >/dev/null 2>&1 || true
	cd roles/apps/xray && $(MOLECULE_ENV) molecule test -s default
	cd roles/apps/cloudflared && $(MOLECULE_ENV) molecule reset -s default >/dev/null 2>&1 || true
	cd roles/apps/cloudflared && $(MOLECULE_ENV) molecule test -s default
	cd roles/apps/neo_backend && $(MOLECULE_ENV) molecule reset -s default >/dev/null 2>&1 || true
	cd roles/apps/neo_backend && $(MOLECULE_ENV) molecule test -s default

lint:
	$(ANSIBLE_ENV) ansible-lint site.yml

syntax:
	$(ANSIBLE_ENV) ansible-playbook -i .local.example/inventory.yml site.yml --syntax-check

inventory:
	$(ANSIBLE_ENV) ansible-inventory -i .local.example/inventory.yml --list >/dev/null
