FROM python:3.11-slim

RUN pip install --no-cache-dir --timeout 100 --retries 5 mlflow==3.16.0

EXPOSE 5000

CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri", "sqlite:////mlflow-data/mlflow.db", "--default-artifact-root", "/mlflow-data/mlruns", "--serve-artifacts"]