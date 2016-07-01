#!/usr/bin/env python
#encoding: utf-8


import pytz
import re
from flask import url_for, request
from ...core import *
from ..auth import auth
from ..errors import not_found, internal_error, not_allowed
from ..decorators import json
from . import api

tz = pytz.timezone('Indian/Antananarivo')

@api.route('/media/', methods=['GET', 'POST'])
@auth.login_required
@json
def media():
    files = [i.split('/')[-1] for i in DB.zrange('files', 0, -1)]
    media = [Media(i) for i in files]
    if not media:
        return not_found('no media found')
    elif request.method == 'POST':
        files = [
            Media(i) for i in files
            if re.compile('.*{}.*'.format(request.form['search'])).match(i)
            ]
        if not files:
            return not_found('no media found')
        else:
            result = [
                {
                    'name': i.filename,
                    'resource_uri': url_for(
                        'api.medium',
                        name=i.filename[:-3])
                }
                for i in files
                ]
            return {'media': result}
    else:
        result = [
            {
                'name': i.filename,
                'resource_uri': url_for(
                    'api.medium',
                    name=i.filename[:-3])
            }
            for i in media
            ]
        return {'media': result}
    else:
        return not_allowed()
    
@api.route('/media/<string:name>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@auth.login_required
@json
def medium(name):
    tsfile = Media(name)
    if not tsfile.exists:
        return not_found('no media found')
    else:
        if request.method == 'PUT':
            tsfile.update()
        elif request.method == 'POST':
            # get new name, rename, update
            tsfile = Manager.renamefile(name+'.ts',
                                        request.form['new'])
        elif request.method == 'DELETE':
            tsfile = Media(name)
            result = tsfile.delete()
            if not result:
                return {
                    'media': name,
                    'info': 'deleted'
                    }
            else:
                return {
                    'media': name,
                    'info': 'not deleted: {0}'.format(result)
                    }
        infos = {
            'file': tsfile.filepath,
            'duration': tsfile.duration,
            'resource_uri': url_for(
                'api.medium',
                name=name),
            'schedules': []
            }
        schedules = tsfile.schedules
        for channel, timestamps in schedules.items():
            infos['schedules'].append(
                {
                    'channel': url_for('api.channel', service=channel),
                    'program': timestamps
                    }
                )
        return infos
