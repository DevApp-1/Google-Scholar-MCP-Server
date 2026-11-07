FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 MCP_TRANSPORT=streamable-http
COPY requirements.txt .
RUN pip install -U pip setuptools wheel && pip install -r requirements.txt
COPY *.py .
EXPOSE 8000
CMD ["python", "google_scholar_server.py"]
