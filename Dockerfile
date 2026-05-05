FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        gcc \
        g++ \
        gettext \
        gnupg \
        libbz2-dev \
        libffi-dev \
        libjpeg62-turbo-dev \
        liblzma-dev \
        libmemcached-dev \
        libssl-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade "pip<25" "setuptools<70" "wheel<0.45" \
    && pip install --no-cache-dir --no-build-isolation -r requirements.txt

COPY . .
RUN sed -i 's/\r$//' ./uwsgi-run.sh && chmod +x ./uwsgi-run.sh
CMD ["./uwsgi-run.sh"]
