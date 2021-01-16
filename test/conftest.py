#!/usr/bin/env python3

# It's the pytest way, pylint: disable=redefined-outer-name

# standards
from pathlib import Path
from random import randrange
from tempfile import TemporaryDirectory
from threading import Thread

# 3rd parties
from flask import Flask, request
import pytest
from werkzeug.serving import make_server  # installed transitively by Flask

# forban
from forban import Cache, Client
from forban.cache import BodyStorage, HeaderStorage


@pytest.fixture
def header_storage():
    with TemporaryDirectory() as temp_root:
        yield HeaderStorage(Path(temp_root))


@pytest.fixture
def body_storage():
    with TemporaryDirectory() as temp_root:
        yield BodyStorage(Path(temp_root))


@pytest.fixture
def cache():
    with TemporaryDirectory() as temp_root:
        yield Cache(temp_root)


@pytest.fixture
def client(cache):
    yield Client(cache=cache)


def flask_app():
    app = Flask('forban-tests')
    # yeah we don't call these directly, but they still need names, pylint: disable=unused-variable

    @app.route('/hello')
    def hello():
        return 'hello'

    @app.route('/method-test', methods=['GET', 'POST', 'PUT'])
    def method_test():
        return request.method

    return app


@pytest.fixture(scope='session')
def server():
    app = flask_app()
    port = randrange(5000, 50000)
    server = make_server('127.0.0.1', port, app)  # pylint: disable=redefined-outer-name
    app.app_context().push()
    thread = Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.shutdown()
        thread.join()
