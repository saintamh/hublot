#!/usr/bin/env python3

# standards
from pathlib import Path
from random import randrange
from tempfile import TemporaryDirectory
from threading import Thread

# 3rd parties
from flask import Flask
import pytest
from werkzeug.serving import make_server  # installed transitively by Flask

# forban
from forban import Cache
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


def flask_app():
    app = Flask('forban-tests')

    @app.route('/hello')
    def _():
        return 'hello'

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
        yield f'http://127.0.0.1:{port}/'
    finally:
        server.shutdown()
        thread.join()
