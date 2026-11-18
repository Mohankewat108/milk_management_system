FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements/production.txt requirements/production.txt
COPY requirements/base.txt requirements/base.txt
RUN python -m pip install --upgrade pip \
    && pip install -r requirements/production.txt

COPY --chown=app:app . .
RUN mkdir -p /app/private_uploads && chown -R app:app /app/private_uploads

USER app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
