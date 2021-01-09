#!/usr/bin/env python3

# 3rd parties
import pytest

# melba
import melba


@pytest.mark.parametrize(
    'courtesy_seconds',
    [None, 0, 5, 37],
)
def test_courtesy_sleep(mocker, server, courtesy_seconds):
    # you're confused because we're patching the `sleep` function, pylint: disable=no-member
    kwargs = {} if courtesy_seconds is None else {'courtesy_sleep': courtesy_seconds}
    fetch = melba.Melba(**kwargs).fetch
    mocker.patch('melba.melba.sleep')
    fetch(f'{server}/hello')
    melba.melba.sleep.assert_not_called()  # 1st request, no sleep
    fetch(f'{server}/hello')
    if courtesy_seconds == 0:
        melba.melba.sleep.assert_not_called()
    else:
        melba.melba.sleep.assert_called_once()
        delay, = melba.melba.sleep.call_args[0]
        assert delay == pytest.approx(courtesy_seconds or 5, 0.1)
