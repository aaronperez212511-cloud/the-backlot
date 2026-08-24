FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ common/
COPY agents/ agents/
COPY orchestrator/ orchestrator/

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "adk web orchestrator --host 0.0.0.0 --port ${PORT}"]
