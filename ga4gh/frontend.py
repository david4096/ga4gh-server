"""
The Flask frontend for the GA4GH API.

TODO Document properly.
"""
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask

import configApp
import ga4gh.exceptions as exceptions
import ga4gh.routes as routes
import ga4gh.auth as auth
import ga4gh.handlers as handlers


SECRET_KEY_LENGTH = 24

app = flask.Flask(__name__)


def configure(configFile=None, baseConfig="ProductionConfig",
              port=8000, extraConfig={}):
    configApp.configure(app, configFile, baseConfig, port, extraConfig)


def reset():
    """
    Resets the flask app; used in testing
    """
    app.config.clear()
    configStr = 'ga4gh.serverconfig:FlaskDefaultConfig'
    app.config.from_object(configStr)


@app.errorhandler(Exception)
def handleException(exception):
    """
    Handles an exception that occurs somewhere in the process of handling
    a request.
    """
    if app.config['DEBUG']:
        app.log_exception(exception)
    serverException = exception
    if not isinstance(exception, exceptions.BaseServerException):
        serverException = exceptions.getServerError(exception)
    responseStr = serverException.toProtocolElement().toJsonString()
    return handlers.getFlaskResponse(responseStr, serverException.httpStatus)

@app.errorhandler(404)
def pathNotFoundHandler(errorString):
    return handleException(exceptions.PathNotFoundException())


@app.errorhandler(405)
def methodNotAllowedHandler(errorString):
    return handleException(exceptions.MethodNotAllowedException())


@app.errorhandler(403)
def notAuthenticatedHandler(errorString):
    return handleException(exceptions.NotAuthenticatedException())

app.urls = []

routes.addRoutes(app)
auth.addAuth(app)