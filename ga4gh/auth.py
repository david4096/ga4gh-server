import socket
import urlparse
import functools

import flask
import flask.ext.cors as cors
import oic
import oic.oauth2
import oic.oic.message as message

import ga4gh.exceptions as exceptions

SECRET_KEY_LENGTH = 24

def addAuth(app):

    def startLogin():
        """
        If we are not logged in, this generates the redirect URL to the OIDC
        provider and returns the redirect response
        :return: A redirect response to the OIDC provider
        """
        flask.session["state"] = oic.oauth2.rndstr(SECRET_KEY_LENGTH)
        flask.session["nonce"] = oic.oauth2.rndstr(SECRET_KEY_LENGTH)
        args = {
            "client_id": app.oidcClient.client_id,
            "response_type": "code",
            "scope": ["openid", "profile"],
            "nonce": flask.session["nonce"],
            "redirect_uri": app.oidcClient.redirect_uris[0],
            "state": flask.session["state"]
        }

        result = app.oidcClient.do_authorization_request(
            request_args=args, state=flask.session["state"])
        return flask.redirect(result.url)


    @app.before_request
    def checkAuthentication():
        """
        The request will have a parameter 'key' if it came from the command line
        client, or have a session key of 'key' if it's the browser.
        If the token is not found, start the login process.

        If there is no oidcClient, we are running naked and we don't check.
        If we're being redirected to the oidcCallback we don't check.

        :returns None if all is ok (and the request handler continues as usual).
        Otherwise if the key was in the session (therefore we're in a browser)
        then startLogin() will redirect to the OIDC provider. If the key was in
        the request arguments, we're using the command line and just raise an
        exception.
        """
        if app.oidcClient is None:
            return
        if flask.request.endpoint == 'oidcCallback':
            return
        key = flask.session.get('key') or flask.request.args.get('key')
        if app.tokenMap.get(key) is None:
            if 'key' in flask.request.args:
                raise exceptions.NotAuthenticatedException()
            else:
                return startLogin()






    @app.route('/oauth2callback', methods=['GET'])
    def oidcCallback():
        """
        Once the authorization provider has cleared the user, the browser
        is returned here with a code. This function takes that code and
        checks it with the authorization provider to prove that it is valid,
        and get a bit more information about the user (which we don't use).

        A token is generated and given to the user, and the authorization info
        retrieved above is stored against this token. Later, when a client
        connects with this token, it is assumed to be a valid user.

        :return: A display of the authentication token to use in the client. If
        OIDC is not configured, raises a NotImplementedException.
        """
        if app.oidcClient is None:
            raise exceptions.NotImplementedException()
        response = dict(flask.request.args.iteritems(multi=True))
        aresp = app.oidcClient.parse_response(
            message.AuthorizationResponse,
            info=response,
            sformat='dict')
        sessState = flask.session.get('state')
        respState = aresp['state']
        if (not isinstance(aresp, message.AuthorizationResponse) or
                respState != sessState):
            raise exceptions.NotAuthenticatedException()

        args = {
            "code": aresp['code'],
            "redirect_uri": app.oidcClient.redirect_uris[0],
            "client_id": app.oidcClient.client_id,
            "client_secret": app.oidcClient.client_secret
        }
        atr = app.oidcClient.do_access_token_request(
            scope="openid",
            state=respState,
            request_args=args)

        if not isinstance(atr, message.AccessTokenResponse):
            raise exceptions.NotAuthenticatedException()

        atrDict = atr.to_dict()
        if flask.session.get('nonce') != atrDict['id_token']['nonce']:
            raise exceptions.NotAuthenticatedException()
        key = oic.oauth2.rndstr(SECRET_KEY_LENGTH)
        flask.session['key'] = key
        app.tokenMap[key] = aresp["code"], respState, atrDict
        # flask.url_for is broken. It relies on SERVER_NAME for both name
        # and port, and defaults to 'localhost' if not found. Therefore
        # we need to fix the returned url
        indexUrl = flask.url_for('index', _external=True)
        indexParts = list(urlparse.urlparse(indexUrl))
        if ':' not in indexParts[1]:
            indexParts[1] = '{}:{}'.format(socket.gethostname(), app.myPort)
            indexUrl = urlparse.urlunparse(indexParts)
        response = flask.redirect(indexUrl)
        return response

