#!/usr/bin/env python
# encoding: utf-8


import os
import flask
from werkzeug.utils import secure_filename
from ...core import config, Listing
from ..auth import auth
from ..errors import no_content
from . import api


@api.route('/listing', methods=['POST'])
@auth.login_required
def listing():
    fileobject = flask.request.files['file']
    filepath = os.path.join(
        config.get('DATA_FOLDERS', 'uploads'),
        secure_filename(fileobject.filename)
        )
    fileobject.save(filepath)
    service_id = flask.request.form.get('service_id')
    l = Listing(filepath)
    if not service_id:
        return flask.Response(flask.stream_with_context(l.parse()))
    data = l.parse()
    l.apply(data, data)
    return no_content()
