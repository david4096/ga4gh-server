import datetime

import humanize

import ga4gh
import ga4gh.protocol as protocol

class ServerStatus(object):
    """
    Generates information about the status of the server for display
    """
    def __init__(self, app):
        self.app = app
        self.startupTime = datetime.datetime.now()

    def getConfiguration(self):
        """
        Returns a list of configuration (key, value) tuples
        that are useful for users to view on an information page.
        Note that we should be careful here not to leak sensitive
        information. For example, keys and paths of data files should
        not be returned.
        """
        # TODO what other config keys are appropriate to export here?
        keys = [
            'DEBUG', 'REQUEST_VALIDATION', 'RESPONSE_VALIDATION',
            'DEFAULT_PAGE_SIZE', 'MAX_RESPONSE_LENGTH',
        ]
        return [(k, self.app.config[k]) for k in keys]

    def getPreciseUptime(self):
        """
        Returns the server precisely.
        """
        return self.startupTime.strftime("%H:%M:%S %d %b %Y")

    def getNaturalUptime(self):
        """
        Returns the uptime in a human-readable format.
        """
        return humanize.naturaltime(self.startupTime)

    def getProtocolVersion(self):
        """
        Returns the GA4GH protocol version we support.
        """
        return protocol.version

    def getServerVersion(self):
        """
        Returns the software version of this server.
        """
        return ga4gh.__version__

    def getUrls(self):
        """
        Returns the list of (httpMethod, URL) tuples that this server
        supports.
        """
        self.app.urls.sort()
        return self.app.urls

    def getDatasets(self):
        """
        Returns the list of datasetIds for this backend
        """
        return self.app.backend.getDataRepository().getDatasets()

    def getVariantSets(self, datasetId):
        """
        Returns the list of variant sets for the dataset
        """
        return self.app.backend.getDataRepository().getDataset(
            datasetId).getVariantSets()

    def getReadGroupSets(self, datasetId):
        """
        Returns the list of ReadGroupSets for the dataset
        """
        return self.app.backend.getDataRepository().getDataset(
            datasetId).getReadGroupSets()

    def getReferenceSets(self):
        """
        Returns the list of ReferenceSets for this server.
        """
        return self.app.backend.getDataRepository().getReferenceSets()