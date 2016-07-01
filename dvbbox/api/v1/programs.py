#!/usr/bin/env python
#encoding: utf-8

import pytz
import os
from datetime import datetime
from flask import request, url_for
from ...core import *
from ..auth import auth
from ..errors import not_found, not_allowed
from ..decorators import json
from . import api

tz = pytz.timezone('Indian/Antananarivo')

@api.route('/programs/', methods=['GET'])
@auth.login_required
@json
def programs():
    """get programs existing"""
    channels = map(Channel, settings.CHANNELS.keys())
    result = {
        'programs': {
            channel.service_id: [
                url_for('api.program', date=j, service=channel.service_id)
                for j in channel.__programs__()
                ]
            for channel in channels
            }
        }
    return result


@api.route('/programs/<int:service>',
           methods=['GET', 'POST'], defaults={'date': None})
@api.route('/programs/<int:service>/<string:date>')
@auth.login_required
@json
def program(service, date):
    channel = Channel(service)
    if request.method == "POST":
        try:
            fileobject = request.files['file']
            fileobject.save(
                os.path.join(settings.UPLOAD_DIR, fileobject.filename)
                )
            infos = Playlist(
                os.path.join(settings.UPLOAD_DIR, fileobject.filename)
                ).apply(service)
            result = {
                'channel': channel.name,
                'infos': list(infos)
                }
            return result
        except IOError as err:
            msg = '{0}: {1}'.format(err.strerror, err.filename)
            return not_found(msg), 500
    else:
        programs = channel.__programs__(date=date)
        if not programs:
            return not_found("no schedule found for {0}".format(channel.name))
        elif not date:
            result = {
                'programs': [
                    url_for('api.program', date=i, service=service)
                    for i in programs
                    ]
                }
            return result
        else:
            result = {'programs': programs[date]}
            return result
    else:
        return not_allowed()
