#!/usr/bin/env python
# encoding: utf-8


from flask import Blueprint, g, url_for
from ..errors import ValidationError, bad_request


api = Blueprint('api', __name__)


def get_catalog():
    return {
        'media_url': url_for('api.media'),
        'programs_url': url_for('api.programs'),
        'listing_url': url_for('api.listing'),
        'infos_url': url_for('api.infos'),
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

from . import media, programs, listing, infos
