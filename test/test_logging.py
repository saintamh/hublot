#!/usr/bin/env python3

# standards
import re


def test_basic_logging(client, server, captured_logs):
    client.get(f'{server}/hello')
    assert re.search(fr'^\[\w\w\w/\w{{13}}\]          {server}/hello\n$', captured_logs())
    client.get(f'{server}/hello')
    assert re.search(fr'^\[\w\w\w/\w{{13}}\] \[cached\] {server}/hello\n$', captured_logs())
