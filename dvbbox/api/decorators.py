#!/usr/bin/env python
#encoding: utf-8

import functools
import sys
from flask import jsonify


def json(f):
    """Génération (compliquée?) d'un JSON à partir d'un dico Python"""
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        rv = f(*args, **kwargs)
        status_or_headers = None
        headers = None
        if isinstance(rv, tuple):
            rv, status_or_headers, headers = rv + (None,) * (3 - len(rv))
        if isinstance(status_or_headers, (dict, list)):
            headers, status_or_headers = status_or_headers, None
        # if not isinstance(rv, dict):
        #     rv = rv.export_data()
        try:    
            rv = jsonify(rv)
        except:
            pass
        if status_or_headers is not None:
            rv.status_code = status_or_headers
        if headers is not None:
            rv.headers.extend(headers)
        return rv
    return wrapped
