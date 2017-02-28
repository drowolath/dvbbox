#!/usr/bin/env python
# encoding: utf-8

from flask import request
from werkzeug.contrib.cache import SimpleCache

CACHE_TIMEOUT = 600

cache = SimpleCache()


class Cached(object):
    def __init__(self, timeout=None):
        self.timeout = timeout or CACHE_TIMEOUT

    def __call__(self, f):
        def decorator(*args, **kwargs):
            response = cache.get(request.path)
            if response is None:
                response = f(*args, **kwargs)
                cache.set(request.path, response, self.timeout)
            return response
        return decorator
