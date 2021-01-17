#!/usr/bin/env python3

# It's the pytest way, pylint: disable=redefined-outer-name

# standards
from itertools import count
from pathlib import Path
from random import choices, random, randrange
from string import ascii_letters
from tempfile import TemporaryDirectory
from threading import Thread

# 3rd parties
from flask import Flask, jsonify, make_response, request
import pytest
from werkzeug.serving import make_server  # installed transitively by Flask

# forban
from forban import Cache, Client, forban
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

    iter_numbers = count()
    @app.route('/unique-number')
    def unique_number():
        return str(next(iter_numbers))

    @app.route('/echo', methods=['GET', 'POST'])
    def echo():
        return jsonify({
            'args': request.args,
            'files': {
                key: storage.read().decode('UTF-8')
                for key, storage in request.files.items()
            },
            'form': request.form,
            'json': request.json,
        })

    @app.route('/fail-with-random-value')
    def fail_with_random_value():
        return str(random()), 500

    num_failures_by_key = {}
    @app.route('/fail-twice-then-succeed/<key>')
    def fail_twice_then_succeed(key):
        num_failures = num_failures_by_key.get(key, 0)
        num_failures_by_key[key] = num_failures + 1
        if num_failures < 2:
            return f'crash {num_failures}', 500
        return f'success after {num_failures} failures', 200

    @app.route('/cookies/get')
    def get_cookie():
        return request.cookies

    @app.route('/cookies/set')
    def set_cookie():
        res = make_response()
        for key, value in request.args.items():
            res.set_cookie(key, value)
        return res

    @app.route('/redirect/chain/1')
    def redirect_chain_1():
        res = make_response('Bounce 1', 302)
        res.headers['Location'] = '/redirect/chain/2'
        res.set_cookie('redirect1', 'yes')
        return res

    @app.route('/redirect/chain/2')
    def redirect_chain_2():
        res = make_response('Bounce 2', 302)
        res.headers['Location'] = '/redirect/chain/3'
        res.set_cookie('redirect2', 'yes')
        return res

    @app.route('/redirect/chain/3')
    def redirect_chain_3():
        res = make_response('Landed')
        res.set_cookie('redirect3', 'yes')
        return res

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


@pytest.fixture
def mocked_sleep(mocker):
    mocker.patch('forban.forban.sleep')
    return forban.sleep


@pytest.fixture
def unique_key():
    return ''.join(choices(ascii_letters, k=32))
