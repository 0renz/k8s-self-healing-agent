"""
Agente de Diagnóstico.

Consulta métricas do Prometheus relacionadas ao namespace monitorado, e usa
um LLM para interpretar essas métricas e propor uma hipótese de causa raiz.

O diagnóstico produzido é estruturado (JSON) para que o Agente de Decisão
consiga consumi-lo programaticamente, sem parsear texto livre.
"""

import json
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Any, TypedDict

import openai
#import anthropic
import yaml

from client_prometheus import PrometheusClientError, query

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH)

# --- Configuração compartilhada com os playbooks de remediação ---

SAFETY_VARS_PATH = (
    Path(__file__).parent.parent
    / "infra"
    / "ansible"
    / "playbooks"
    / "remediation"
    / "vars"
    / "safety.yml"
)


def _load_safety_config() -> dict[str, Any]:
    """Lê a mesma allowlist usada pelos playbooks Ansible, para evitar duas fontes de verdade."""
    with open(SAFETY_VARS_PATH) as f:
        return yaml.safe_load(f)


SAFETY_CONFIG = _load_safety_config()
ALLOWED_NAMESPACES: list[str] = SAFETY_CONFIG["allowed_namespaces"]
ALLOWED_DEPLOYMENTS: list[str] = SAFETY_CONFIG["allowed_deployments"]

#ANTHROPIC_MODEL = os.getenv("DIAGNOSTIC_AGENT_MODEL", "claude-sonnet-5")
#OPENAI_MODEL = os.getenv("DIAGNOSTIC_AGENT_MODEL", "gpt-4o")
LLM_MODEL = os.getenv("DIAGNOSTIC_AGENT_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")


class Diagnosis(TypedDict):
    anomaly_detected: bool
    affected_deployment: str | None
    anomaly_type: str  # "crashloop" | "high_memory" | "high_error_rate" | "unknown" | "none"
    root_cause_hypothesis: str
    confidence: float  # 0.0 a 1.0
    evidence: list[str]


# --- Coleta de métricas ---

def _collect_metrics(namespace: str) -> dict[str, Any]:
    """
    Coleta um snapshot das métricas relevantes para diagnóstico de anomalias
    no namespace informado. Cada consulta é isolada: se uma falhar, as outras
    continuam, e o erro fica registrado no próprio snapshot.
    """
    metrics: dict[str, Any] = {}

    queries = {
        "pod_restarts_10m": (
            f'increase(kube_pod_container_status_restarts_total{{namespace="{namespace}"}}[10m])'
        ),
        "pod_phase_not_running": (
            f'kube_pod_status_phase{{namespace="{namespace}", phase!="Running"}} == 1'
        ),
        "memory_usage_ratio": (
            f'container_memory_working_set_bytes{{namespace="{namespace}", container!=""}} '
            f'/ on(namespace, pod, container) '
            f'kube_pod_container_resource_limits{{namespace="{namespace}", resource="memory"}}'
        ),
        "otel_collector_up": 'up{job=~".*otel-collector.*"}',
    }

    for label, promql in queries.items():
        try:
            metrics[label] = query(promql)
        except PrometheusClientError as exc:
            metrics[label] = {"error": str(exc)}

    return metrics


# --- Diagnóstico via LLM ---

SYSTEM_PROMPT = """\
Você é um agente de diagnóstico de SRE especializado em Kubernetes.
Você recebe um snapshot de métricas do Prometheus e deve identificar se há
uma anomalia, qual deployment é afetado, e uma hipótese de causa raiz.

Responda APENAS com um objeto JSON válido, sem markdown, sem texto antes ou
depois, no seguinte formato exato:

{{
  "anomaly_detected": true | false,
  "affected_deployment": "<nome-do-deployment>" | null,
  "anomaly_type": "crashloop" | "high_memory" | "high_error_rate" | "unknown" | "none",
  "root_cause_hypothesis": "<explicação curta e objetiva>",
  "confidence": <número entre 0.0 e 1.0>,
  "evidence": ["<métrica ou observação que sustenta a hipótese>", ...]
}}

Regras:
- Se as métricas não indicarem nenhuma anomalia, retorne anomaly_detected: false
  e anomaly_type: "none".
- "affected_deployment" só pode ser um destes valores, ou null: {deployments}
- Nunca invente métricas que não estejam no snapshot fornecido.
- Se o snapshot contiver erros de coleta, mencione isso em "evidence" e reduza
  a confiança do diagnóstico proporcionalmente.
"""


def _build_user_prompt(namespace: str, metrics: dict[str, Any]) -> str:
    return (
        f"Namespace monitorado: {namespace}\n\n"
        f"Snapshot de métricas (JSON):\n{json.dumps(metrics, indent=2, default=str)}"
    )


def _parse_llm_response(raw_text: str) -> Diagnosis:
    """Remove eventuais cercas de código e faz o parse do JSON retornado pelo LLM."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM retornou JSON inválido: {raw_text!r}") from exc

    return parsed  # type: ignore[return-value]


def _validate_diagnosis(diagnosis: Diagnosis) -> Diagnosis:
    """
    Segunda camada de segurança: mesmo que o LLM alucine um deployment fora
    da allowlist, o diagnóstico é neutralizado antes de chegar ao Agente de
    Decisão.
    """
    affected = diagnosis.get("affected_deployment")
    if affected is not None and affected not in ALLOWED_DEPLOYMENTS:
        diagnosis["evidence"] = diagnosis.get("evidence", []) + [
            f"Deployment '{affected}' fora da allowlist {ALLOWED_DEPLOYMENTS}; diagnóstico invalidado."
        ]
        diagnosis["affected_deployment"] = None
        diagnosis["anomaly_detected"] = False
        diagnosis["anomaly_type"] = "unknown"
        diagnosis["confidence"] = 0.0

    return diagnosis


def diagnose(namespace: str = "sample-app") -> Diagnosis:
    """
    Ponto de entrada principal do Agente de Diagnóstico.
    Coleta métricas do namespace e retorna um diagnóstico estruturado.
    """
    if namespace not in ALLOWED_NAMESPACES:
        raise ValueError(
            f"Namespace '{namespace}' não está na allowlist: {ALLOWED_NAMESPACES}"
        )

    metrics = _collect_metrics(namespace)
    
    client = openai.OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(deployments=ALLOWED_DEPLOYMENTS)},
            {"role": "user", "content": _build_user_prompt(namespace, metrics)},
        ],
    )


# 'NoneType' object is not subscriptable
    raw_text = response.choices[0].message.content if response.choices else None
    if raw_text is None:
        raise ValueError("LLM retornou resposta vazia.")
    diagnosis = _parse_llm_response(raw_text)
    return _validate_diagnosis(diagnosis)


# --- Nó do LangGraph ---
# graph.py ainda vai definir o schema de estado compartilhado entre os agentes;
# por ora, este nó espera e devolve um dict com a chave "diagnosis".

def diagnostic_node(state: dict[str, Any]) -> dict[str, Any]:
    namespace = state.get("namespace", "sample-app")
    diagnosis = diagnose(namespace)
    return {**state, "diagnosis": diagnosis}


if __name__ == "__main__":
    # Teste manual, sem depender do grafo LangGraph ainda:
    #   PROMETHEUS_URL=http://localhost:9090 python agents/diagnostic_agent.py
    result = diagnose()
    print(json.dumps(result, indent=2, ensure_ascii=False))