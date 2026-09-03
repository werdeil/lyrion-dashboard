FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The app only ever reads — its own sources, Lyrion's read-only mounts — so
# the tree stays root-owned and the process runs unprivileged.
RUN useradd --create-home --uid 1000 dashboard
USER dashboard

EXPOSE 1111

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c 'import urllib.request as u; u.urlopen("http://127.0.0.1:1111/health")'

CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:1111", "app:app", \
     "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info"]
