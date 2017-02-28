#!/usr/bin/env python
# encoding: utf-8

from flask import Blueprint, g
from flask_httpauth import HTTPBasicAuth
from .models import User
from .errors import unauthorized
from .decorators import json

token = Blueprint('token', __name__)
token_auth = HTTPBasicAuth()


@token_auth.verify_password
def verify_password(username, password):
    try:
        g.user = User(username)
        return g.user.verify_password(password)
    except ValueError:
        return False


@token_auth.error_handler
def unauthorized_error():
    return unauthorized('Please authenticate to get your token.')


@token.route('/request-token', methods=['POST'])
@token_auth.login_required
@json
def request_token():
    #  on ajoute ':' à la fin parce qu'on veut
    #  simplifier la création d'un champ password vide
    return {'token': g.user.generate_auth_token() + ':'}
