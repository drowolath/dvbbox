#!/usr/bin/env python
# encoding: utf-8

from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from flask import current_app
from flask_redis import FlaskRedis

db = FlaskRedis()


class User(object):
    """represents a user of the api"""
    def __init__(self, username):
        if not bool(db.get(username)):
            raise ValueError("username does not exists")
        else:
            self.username = username
            self.password_hash = db.get(username)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
        db.set(self.username, self.password_hash)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_auth_token(self):
        s = Serializer(current_app.config['SECRET_KEY'], expires_in=3600)
        return s.dumps({'username': self.username}).decode('utf-8')

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
            return User(data['username'])
        except:
            return None



