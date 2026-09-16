import os
import logging
import requests
from fastapi import FastAPI
from random import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
UPSTREAM_URL = os.getenv("UPSTREAM_URL")

@app.get("/healthz")
def health_check():
    return {"status": "ok"}

@app.get("/")
def entry_point():
    logger.info("Recebendo requisição no serviço.")

    if random() < 0.2:
        logger.error("Falha interna simulada!")
        return {"status": "error", "message": "Falha na comunicação"}

    if UPSTREAM_URL:
        logger.info(f"Chamando serviço downstream: {UPSTREAM_URL}")
        response = requests.get(UPSTREAM_URL)
        return {"status": "success", "downstream_response": response.json()}

    logger.info("Processamento finalizado no serviço downstream.")
    return {"status": "success", "data": "Dados processados com sucesso!"}