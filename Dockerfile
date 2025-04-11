FROM python:3.12.0-slim

COPY ./requirements.txt /variantis/requirements.txt

COPY . /variantis

RUN chmod a+x /variantis/start_app.sh

RUN mkdir /logs

RUN apt-get update && apt-get install -y curl libpq-dev build-essential sqlite3 emboss

RUN useradd -m -g www-data deepthi

#RUN service postgresql start
RUN chown -R deepthi:www-data variantis

USER deepthi

RUN pip install --upgrade pip && pip3 install -r /variantis/requirements.txt

# COPY requirements.txt /variantis/requirements.txt
WORKDIR /variantis

#CMD ["gunicorn", "-k", "gevent", "--worker-tmp-dir" ,"/dev/shm", "--workers", "4", "--access-logfile", "/logs/gunicorn_access.log", "--error-logfile", "/logs/gunicorn_error.log", "--threads", "2", "--bind=unix:/dev/shm/variantis.sock", "wsgi:app"]
ENV PATH=/home/deepthi/.local/bin:$PATH

# CMD ["/bin/bash"]

ENTRYPOINT ["./start_app.sh"]
