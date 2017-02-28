#!/usr/bin/env python
# encoding: utf-8

from flask import g
from flask_httpauth import HTTPBasicAuth
from .models import User
from .errors import unauthorized

auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username_or_token, password):
    g.user = User.verify_auth_token(username_or_token)
    return g.user is not None


@auth.error_handler
def unauthorized_error():
    return unauthorized()
