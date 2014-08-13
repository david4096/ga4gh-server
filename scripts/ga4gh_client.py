"""
Command line interface for the ga4gh reference implementation.
"""
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import future
import argparse
 
from future.standard_library import hooks
with hooks():
    import http.client

import ga4gh
import ga4gh.protocol

class VariantSearchRunner(object):
    def __init__(self, args):
        self.start = args.start
        self.end = args.end
        self.verbosity = args.verbose
        self.http_client = http.client.HTTPConnection(args.hostname, args.port)
        self.http_client.set_debuglevel(self.verbosity)

    def run(self):
        svr = ga4gh.protocol.GASearchVariantsRequest()
        svr.start = self.start 
        svr.end = self.end 
        s = svr.toJSON()
        self.http_client.request("POST", "variants/search", s)
        r = self.http_client.getresponse()
        s = r.read().decode()
        resp = ga4gh.protocol.GASearchVariantsResponse.fromJSON(s)
        self.print_variants(resp)
    
    def print_variants(self, response):
        """
        Prints out the specified SearchVariantsReponse object in a VCF-like
        form.
        """
        for v in response.variants:
            print(v.id, v.variantSetId, v.names, v.created, v.updated, 
                    v.referenceName, v.start, v.end, v.referenceBases, 
                    v.alternateBases, sep="\t", end="")
            # TODO insert info fields
            for c in v.calls:
                print(c.genotype, c.genotypeLikelihood, sep=":", end="\t")
            print()

def main():
    parser = argparse.ArgumentParser(description="GA4GH reference client")                                       
    # Add global options
    parser.add_argument("--hostname", "-H", default="localhost",
            help="The server host")
    parser.add_argument("--port", "-P", default=8000, type=int,
            help="The server port")
    parser.add_argument('--verbose', '-v', action='count')
    subparsers = parser.add_subparsers(title='subcommands',)                                             
                                                                                                                 
    # help  
    help_parser = subparsers.add_parser("help",
            description = "ga4gh_client help",
            help="show this help message and exit")
    # variants/search 
    vs_parser = subparsers.add_parser("variants-search",
            description = "Search for variants",
            help="Search for variants.")
    vs_parser.set_defaults(runner=VariantSearchRunner)
    vs_parser.add_argument("--start", "-s", default=0, type=int,
            help="The start of the search range (inclusive).")
    vs_parser.add_argument("--end", "-e", default=1, type=int,
            help="The end of the search range (exclusive).")
    args = parser.parse_args()
    if "runner" not in args:
        parser.print_help()
    else:
        runner = args.runner(args)
        runner.run()

if __name__ == "__main__":
    main()
