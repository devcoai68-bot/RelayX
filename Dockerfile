FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY relayx ./relayx
RUN pip install --no-cache-dir . \
    && adduser --system --group --home /nonexistent relayx
USER relayx
EXPOSE 8000
CMD ["relayx", "server"]
