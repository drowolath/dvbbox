#!/usr/bin/env python
#encoding: utf-8

import os
from flask import url_for, request
from ...core import *
from . import api
from ..auth import auth
from ..errors import not_found, created, no_content
from ..decorators import json

@api.route('/channels/', methods=['GET'])
@auth.login_required
@json
def channels():
    """list of channels configured on the node"""
    channels = [
        url_for('api.channel', service=i)
        for i in settings.CHANNELS.keys()
        ]
    if not channels:
        return not_found('no channel found')
    else:
        result = {'channels': channels}
        return result

@api.route('/channels/<int:service>', methods=['GET'])
@auth.login_required
@json
def channel(service):
    """informations about a channel"""
    channels = [
        int(i) for i in settings.CHANNELS.keys()
        ]
    if not service in channels:
        return not_found("channel {0} doesn't exist".format(service))
    else:
        result = Channel(service).__dict__
        return result
