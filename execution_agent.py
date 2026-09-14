import ansible_runner

def run_remediation(playbook: str, extravars: dict) -> dict:
    result = ansible_runner.run(
        private_data_dir="infra/ansible",
        playbook=f"playbooks/remediation/{playbook}",
        extravars=extravars,
    )
    return {
        "status": result.status,
        "rc": result.rc,
        "events": list(result.events),
    }