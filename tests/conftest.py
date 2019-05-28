#!/usr/bin/env python
# encoding: utf-8

import pytest


def pytest_addoption(parser):
    parser.addoption("--platform", default="debian-9", action="store", help="Define which platform of images to run tests again (default: debian-9)")
