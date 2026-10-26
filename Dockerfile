FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIR=/app/frontend

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY frontend /app/frontend

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000
# Un solo proceso: los datos viven en memoria, así que varios workers tendrían datos distintos.
CMD ["sh", "-c", "uvicorn app.main:crear_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
