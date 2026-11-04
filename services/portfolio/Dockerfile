FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY portfolio_service ./portfolio_service

RUN useradd --create-home appuser
USER appuser

EXPOSE 8002

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8002/health', timeout=2)"

CMD ["gunicorn", "--bind", "0.0.0.0:8002", "--workers", "2", "--threads", "4", "--access-logfile", "-", "portfolio_service.wsgi:app"]
