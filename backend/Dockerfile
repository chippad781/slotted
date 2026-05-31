FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# don't run as root in production
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# default command — overridden by docker-compose for the worker service
CMD ["gunicorn", "slotted.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
