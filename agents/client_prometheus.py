"""Cliente HTTP simples para a API do Prometheus."""

import os
from typing import Any

import requests

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")


class PrometheusClientError(Exception):
    """Erro ao consultar o Prometheus (rede, timeout, ou resposta inesperada)."""


def query(promql: str, timeout: int = 10) -> list[dict[str, Any]]:
    """
    Executa uma instant query PromQL e retorna a lista de séries em `data.result`.
    Levanta PrometheusClientError se o Prometheus estiver inacessível ou a query falhar.
    """
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": promql},
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise PrometheusClientError(
            f"Falha ao conectar ao Prometheus em {PROMETHEUS_URL}: {exc}"
        ) from exc

    payload = resp.json()
    if payload.get("status") != "success":
        raise PrometheusClientError(f"Query PromQL falhou: {payload}")

    return payload["data"]["result"]