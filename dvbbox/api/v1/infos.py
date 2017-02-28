#!/usr/bin/env python
# encoding: utf-8


from ...core import media_folders, Partition, config
from ..auth import auth
from ..decorators import json
from . import api


@api.route('/infos/', methods=['GET'])
@auth.login_required
@json
def infos():
    result = {
        'result': {
            'media_folders': [
                {
                    'name': p.path,
                    'disk_size': p.bytes2human(p.size.total),
                    'free_space': p.bytes2human(p.size.free),
                    'disk_usage': '{}%'.format(p.usage * 100)
                    }
                for p in [Partition(folder) for folder in media_folders]
                ],
            'channels': [
                {
                    'id': x,
                    'name': config.get('SERVICE:'+x, 'name')
                    }
                for x in [
                        i.split(':')[1] for i in config.sections()
                        if i.startswith('SERVICE:')
                        ]
                ]
            }
        }
    return result
