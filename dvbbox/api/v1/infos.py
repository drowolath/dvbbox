#!/usr/bin/env python
#encoding: utf-8

from ...core import System
from ..auth import auth
from ..errors import bad_request
from ..decorators import json
from . import api


@api.route('/infos/', methods=['GET'])
@auth.login_required
@json
def infos():
    infos = System.nodeinfos()
    return infos
