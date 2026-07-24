FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system compose && adduser --system --ingroup compose compose

COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

RUN pip install --upgrade pip && pip install .

USER compose

EXPOSE 8000
CMD ["uvicorn", "compose_ai_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
