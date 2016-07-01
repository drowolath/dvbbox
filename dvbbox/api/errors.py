#!/usr/bin/env python
#encoding: utf-8

"""
Personalisation des erreurs HTTP communes
pour surclasser le code abort() par défaut
de Flask
"""

from flask import jsonify, url_for, current_app


class ValidationError(ValueError):
    pass
    

def internal_error(message):
    u"""HTTP 500"""
    response = jsonify(
        {
            'status': 500,
            'error': 'internal server error',
            'message': message
        }
    )
    response.status_code = 500
    return response

def not_modified():
    u"""HTTP 304"""
    response = jsonify(
        {
            'status': 304,
            'error': 'not modified'
        }
    )
    response.status_code = 304
    return response

def no_content():
    u"""HTTP 204"""
    response = jsonify(
        {
            'status': 204,
            'message': 'correctly processed: no content to return'
        }
    )
    response.status_code = 204
    return response

def created():
    u"""HTTP 201"""
    response = jsonify(
        {
            'status': 201,
            'message': 'resource created'
        }
    )
    response.status_code = 201
    return response

def bad_request(message):
    u"""HTTP 400"""
    response = jsonify(
        {
            'status': 400,
            'error': 'bad request',
            'message': message
        }
    )
    response.status_code = 400
    return response

def unauthorized(message=None):
    u"""HTTP 401"""
    if message is None:
        if current_app.config['USE_TOKEN_AUTH']:
            message = 'Please authenticate with your token.'
        else:
            message = 'Please authenticate.'
    response = jsonify(
        {
            'status': 401,
            'error': 'unauthorized',
            'message': message
        }
    )
    response.status_code = 401
    if current_app.config['USE_TOKEN_AUTH']:
        response.headers['Location'] = url_for('token.request_token')
    return response

def not_found(message):
    u"""HTTP 404"""
    response = jsonify(
        {
            'status': 404,
            'error': 'not found',
            'message': message
        }
    )
    response.status_code = 404
    return response

def not_allowed():
    u"""HTTP 405"""
    response = jsonify(
        {
            'status': 405,
            'error': 'method not allowed'
        }
    )
    response.status_code = 405
    return response
