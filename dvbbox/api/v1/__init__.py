#!/usr/bin/env python
#encoding: utf-8

from flask import Blueprint, g, url_for, request
from werkzeug.contrib.cache import RedisCache
from ..errors import ValidationError, bad_request, not_found
from ..auth import auth
from ..decorators import json

api = Blueprint('api', __name__)

def get_catalog():
    return {
        'channels_url': url_for(
            'api.channels', _external=True, _scheme='http'),
        'media_url': url_for(
            'api.media', _external=True, _scheme='http'),
        'programs_url': url_for(
            'api.programs', _external=True, _scheme='http'),
        'infos_url': url_for(
            'api.infos', _external=True, _scheme='http'),
        }

@api.errorhandler(ValidationError)
def validation_error(e):
    return bad_request(str(e))

@api.errorhandler(400)
def bad_request_error(e):
    return bad_request('invalid request')

@api.after_request
def after_request(response):
    if hasattr(g, 'headers'):
        response.headers.extend(g.headers)
    return response

from . import channels, programs, media, infos
