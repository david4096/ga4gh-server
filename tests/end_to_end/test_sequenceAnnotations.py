"""
Sequence Annotations testing on the test data
"""
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import logging

import ga4gh.protocol as protocol
import ga4gh.frontend as frontend
import tests.paths as paths


class TestSequenceAnnotations(unittest.TestCase):
    exampleUrl = 'www.example.com'
    datasetId = "YnJjYTE"

    @classmethod
    def setUpClass(cls):
        config = {
            "DATA_SOURCE": paths.testDataRepo,
            "DEBUG": False
        }
        logging.getLogger('ga4gh.frontend.cors').setLevel(logging.CRITICAL)
        frontend.reset()
        frontend.configure(
            baseConfig="TestConfig", extraConfig=config)
        cls.app = frontend.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.app = None

    def sendSearchRequest(self, path, request, responseClass):
        """
        Sends the specified protocol request instance as JSON, and
        parses the result into an instance of the specified response.
        """
        response = self.sendJsonPostRequest(path, protocol.toJson(request))
        self.assertEqual(200, response.status_code)
        responseData = protocol.fromJson(response.data, responseClass)
        self.assertTrue(
            protocol.validate(protocol.toJson(responseData), responseClass))
        return responseData

    def getAllDatasets(self):
        path = 'datasets/search'
        request = protocol.SearchDatasetsRequest()
        responseData = self.sendSearchRequest(
            path, request, protocol.SearchDatasetsResponse)
        return responseData.datasets

    def getAllFeatureSets(self):
        datasetId = self.getAllDatasets()[0].id
        path = 'featuresets/search'
        request = protocol.SearchFeatureSetsRequest()
        request.dataset_id = datasetId
        responseData = self.sendSearchRequest(
            path, request, protocol.SearchFeatureSetsResponse)
        return responseData.feature_sets

    def testSearchFeatureAttributes(self):
        featureSets = self.getAllFeatureSets()
        ran = False
        for featureSet in featureSets:
            ran = True
            # find a feature
            path = "features/search"
            featureSetId = featureSet.id
            request = protocol.SearchFeaturesRequest()
            request.feature_set_id = featureSetId
            request.start = 0
            request.end = 2**16
            request.page_size = 1
            request.reference_name = "chr1"
            responseData = self.sendSearchRequest(
                path, request, protocol.SearchFeaturesResponse)
            request.feature_set_id = featureSetId
            for feature in responseData.features:
                for key in feature.attributes.vals:
                    # Make a request for each key with a bad value
                    request.attributes[key] = "NOT A GOOD VALUE"
                    request.page_size = 100
                    innerResponse = self.sendSearchRequest(
                        path, request, protocol.SearchFeaturesResponse)
                    for innerFeature in innerResponse.features:
                        self.assertNotEqual(innerFeature.id, feature.id)
                    request.attributes[key] = feature.attributes.vals[key].values[0].string_value
                    innerResponse = self.sendSearchRequest(
                        path, request, protocol.SearchFeaturesResponse)
                    found = False
                    for innerFeature in innerResponse.features:
                        if innerFeature.id == feature.id:
                            found = True
                    self.assertTrue(found)
        self.assertTrue(ran)

    def testSearchFeatures(self):
        featureSets = self.getAllFeatureSets()
        for featureSet in featureSets:
            path = "features/search"
            request = protocol.SearchFeaturesRequest()
            request.feature_set_id = featureSet.id
            request.start = 0
            request.end = 2**16
            request.feature_types.extend(["exon"])
            request.reference_name = "chr1"
            responseData = self.sendSearchRequest(
                path, request, protocol.SearchFeaturesResponse)
            for feature in responseData.features:
                self.assertIn(
                    feature.feature_type.term,
                    request.feature_types,
                    "Term should be present {} {} \n{}\n{}".format(
                        feature.feature_type.term,
                        request.feature_types,
                        feature, request))

            path = "features/search"
            request = protocol.SearchFeaturesRequest()
            request.feature_set_id = featureSet.id
            request.start = 0
            request.end = 2**16
            request.feature_types.extend(["gene", "exon"])
            request.reference_name = "chr1"
            responseData = self.sendSearchRequest(
                path, request, protocol.SearchFeaturesResponse)
            for feature in responseData.features:
                self.assertIn(feature.feature_type.term, request.feature_types)

            request = protocol.SearchFeaturesRequest()
            request.feature_set_id = featureSet.id
            request.start = 0
            request.end = 2**16
            request.feature_types.extend(["exon"])
            request.reference_name = "chr1"
            responseData = self.sendSearchRequest(
                path, request, protocol.SearchFeaturesResponse)
            for feature in responseData.features:
                self.assertIn(feature.feature_type.term, request.feature_types)

    def sendJsonPostRequest(self, path, data):
        """
        Sends a JSON request to the specified path with the specified data
        and returns the response.
        """
        return self.app.post(
            path, headers={'Content-type': 'application/json'},
            data=data)
