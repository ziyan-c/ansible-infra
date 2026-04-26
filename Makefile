ANSIBLE_ENV = ANSIBLE_HOME=$(CURDIR)/.ansible ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote
MOLECULE_ENV = $(ANSIBLE_ENV) ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=false

.PHONY: test test-all test-python test-pytest test-bash test-bats test-format test-templates test-ansible test-molecule lint syntax inventory

test: test-python test-bash test-bats test-format test-templates test-ansible

test-all: test test-molecule

test-python:
	python3 -m unittest discover -s tests -p 'test_*.py'

test-pytest:
	pytest tests

test-bash:
	tests/test_shell_static.sh

test-bats:
	tests/test_bats.sh

test-format:
	tests/test_format_static.sh

test-templates:
	tests/test_templates_static.sh

test-ansible:
	tests/test_ansible_static.sh

test-molecule:
	cd roles/apps/v2ray && $(MOLECULE_ENV) molecule reset -s default >/dev/null 2>&1 || true
	cd roles/apps/v2ray && $(MOLECULE_ENV) molecule test -s default

lint:
	$(ANSIBLE_ENV) ansible-lint site.yml

syntax:
	$(ANSIBLE_ENV) ansible-playbook -i .local.example/inventory.yml site.yml --syntax-check

inventory:
	$(ANSIBLE_ENV) ansible-inventory -i .local.example/inventory.yml --list >/dev/null
