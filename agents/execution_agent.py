import ansible_runner
import json
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_PLAYBOOKS = {"restart_deployment.yml", "scale_replicas.yml"}

def run_remediation(playbook: str, extravars: dict) -> dict:
    if playbook not in ALLOWED_PLAYBOOKS:
        raise ValueError(f"Playbook '{playbook}' não é uma ação de remediação permitida.")

    result = ansible_runner.run(
        private_data_dir="infra/ansible",
        playbook=f"playbooks/remediation/{playbook}",
        extravars=extravars,
    )

    audit_entry = None
    for event in result.events:
        task = event.get("event_data", {}).get("task", "")
        if "auditoria" in task and event.get("event") == "runner_on_ok":
            audit_entry = event["event_data"]["res"]["msg"]

    audit_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "playbook": playbook,
        "extravars": extravars,
        "status": result.status,
        "rc": result.rc,
        "audit": audit_entry,
    }

    log_path = Path("logs") / f"remediation_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(audit_record) + "\n")

    return audit_record