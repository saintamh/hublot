#!/usr/bin/env python3

# It's the pytest way, pylint: disable=redefined-outer-name

# standards
from io import StringIO
from itertools import count
import logging
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
from forban import Cache, Client, basic_logging_config, logger
import forban.courtesy
import forban.decorator


basic_logging_config(level='DEBUG')


@pytest.fixture
def reinstantiable_cache():
    """
    A callable that can be called repeatedly to reinstantiate the same cache. The idea is to test what happens if you discard a
    cache object then re-create it, with the same parameters, as happens when you re-run a script.
    """
    with TemporaryDirectory() as temp_root:
        yield lambda **kwargs: Cache.load(Path(temp_root), **kwargs)


@pytest.fixture
def reinstantiable_client(reinstantiable_cache):
    """
    A callable that can be called repeatedly to reinstantiate a Client with the same cache parameters.
    """
    yield lambda cookies_enabled=True, **kwargs: Client(
        cache=reinstantiable_cache(**kwargs),
        cookies_enabled=cookies_enabled,
    )


@pytest.fixture
def cache(reinstantiable_cache):
    yield reinstantiable_cache()


@pytest.fixture
def client(cache):
    yield Client(cache=cache)


def flask_app():
    # Yeah, we don't call these directly, but they still need names, pylint: disable=unused-variable
    # And yes, it's a bit long for a function, but it's still readable, pylint: disable=too-many-locals
    app = Flask('forban-tests')

    @app.route('/hello')
    def hello():
        return 'hello'

    @app.route('/method-test', methods=['GET', 'POST', 'PUT'])
    def method_test():
        return request.method

    iter_numbers = count()
    @app.route('/unique-number', methods=['GET', 'POST'])
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
            'form': request.data.decode('UTF-8') if request.data and not request.json else request.form,
            'json': request.json,
            'headers': dict(request.headers.items()),
        })

    @app.route('/fail-with-random-value')
    def fail_with_random_value():
        return str(random()), 500

    num_calls_by_key = {}
    num_failures_by_key = {}
    @app.route('/fail-twice-then-succeed/<key>')
    def fail_twice_then_succeed(key):
        num_calls = num_calls_by_key.get(key, 0)
        num_calls_by_key[key] = num_calls + 1
        num_failures = num_failures_by_key.get(key, 0)
        if num_calls < 2:
            num_failures_by_key[key] = num_failures + 1
            return f'crash {num_failures}', 500
        status = f'success after {num_failures} failures'
        if num_calls > num_failures:
            status += f' and {num_calls - num_failures} successes'
        return status, 200

    @app.route('/cookies/get')
    def get_cookie():
        return request.cookies

    @app.route('/cookies/set')
    def set_cookie():
        res = make_response()
        for key, value in request.args.items():
            res.set_cookie(key, value)
        return res

    @app.route('/cookies/set-two-cookies')
    def set_two_cookies():
        return str(next(iter_numbers)), 200, {'Set-Cookie': ['a=1', 'b=2']}

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

    @app.route('/redirect/loop')
    def redirect_loop():
        res = make_response('Loop 1', 302)
        res.headers['Location'] = '/redirect/loop-back'
        return res

    @app.route('/redirect/loop-back')
    def redirect_loop_back():
        res = make_response('Loop 2', 302)
        res.headers['Location'] = '/redirect/loop'
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
def mocked_courtesy_sleep(mocker):
    mocker.patch('forban.courtesy.sleep')
    return forban.courtesy.sleep


@pytest.fixture
def mocked_sleep_on_retry(mocker):
    mocker.patch('forban.decorator.sleep')
    return forban.decorator.sleep


@pytest.fixture
def unique_key():
    return ''.join(choices(ascii_letters, k=32))


@pytest.fixture
def captured_logs():
    handler = logging.StreamHandler(StringIO())
    original_handlers = logger.handlers
    logger.handlers = [handler]

    def getvalue():
        value = handler.stream.getvalue()
        handler.stream = StringIO()
        logging.debug('Captured logs: %r', value)
        return value
    yield getvalue

    logger.handlers = original_handlers


def pytest_collection_modifyitems(items):
    for item in items:
        # these are always applied, whether or not the tests want them
        item.fixturenames.append('mocked_courtesy_sleep')
        item.fixturenames.append('mocked_sleep_on_retry')
