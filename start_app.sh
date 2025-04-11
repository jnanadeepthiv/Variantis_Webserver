#!/bin/bash

# gunicorn -k gevent --worker-tmp-dir /dev/shm --workers 4 --threads 2 --bind 0.0.0.0:5000 wsgi:app
#gunicorn -k gevent --worker-tmp-dir /dev/shm  -u gyanesh -g www-data --workers 4 --access-logfile /tmp/gunicorn_access.log --error-logfile /tmp/gunicorn_error.log --threads 2 --bind=unix:/dev/shm/rrnadb.sock wsgi:app
#gunicorn -k gevent --worker-tmp-dir /dev/shm  -u gyanesh -g www-data --workers 4 --access-logfile /tmp/gunicorn_access.log --error-logfile /tmp/gunicorn_error.log --threads 2 --bind=unix:/dev/shm/rrnadb.sock wsgi:app
gunicorn -u deepthi -g www-data --access-logfile /tmp/variantis_access.log --error-logfile /tmp/variantis_error.log --threads 2 --workers 3 --bind unix:/tmp/variantis.sock -m 007 wsgi:app
