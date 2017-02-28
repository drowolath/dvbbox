#!/usr/bin/env python
# encoding: utf-8

import time
from datetime import datetime
from flask import url_for, request
from ...core import config, Program, redis_programs_db
from ..auth import auth
from ..errors import not_found, internal_error, no_content
from ..decorators import json
from . import api


@api.route('/programs/', methods=['GET'])
@auth.login_required
@json
def programs():
    """returns catalog of existing programs"""
    programs = redis_programs_db.keys('*:*')
    programs = [i for i in programs if redis_programs_db.type(i) == 'zset']
    if not programs:
        return not_found('no program found')
    programs = sorted(
        programs,
        key=lambda x: time.strptime(x.split(':')[0], '%d%m%Y')
        )
    programs = sorted(
        programs,
        key=lambda x: int(x.split(':')[1])
        )
    result = {
        'total': len(programs),
        'programs': [
            {
                'day': program.split(':')[0],
                'service_id': program.split(':')[1],
                'ressource_uri': url_for(
                    'api.program',
                    day=program.split(':')[0],
                    service_id=program.split(':')[1]
                    ),
                }
            for program in programs
            ]
        }
    return result


@api.route('/programs/check/<string:day>/<string:service_id>', methods=['GET'])
@json
def program_check(day, service_id):
    """checks program status"""
    return Program(day, service_id).check()


@api.route('/programs/<string:day>/<string:service_id>',
           methods=['GET', 'DELETE', 'POST', 'PUT'])
@auth.login_required
@json
def program(day, service_id):
    u"""enables program management for a given day and a given service id"""
    program = Program(day, service_id)
    infos = program.infos
    if not infos:
        return not_found('no program found')

    if request.method == 'POST':
        # launch program streaming
        program = Program(day, service_id, time.time())
        try:
            process = program.stream()
        except Exception as exc:
            return internal_error(exc.message)
        else:
            result = {
                'result': "Launched with PID {}".format(process.pid)
                }
            return result
    elif request.method == 'PUT':
        # update program
        try:
            program.update()
        except Exception as exc:
            return internal_error(exc.message)
        else:
            return no_content()
    elif request.method == 'DELETE':
        # delete program
        try:
            program.delete()
        except Exception as exc:
            return internal_error(exc.message)
        else:
            return no_content()
    else:
        # display program
        result = {
            'total': len(infos),
            'media': [
                {
                    'start-time': datetime.fromtimestamp(timestamp).strftime(
                        config.get('LOG', 'datefmt')),
                    'filename': entry.split(':')[0].split('/')[-1][:-3],
                    'ressource_uri': url_for(
                        'api.medium',
                        filename=entry.split(':')[0].split('/')[-1][:-3]
                        )
                    }
                for entry, timestamp in infos
                ]
            }
        return result
