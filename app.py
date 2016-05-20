import os
from sqlalchemy.exc import IntegrityError
from flask.ext.sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request, json, redirect, url_for, flash

import boto.sqs
from boto.sqs.message import RawMessage
# import redis
# from rq import Queue
import requests

from urlparse import urlparse
from indexer import Indexer

if os.environ.get('RDS_HOSTNAME'):
    db_url = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user=os.environ.get('RDS_USERNAME'),
        password=os.environ.get('RDS_PASSWORD'),
        host=os.environ.get('RDS_HOSTNAME'),
        port=os.environ.get('RDS_PORT'),
        database=os.environ.get('RDS_DB_NAME'),
    )
else:
    db_url = os.environ.get('HEROKU_POSTGRESQL_VIOLET_URL')

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'top secret key!'
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['REDIS_URL'] = os.environ.get('REDISTOGO_URL', 'redis://localhost:6379')
app.config['AWS_REGION'] = os.environ.get('AWS_REGION')
app.config['WORKER_QUEUE'] = os.environ.get('WORKER_QUEUE')
db = SQLAlchemy(app)
# redis_conn = redis.from_url(app.config['REDIS_URL'])
# q = Queue(connection=redis_conn)
application = app
sqs_conn = boto.sqs.connect_to_region(app.config['AWS_REGION'])

from models import *


def index_esri_server(server_id):
    app.logger.info('Indexing ESRI server %s', server_id)
    server = EsriServer.query.get(server_id)

    if not server:
        app.logger.error('ESRI server %s was not found', server_id)
        return

    server.status = 'importing'
    db.session.add(server)
    db.session.commit()

    resulting_status = 'errored'
    try:
        indexer = Indexer(app.logger)
        services = indexer.get_services(server.url)
        for service in services:
            service_details = indexer.get_service_details(service.get('url'))

            db_service = Service(
                server=server,
                name=service.get('name'),
                service_type=service.get('type'),
                service_data=service_details,
            )
            db.session.add(db_service)

            layers = service_details.get('layers', [])
            for layer in layers:
                db_layer = Layer(
                    service=db_service,
                    name=layer.get('name'),
                    layer_data=layer,
                )
                db.session.add(db_layer)
        resulting_status = 'imported'
    except requests.exceptions.RequestException:
        app.logger.exception('Problem indexing ESRI server %s', server_id)
    except ValueError:
        app.logger.exception('Problem indexing ESRI server %s', server_id)

    server.status = resulting_status
    server.job_id = None
    db.session.add(server)
    db.session.commit()

@app.route('/queue_handler', methods=['POST'])
def queue_handler():
    server_id = request.json.get('server_id')
    app.logger.info("Starting indexing server %s", server_id)

    index_esri_server(server_id)

    app.logger.info("Done indexing server %s", server_id)

    return "ok", 200

@app.route('/servers/new', methods=['POST'])
def new_server():
    url = request.form['url']

    url_parts = urlparse(url)

    if url_parts.scheme not in ('http', 'https'):
        flash('That URL is not valid.')
    else:
        server = EsriServer(url=url)
        db.session.add(server)
        try:
            db.session.commit()

            message = {
                "server_id": server.id
            }
            m = RawMessage()
            m.set_body(json.dumps(message))
            queue = boto.sqs.queue.Queue(sqs_conn, app.config['WORKER_QUEUE'])
            queue.write(m)

            server.status = 'queued'
            db.session.add(server)
            db.session.commit()
        except IntegrityError:
            flash('That URL has already been added.')
            db.session.rollback()

    return redirect(url_for('index'))

@app.route('/')
def index():
    servers = EsriServer\
        .query \
        .order_by('updated_at DESC') \
        .paginate(page=int(request.args.get('page', 1)))

    return render_template('index.html', servers=servers)

@app.route('/servers/<int:server_id>', methods=['GET'])
def show_server(server_id):
    server = EsriServer.query.get_or_404(server_id)

    return render_template('show_server.html', server=server)

@app.route('/servers/<int:server_id>/services/<int:service_id>', methods=['GET'])
def show_service(server_id, service_id):
    server = EsriServer.query.get_or_404(server_id)
    service = Service.query.get_or_404(service_id)

    return render_template('show_service.html', server=server, service=service)

@app.route('/search', methods=['GET'])
def search():
    results = Layer.query \
        .filter(Layer.name.ilike('%{}%'.format(request.args.get('q'))))

    which_server = request.args.get('server_id')
    if which_server and which_server.isdigit():
        results = results.join(Service).filter(Service.server_id == int(which_server))

    page = request.args.get('page', 1)
    if not isinstance(page, int) and not page.isdigit():
        page = 1

    results = results.paginate(page=page)

    return render_template('show_search.html', results=results)

if __name__ == '__main__':
    app.run()
