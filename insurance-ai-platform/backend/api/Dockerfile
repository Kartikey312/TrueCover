# Build context is ./backend (the parent of this directory), not ./backend/api,
# because this image needs both api/app and the sibling graph/ and qdrant/
# packages -- see docker-compose.yml's `build.context` for the api service.
FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/app ./app
COPY graph/*.py ./graph/
COPY qdrant/*.py ./qdrant/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
