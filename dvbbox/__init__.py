#!/usr/bin/env python
# encoding: utf-8


from api.auth import auth
from api.decorators import json
from api.models import db
from api.errors import not_found, not_allowed
from api.v1 import api as api_blueprint, get_catalog as v1_catalog
from api.token import token as token_blueprint
from core import adduser, app, config, copyfile
from core import logger, redis_programs_db, redis_media_db, listing, Listing
from core import manager, media, Media, Partition
from core import program, Program


__all__ = [
    'adduser',
    'app',
    'config',
    'copyfile',
    'logger',
    'redis_programs_db',
    'redis_media_db',
    'Listing',
    'listing',
    'manager',
    'Media',
    'media',
    'Partition',
    'Program',
    'program',
    ]

db.init_app(app)

app.register_blueprint(api_blueprint, url_prefix='/api/dvbbox/v1')

if app.config['USE_TOKEN_AUTH']:
    app.register_blueprint(token_blueprint, url_prefix='/api/dvbbox/auth')


@app.route('/api/dvbbox/')
@auth.login_required
@json
def index():
    u"""Ressource qui renvoie le catalogue des ressources"""
    return {'versions': {'v1': v1_catalog()}}


@app.errorhandler(404)
@auth.login_required
def not_found_error(e):
    return not_found('item not found')


@app.errorhandler(405)
def method_not_allowed_error(e):
    return not_allowed()
