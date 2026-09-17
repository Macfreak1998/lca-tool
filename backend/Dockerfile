FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY app app
COPY alembic alembic
COPY alembic.ini .
COPY data/demo-archive data/demo-archive
COPY data/ef31_method.json data/ef31_method.json
RUN pip install --no-cache-dir .
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=8 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
