#!/usr/bin/env python
# encoding: utf-8

import pytest


def pytest_configure(config):
    # register your new marker to avoid warnings
    config.addinivalue_line(
        "markers",
        "product: specify a test key"
    )

def pytest_collection_modifyitems(config, items):
    filter = config.getoption("--product")
    if filter:
        new_items = []
        for item in items:
            mark = item.get_closest_marker("key")
            if mark and mark.args and mark.args[0] == filter:
                # collect all items that have a key marker with that value
                new_items.append(item)
        items[:] = new_items

def pytest_addoption(parser):
    parser.addoption("--platform", default="debian-9", action="store", help="Define which platform of images to run tests again (default: debian-9)")
    parser.addoption("--product", default="all", action="store", help="Define which tests to run. Values can be splunk, uf, or all (default: all - Splunk and UF)")
