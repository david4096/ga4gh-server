import flask
import werkzeug
import ga4gh.handlers as handlers

import functools

SEARCH_ENDPOINT_METHODS = ['POST', 'OPTIONS']

class DisplayedRoute(object):
    """
    Registers that a route should be displayed on the html page
    """
    def __init__(
            self, path, app={}, postMethod=False, pathDisplay=None):
        self.path = path
        self.app = app
        self.methods = None
        if postMethod:
            methodDisplay = 'POST'
            self.methods = SEARCH_ENDPOINT_METHODS
        else:
            methodDisplay = 'GET'
        if pathDisplay is None:
            pathDisplay = path
        app.urls.append((methodDisplay, pathDisplay))

    def __call__(self, func):
        if self.methods is None:
            self.app.add_url_rule(self.path, func.func_name, func)
        else:
            self.app.add_url_rule(
                self.path, func.func_name, func, methods=self.methods)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return result
        return wrapper

class NoConverter(werkzeug.routing.BaseConverter):
    """
    A converter that allows the routing matching algorithm to not
    match on certain literal terms

    This is needed because if there are e.g. two routes:

    /callsets/search
    /callsets/<id>

    A request for /callsets/search will get routed to
    the second, which is not what we want.
    """
    def __init__(self, map, *items):
        werkzeug.routing.BaseConverter.__init__(self, map)
        self.items = items

    def to_python(self, value):
        if value in self.items:
            raise werkzeug.routing.ValidationError()
        return value


def addRoutes(app):

    app.url_map.converters['no'] = NoConverter

    @app.route('/')
    def index():
        return flask.render_template('index.html', info=app.serverStatus)


    @DisplayedRoute('/references/<id>', app=app)
    def getReference(id):
        return handlers.handleFlaskGetRequest(
            id, flask.request, app.backend.runGetReference)


    @DisplayedRoute('/referencesets/<id>', app=app)
    def getReferenceSet(id):
        return handlers.handleFlaskGetRequest(
            id, flask.request, app.backend.runGetReferenceSet)


    @DisplayedRoute('/references/<id>/bases', app=app)
    def listReferenceBases(id):
        return handlers.handleFlaskListRequest(
            id, flask.request, app.backend.runListReferenceBases)


    @DisplayedRoute('/callsets/search', app=app, postMethod=True)
    def searchCallSets():
        return handlers.handleFlaskPostRequest(
            flask.request, app.backend.runSearchCallSets)


    @DisplayedRoute('/readgroupsets/search', app=app, postMethod=True)
    def searchReadGroupSets():
        return handlers.handleFlaskPostRequest(
            flask.request, app.backend.runSearchReadGroupSets)


    @DisplayedRoute('/reads/search', app=app, postMethod=True)
    def searchReads():
        return handlers.handleFlaskPostRequest(
            flask.request, app.backend.runSearchReads)


    @DisplayedRoute('/referencesets/search', app=app, postMethod=True)
    def searchReferenceSets():
        return handlers.handleFlaskPostRequest(
            flask.request, app.backend.runSearchReferenceSets)


    @DisplayedRoute('/references/search', app=app, postMethod=True)
    def searchReferences():
        return handlers.handleFlaskPostRequest(
            flask.request, app.backend.runSearchReferences)


    @DisplayedRoute('/variantsets/search', app=app, postMethod=True)
    def searchVariantSets():
        return handlers.handleFlaskPostRequest(
            flask.request, app.backend.runSearchVariantSets)


    @DisplayedRoute('/variants/search', app=app ,postMethod=True)
    def searchVariants():
        return handlers.handleFlaskPostRequest(
            flask.request, app.backend.runSearchVariants)


    @DisplayedRoute('/datasets/search', app=app ,postMethod=True)
    def searchDatasets():
        return handlers.handleFlaskPostRequest(
            flask.request, app.backend.runSearchDatasets)


    @DisplayedRoute(
        '/variantsets/<no(search):id>',
        pathDisplay='/variantsets/<id>', app=app)
    def getVariantSet(id):
        return handlers.handleFlaskGetRequest(
            id, flask.request, app.backend.runGetVariantSet)


    @DisplayedRoute(
        '/variants/<no(search):id>',
        pathDisplay='/variants/<id>', app=app)
    def getVariant(id):
        return handlers.handleFlaskGetRequest(
            id, flask.request, app.backend.runGetVariant)


    @DisplayedRoute(
        '/readgroupsets/<no(search):id>',
        pathDisplay='/readgroupsets/<id>', app=app)
    def getReadGroupSet(id):
        return handlers.handleFlaskGetRequest(
            id, flask.request, app.backend.runGetReadGroupSet)


    @DisplayedRoute('/readgroups/<id>', app=app)
    def getReadGroup(id):
        return handlers.handleFlaskGetRequest(
            id, flask.request, app.backend.runGetReadGroup)


    @DisplayedRoute(
        '/callsets/<no(search):id>', app=app,
        pathDisplay='/callsets/<id>')
    def getCallSet(id):
        return handlers.handleFlaskGetRequest(
            id, flask.request, app.backend.runGetCallSet)

    @DisplayedRoute(
        '/datasets/<no(search):id>', app=app,
        pathDisplay='/datasets/<id>')
    def getDataset(id):
        return handlers.handleFlaskGetRequest(
            id, flask.request, app.backend.runGetDataset)
