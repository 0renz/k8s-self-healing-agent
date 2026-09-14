# AIOps Self-Healing Agent

Agente de IA multi-agente para diagnóstico e remediação automatizada de incidentes em um cluster Kubernetes, combinando observabilidade (Prometheus/Grafana), orquestração de agentes (LangGraph) e automação de infraestrutura (Ansible).

## Objetivo

Demonstrar, de forma prática, como agentes de IA generativa podem ser aplicados a operações de SRE/DevOps: monitorar métricas de um sistema em produção, diagnosticar a causa raiz de um problema e executar ações de remediação de forma autônoma e auditável.

## Arquitetura

O sistema é composto por três camadas:

1. **Infraestrutura** — cluster Kubernetes local (Minikube), provisionado via Ansible, rodando uma aplicação de exemplo instrumentada com OpenTelemetry.
2. **Observabilidade** — Prometheus coleta métricas do cluster e da aplicação; Grafana exibe dashboards de saúde do sistema.
3. **Agente de IA (LangGraph)** — um grafo de agentes especializados:
   - **Agente de Diagnóstico**: consulta métricas via API do Prometheus e usa um LLM para identificar a causa provável de uma anomalia.
   - **Agente de Decisão**: avalia o diagnóstico e escolhe uma ação de remediação dentre um conjunto pré-definido e seguro.
   - **Agente de Execução**: aplica a ação escolhida via `kubectl` ou playbook Ansible.

Cada decisão do agente é registrada em log estruturado, permitindo auditoria posterior.

## Tecnologias utilizadas

- Python 3.11
- LangGraph — orquestração multi-agente
- Kubernetes (Minikube/Kind)
- Ansible — provisionamento e playbooks de remediação
- Prometheus + Grafana — observabilidade
- OpenTelemetry — instrumentação da aplicação de exemplo
- FastAPI — aplicação de exemplo monitorada

## Fluxo de execução

1. O agente monitora continuamente métricas expostas pelo Prometheus.
2. Ao detectar uma anomalia (ex: uso de memória acima do limite, pod em `CrashLoopBackOff`), o Agente de Diagnóstico investiga a causa usando as métricas disponíveis.
3. O Agente de Decisão recebe o diagnóstico e escolhe uma ação de remediação (ex: reiniciar deployment, escalar réplicas).
4. O Agente de Execução aplica a ação via `kubectl` ou dispara um playbook Ansible.
5. O resultado da ação é registrado e pode ser usado para validar a eficácia da remediação.

## Estrutura do repositório

```
.
├── README.md
├── requirements.txt
├── infra/
│   ├── ansible/
│   │   └── playbooks/
│   └── k8s/
│       └── manifests/
├── app/
│   └── (aplicação de exemplo instrumentada)
├── agents/
│   ├── diagnostic_agent.py
│   ├── decision_agent.py
│   ├── execution_agent.py
│   └── graph.py
└── logs/
    └── (histórico de decisões do agente)
```

## Como executar

> ⚠️ Seção a ser detalhada conforme o projeto avançar.

```bash
# Subir o cluster local
minikube start

# Provisionar configurações via Ansible
ansible-playbook infra/ansible/playbooks/setup.yml

# Aplicar manifests da aplicação de exemplo
kubectl apply -f infra/k8s/manifests/

# Rodar o agente
python agents/graph.py
```

## Status do projeto

🚧 Em desenvolvimento — projeto pessoal para estudo e prática de orquestração de agentes de IA aplicada a operações de infraestrutura.

## Próximos passos

- [ ] Adicionar agente validador antes da execução de ações críticas
- [ ] Expandir conjunto de ações de remediação suportadas
- [ ] Adicionar métricas de acurácia do diagnóstico do agente
- [ ] Dashboard Grafana dedicado ao histórico de intervenções do agente