#!/bin/bash -ex

# mock runner is not setting up the system correctly
# https://issues.redhat.com/browse/CPDEVOPS-242
if [[ "$(rpm --eval "%dist")" == ".el8" ]]; then
	readarray -t pkgs < automation/check-patch.packages.el8stream
else
	readarray -t pkgs < automation/check-patch.packages
fi
dnf install -y "${pkgs[@]}"

if [[ "$(rpm --eval "%dist")" == ".el9" ]]; then
# ensure ansible-lint is not installed for CentOS Stream 9
# we are going to use ansible 2.11 with CentOS Stream 9 and we'll handle ansible
# in a different way.
dnf remove -y ansible-lint || true
fi

# ensure packages are really updated.
dnf distrosync -y

autopoint
autoreconf -ivf
if [[ "$(rpm --eval "%dist")" == ".el8" ]]; then
./configure
else
# On CentOS Stream 9 ansible will be handled differently due to ansible 2.11
./configure --disable-ansible-syntax-check
fi
make test

# make distcheck skipped due to bug afflicting automake.
# fc29: https://bugzilla.redhat.com/1716384
# fc30: https://bugzilla.redhat.com/1757854
# el8:  https://bugzilla.redhat.com/1759942

./automation/build-artifacts.sh

export PREFIX=$(mktemp -d /tmp/he-prefix.XXXXXX)
make install prefix="${PREFIX}"

mkdir -p exported-artifacts/tests

export HE_ANSIBLE_LOG_PATH=exported-artifacts/tests/filter-test-$(date -u +%Y%m%d%H%M%S).log
export ANSIBLE_STDOUT_CALLBACK=2_ovirt_logger
export ANSIBLE_CALLBACK_PLUGINS=src/ansible

ANSIBLE_LOG=exported-artifacts/tests/filter-test-ansible-output-$(date -u +%Y%m%d%H%M%S).log

ansible-playbook --inventory=localhost, -vvvvvv tests/ansible/playbooks/test_filtering.yml > "${ANSIBLE_LOG}" 2>&1
if grep 'secret_data' $HE_ANSIBLE_LOG_PATH; then
	echo Found non-filtered secrets in the log ^^^
	exit 1
fi
