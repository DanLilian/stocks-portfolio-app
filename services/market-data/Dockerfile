FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY market_data ./market_data

RUN useradd --create-home appuser
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8001/health', timeout=2)"

CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "2", "--threads", "4", "--access-logfile", "-", "market_data:create_app()"]
