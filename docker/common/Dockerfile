FROM continuumio/miniconda:4.3.27

LABEL maintainer="boutte3@llnl.gov"

ENV CELERY_BROKER_URL=redis://redis/0

ENV CELERY_RESULT_BACKEND=redis://redis/0

ENV POSTGRES_HOST=postgres

ENV WPS_HOST=0.0.0.0

COPY docker/common/environment.yml environment.yml

RUN apt-get update && \
	apt-get install -y --no-install-recommends build-essential libev-dev && \
	conda env create -n wps -f environment.yml && \
	conda clean -y --all && \
	rm -rf /opt/conda/pkgs/* && \
	apt-get autoremove -y build-essential && \
	rm -rf /usr/share/doc/ && \
	rm -rf /usr/share/man/ && \
	rm -rf /usr/share/locale && \
	rm -rf /var/lib/apt/lists/*

COPY compute/ /var/www/webapp/compute

WORKDIR /var/www/webapp

ENV CWT_BASE=/var/www/webapp/compute

RUN mkdir -p /var/log/cwt && \
	mkdir -p /etc/config

COPY docker/common/app.properties /etc/config

COPY docker/common/django.properties /etc/config
