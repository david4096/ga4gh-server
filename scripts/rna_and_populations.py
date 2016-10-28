"""
1kgenomes population_data.py
"""
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import os
import shutil
import json
import pysam
import utils
import sys
import generate_gff3_db
import tempfile
import zipfile
import csv
import datetime
import string 
import sqlite3
import urllib 

utils.ga4ghImportGlue()

# We need to turn off QA because of the import glue
import ga4gh.datarepo as datarepo  # NOQA
import ga4gh.datamodel.references as references  # NOQA
import ga4gh.datamodel.datasets as datasets  # NOQA
import ga4gh.datamodel.variants as variants  # NOQA
import ga4gh.datamodel.reads as reads  # NOQA
import ga4gh.datamodel.ontologies as ontologies  # NOQA
import ga4gh.datamodel.sequence_annotations as sequenceAnnotations  # NOQA
import ga4gh.datamodel.bio_metadata as biodata  # NOQA
import ga4gh.repo.rnaseq2ga as rnaseq2ga

# save_files_locally()
# Requires wget
def save_files_locally(data):
  print("Gonna download {} indexes!".format(len(data)))
  for row in data:
      download_url = make_address(row['name'], os.path.basename(row['indexUrl'])) 
      os.system("wget {}".format(download_url)) 
	

# converts the data in the merged json, which describes the locations of BAMs in
# EBI's ftp into amazon url's
def make_address( dirname, filename ):
    base = "http://"
    url = "s3.amazonaws.com/1000genomes/"
    return base + url + "phase3/data/" + dirname + "/alignment/" + filename  

# parses population metadata in csv file and returns
# individual and biosample dictionaries
def parse_file(filename):
  bio_samples = []
  individuals = []
  print("Loading biodata csv")
  with open(filename, 'r') as csvfile:
      reader = csv.DictReader(csvfile)
      for row in reader:
        description = "{}{}{}".format(
          row['Population'],
          row['Population Description'],
          row['Gender'])
        info = {}
        for key in row:
          info[key] = [row[key]]
        # TODO update to use schemas
        biosample = {
             "name": row['Sample'],
             "description": description,
             "disease": None,  # Ontology term
             "created": datetime.datetime.now().isoformat(),
             "updated": datetime.datetime.now().isoformat(),
             "info": info
        }
        if row['Gender'] == 'male':
           sex = {
               "id": "PATO:0020001",
               "term": "male genotypic sex",
               "sourceName": "PATO",
               "sourceVersion": "2015-11-18"
        }
        elif row['Gender'] == 'female':
          sex = {
            "id": "PATO:0020002",
            "term": "female genotypic sex",
            "sourceName": "PATO",
            "sourceVersion": "2015-11-18"
          }
        else:
          sex = None
        individual = {
               "name": row['Sample'],
               "description": description,
               "created": datetime.datetime.now().isoformat(),
               "updated": datetime.datetime.now().isoformat(),
               "species": {
                   "term": "Homo sapiens",
                   "id": "NCBITaxon:9606",
                   "sourceName": "http://purl.obolibrary.org/obo",
                   "sourceVersion": "2016-02-02"
                     },
                     "sex": sex,
                     "info": info
        }
        bio_samples.append(biosample)
        individuals.append(individual)
  return individuals, bio_samples


# main():
# populates database relations with data from each person
# in both the individual and biosample directories 
@utils.Timed()
def main():
    index_list_path = 'scripts/merged.json'
    download_indexes = False
    #reference_set_path = '/Users/david/data/references/hs37d5.fa.gz'
    reference_set_path = '/run/shm/1000Genomes/reference/hs37d5.fa.gz'
    csv_location = 'scripts/20130606_sample_info.csv'
    individuals, bio_samples = parse_file(csv_location)
    repoPath = os.path.join("repo2.db")
    repo = datarepo.SqlDataRepository(repoPath)
    if ( os.path.isfile("repo2.db") == True ):
        os.system( "repo2.db" )
    repo.open("w")
    repo.initialise()
    dataset = datasets.Dataset("1kgenomes")
    dataset.setDescription("Variants from the 1000 Genomes project and GENCODE genes annotations")
    repo.insertDataset(dataset)
     
    print("Inserting individuals")
    new_individuals= []
    for individual in individuals:
      new_individual = biodata.Individual(dataset, individual['name'])
      new_individual.populateFromJson(json.dumps(individual))
      repo.insertIndividual(new_individual)
      new_individuals.append(new_individual)
    
    print("Inserting biosamples")
    new_bio_samples = []
    for bio_sample in bio_samples:
      new_bio_sample = biodata.BioSample(dataset, bio_sample['name'])
      new_bio_sample.populateFromJson(json.dumps(bio_sample))
      for individual in new_individuals:
        if individual.getLocalId() == new_bio_sample.getLocalId():
          new_bio_sample.setIndividualId(str(individual.getId()))
      repo.insertBioSample(new_bio_sample)
      new_bio_samples.append(new_bio_sample)

    print("Adding reference set (takes a while)")
    reference_set = references.HtslibReferenceSet("NCBI37")
    reference_set.populateFromFile(reference_set_path)
    # reference_set.setAssemblyId()
    reference_set.setDescription("NCBI37 assembly of the human genome")
    reference_set.setNcbiTaxonId(9606)
    # TODO is it derived?
    # reference_set.setIsDerived(refSetMetadata['isDerived'])
    reference_set.setSourceUri("ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/technical/reference/phase2_reference_assembly_sequence/hs37d5.fa.gz")
    # TODO set proper accessions!?
    # reference_set.setSourceAccessions(refSetMetadata['sourceAccessions'])
    for reference in reference_set.getReferences():
        reference.setNcbiTaxonId(9606)
        #reference.setSourceAccessions(
        #    refMetadata['sourceAccessions'])
    repo.insertReferenceSet(reference_set)
    vcf_directory = "/srv/ga4gh/ga4gh-example-data/datasets/1kgenomes/variants/release"
    annotation_directory = "/run/shm/1000Genomes/ann/filtered"
	#TODO add ontology, gencode, and variantSet 
    seq_ontology = ontologies.Ontology("so-xp")	
    ontology_file_path = 'so-xp-simple.obo'
    seq_ontology.populateFromFile(ontology_file_path)
    seq_ontology._id = "so-xp"
    repo.insertOntology(seq_ontology)
    repo.addOntology(seq_ontology)
    gencode_file_path = '/srv/ga4gh/ga4gh-example-data/datasets/1kgenomes/sequenceAnnotations/gencode_v24lift37.db'	
    gencode = sequenceAnnotations.Gff3DbFeatureSet(dataset, "gencode_v24lift37")
    gencode.setOntology(seq_ontology)
    gencode.populateFromFile(gencode_file_path)
    gencode.setReferenceSet(reference_set)
    repo.insertFeatureSet(gencode)
    name = "phase3-release"
    variant_set = variants.HtslibVariantSet(dataset, name)
    variant_set.setReferenceSet(reference_set)
    variant_set.populateFromDirectory(vcf_directory)
    #variant_set.checkConsistency()
    for call_set in variant_set.getCallSets():
	  for bio_sample in new_bio_samples:
		  if bio_sample.getLocalId() == call_set.getLocalId():
			  call_set.setBioSampleId(bio_sample.getId())
    repo.insertVariantSet(variant_set)
    name = "functional-annotation"
    variant_set2 = variants.HtslibVariantSet(dataset, name)
    variant_set2.setReferenceSet(reference_set)
    variant_set2.populateFromDirectory(annotation_directory)
    #variant_set2.checkConsistency()
    repo.insertVariantSet(variant_set2)
    for annotation_set in variant_set2.getVariantAnnotationSets():
	    annotation_set.setOntology(seq_ontology)
	    repo.insertVariantAnnotationSet(annotation_set)
 
    print("Load list of read group sets")
    with open (index_list_path) as merged:
        data = json.load(merged)
        print("Found {} read group sets".format(len(data)))
        if download_indexes:
          save_files_locally(data)
        # TODO might have to do something smart about pointing to different index locations
        for row in data:
            print("Adding {}".format(row['name']))
            download_url = make_address(row['name'], os.path.basename(row['dataUrl']))
            name = row['name']
            read_group_set = reads.HtslibReadGroupSet(dataset, name)
            #read_group_set.populateFromFile(download_url, os.path.join('/run/shm/1000Genomes/bamIndexes', row['indexUrl']))
            # could optimize by storing biodata in a name:value dictionary
            #for read_group in read_group_set.getReadGroups():
            #  for bio_sample in new_bio_samples:
            #      if bio_sample.getLocalId() == read_group.getSampleName():
            #          read_group.setBioSampleId(bio_sample.getId())
            #read_group_set.setReferenceSet(reference_set)
            #repo.insertReadGroupSet(read_group_set)
    quant_location = '/run/shm/1000Genomes/rna_quantifications' 
    store = rnaseq2ga.RnaSqliteStore(quant_location)
    store.createTables()
    directory_contents = os.listdir(quant_location)
    db_location = ''
    data_dir_list = []
    for element in directory_contents:    
        if (element == 'rnaseq.db'): db_location = quant_location + '/' + element
        if (element.startswith('hg') ): data_dir_list.append(element)
 
    for direct in data_dir_list:
        filename_location = dirtect +'/abundance.tsv'
        rnaseq2ga.rnaseq2ga(
        '.', filename_location, db_location,
        self._args.format, dataset=dataset, featureType='transcript',
        description='RNA seq data from lymphoblastoid cell lines in the 1000 Genome Project, ' 
                         'http://www.ebi.ac.uk/arrayexpress/experiments/E-GEUV-1/samples/', 
        programs=None,
        featureSetNames='gencode_v24lift37',
        readGroupSetNames=None,
        bioSampleId=dataset.getBioSampleId(file))
    rnaQuantificationSet = rna_quantification.SqliteRnaQuantificationSet(dataset, "E-GEUV-1 1000 Genomes RNA Quantification") 
    repo.commit()
    print ( "database filled!")			

if __name__ == "__main__":
    main()
