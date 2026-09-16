FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN opentelemetry-bootstrap -a install
COPY main.py .
CMD ["sh", "-c", "opentelemetry-instrument --logs_exporter otlp uvicorn main:app --host 0.0.0.0 --port ${PORT}"]