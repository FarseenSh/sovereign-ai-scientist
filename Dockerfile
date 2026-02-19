FROM --platform=linux/amd64 python:3.11-slim
USER root

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ /app/agent/
COPY server.py /app/
COPY frontend/ /app/frontend/

EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
