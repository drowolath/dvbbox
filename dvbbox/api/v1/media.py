#!/usr/bin/env python
# encoding: utf-8


import os
import re
from flask import url_for, redirect, request
from werkzeug.utils import secure_filename
from ...core import config, Media
from ..auth import auth

from ..errors import not_found, no_content, bad_request, not_modified
from ..decorators import json
from . import api


@api.route('/media/', methods=['GET', 'POST'])
@auth.login_required
@json
def media():
    """lists all media or checks if given media exist"""
    media = Media.all()  # dictionnary mapping file names to filepaths
    if request.method == 'GET':
        search = request.args.get('search', None)
        if search:
            bar = [
                i for i in Media.all()
                if re.compile('.*{}.*'.format(search)).match(i)
                ]
            media = {i: media[i] for i in bar}
        if not media:
            return no_content('no media found')
        result = {
            'total': len(media),
            'media': [
                {
                    'filename': filename.replace('.ts', ''),
                    'ressource_uri': url_for(
                        'api.medium',
                        filename=filename.replace('.ts', ''))
                    }
                for filename, filepath in media.items()
                ]
            }
        return result
    elif request.method == 'POST':
        fileobject = request.files['file']
        filepath = os.path.join(
            config.get('DATA_FOLDERS', 'uploads'),
            secure_filename(fileobject.filename)
            )
        fileobject.save(filepath)
        exist = []
        dont_exist = []
        with open(filepath) as infile:
            for line in infile:
                line = line.replace('\n', '')
                if line and line+'.ts' in media:
                    exist.append(line)
                elif line and line+'.ts' not in media:
                    dont_exist.append(line)
        result = {
            'total': len(exist) + len(dont_exist),
            'media': [
                {
                    'filename': filename,
                    'ressource_uri': url_for(
                        'api.medium',
                        filename=filename)
                    }
                for filename in exist
                ],
            'errors': [i for i in dont_exist]
            }
        return result


@api.route('/media/<string:filename>', methods=['GET', 'POST', 'DELETE'])
@auth.login_required
@json
def medium(filename):
    u"""proposes the management of a given filename"""
    medium = Media(filename)
    if not medium.filepath:
        return not_found('{} does not exist'.format(medium.filename))
    elif request.method == 'POST':
        # rename the media
        new_name = request.form.get('new_name', None)
        if not new_name:
            return bad_request("you need to provide a new name for renaming")
        medium = medium.rename(new_name)
        return redirect(url_for('api.medium', filename=new_name))
    elif request.method == 'DELETE':
        # delete the media
        try:
            medium.delete()
        except ValueError:
            msg = ("{} is not deleted since it's "
                   "scheduled for future streaming").format(filename)
            return not_modified(msg)
        else:
            return no_content('{} has been deleted'.format(filename))
    elif request.method == 'GET':
        # return media informations
        result = {
            'filepath': medium.filepath,
            'duration': medium.duration,  # in seconds
            'schedule': medium.schedule(),
            }
        return result
