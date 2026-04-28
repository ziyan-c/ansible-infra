FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client sshpass \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8000 8080
CMD ["neo-backend"]
