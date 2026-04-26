ANSIBLE_ENV = ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote

.PHONY: test test-python test-bash test-ansible lint syntax inventory

test: test-python test-bash test-ansible

test-python:
	python3 -m unittest discover -s tests -p 'test_*.py'

test-bash:
	tests/test_shell_static.sh

test-ansible:
	tests/test_ansible_static.sh

lint:
	$(ANSIBLE_ENV) ansible-lint site.yml

syntax:
	$(ANSIBLE_ENV) ansible-playbook -i .local.example/inventory.yml site.yml --syntax-check

inventory:
	$(ANSIBLE_ENV) ansible-inventory -i .local.example/inventory.yml --list >/dev/null
