FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ common/
COPY agents/ agents/
COPY orchestrator/ orchestrator/
COPY web/ web/
COPY server.py .

# Without this the ADK agents build a google-genai client against the AI
# Studio backend and fail at the first turn with "No API key was provided",
# even though the service account has Vertex AI access. It is the single
# most important line in this file.
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE
ENV PORT=8080
EXPOSE 8080

# server.py serves the Control Room console at / and mounts the full ADK API
# (including its developer UI) under /adk.
CMD ["python", "server.py"]
