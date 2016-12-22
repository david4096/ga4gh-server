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
import sys
import generate_gff3_db
import tempfile
import zipfile
import csv
import datetime
import string 
import sqlite3
import urllib

import ga4gh.common.utils as utils
import glue

glue.ga4ghImportGlue()

base = "/media/data"
reference_set_location = base + "/hs37d5.fa.gz"
feature_set_location = base + "/gencode_v24lift37.db"
ontology_location = base + "/so-xp.obo"
variant_set_location = base + "/release"
variant_annotation_set_location = base + "/filtered"
rna_quantification_set_location = base + "/rna_quantifications/"

# We need to turn off QA because of the import glue
import ga4gh.server.datarepo as datarepo  # NOQA
import ga4gh.server.datamodel.references as references  # NOQA
import ga4gh.server.datamodel.datasets as datasets  # NOQA
import ga4gh.server.datamodel.variants as variants  # NOQA
import ga4gh.server.datamodel.reads as reads  # NOQA
import ga4gh.server.datamodel.ontologies as ontologies  # NOQA
import ga4gh.server.datamodel.sequence_annotations as sequenceAnnotations  # NOQA
import ga4gh.server.datamodel.bio_metadata as biodata  # NOQA
import ga4gh.server.datamodel.rna_quantification as rna_quantification  # NOQA
import ga4gh.server.repo.rnaseq2ga as rnaseq2ga  # NOQA

def init_database(location):
    os.system("""echo "
    CREATE TABLE RnaQuantification (
                           id TEXT NOT NULL PRIMARY KEY,
                           feature_set_ids TEXT,
                           description TEXT,
                           name TEXT,
                           read_group_ids TEXT,
                           programs TEXT,
                           bio_sample_id TEXT);

    -- Then create the expression table if it doesn't exist
    CREATE TABLE Expression (
                           id TEXT NOT NULL PRIMARY KEY,
                           rna_quantification_id TEXT,
                           name TEXT,
                           feature_id TEXT,
                           expression REAL,
                           is_normalized BOOLEAN,
                           raw_read_count REAL,
                           score REAL,
                           units INTEGER,
                           conf_low REAL,
                           conf_hi REAL);

    " > out
    sqlite3 {location} < out
    """.format(location))

def load_tsv(
        dblocation="rnaseq.db",
        location="/home/david/data/rna_quantifications/kallisto/HG00096/abundance.tsv",
        rna_quantification_id="rnaid",
        name="HG00096",
        bio_sample_id="bsid",
        description="desc",
        feature_set_ids="fsid"):
    os.system("""
    echo "

    -- make a table for the TSV
create table tsvdump(
                        target_id text,
                        length int,
                        eff_length real,
                        est_counts real,
                        tpm real);

    -- then load some data into it
    -- the TSV needs to have had its first line of column names removed
.separator \42{separator}\42
.import {location} tsvdump

insert into RnaQuantification (
                           id,
                           feature_set_ids,
                           description,
                           name,
                           read_group_ids,
                           programs,
                           bio_sample_id) VALUES('{rna_quantification_id}','{feature_set_ids}','{description}','{directory}','','','{bio_sample_id}');

    -- Then insert the new things into our table
insert into Expression select
                           target_id || '{directory}' as id,
                           '{rna_quantification_id}' as rna_quantification_id,
                           target_id as name,
                           target_id as feature_id,
                           est_counts as expression,
                           1 as is_normalized,
                           est_counts as raw_read_count,
                           target_id as score,
                           2 as units,
                           0 as conf_low,
                           0 as conf_hi from tsvdump;
    --, this will throw an error if it doesn't exist
drop table tsvdump;
    " > out
    sqlite3 {dblocation} < out
    """.format(
                dblocation=dblocation,
                location=location,
                rna_quantification_id=rna_quantification_id,
                directory=name,
                bio_sample_id=bio_sample_id,
                description=description,
                feature_set_ids=feature_set_ids,
                separator="\134\164"))


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
        description = "{} - {} - {}".format(
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
    reference_set_path = reference_set_location
    csv_location = 'scripts/20130606_sample_info.csv'
    individuals, bio_samples = parse_file(csv_location)
    repoPath = os.path.join("registry.db")
    repo = datarepo.SqlDataRepository(repoPath)
    repo.open("w")
    repo.initialise()
    dataset = datasets.Dataset("1kgenomes")
    dataset.setDescription("Variants from the 1000 Genomes project and GENCODE genes annotations")
    repo.insertDataset(dataset)
    repo.commit()
    print("Inserting individuals")
    new_individuals= []

    for individual in individuals:
      new_individual = biodata.Individual(dataset, individual['name'])
      new_individual.populateFromJson(json.dumps(individual))
      repo.insertIndividual(new_individual)
      new_individuals.append(new_individual)
    repo.commit()
    print("Inserting biosamples")
    new_bio_samples = []


    for bio_sample in bio_samples:
      new_bio_sample = biodata.BioSample(dataset, bio_sample['name'])
      new_bio_sample.populateFromJson(json.dumps(bio_sample))
      for individual in new_individuals:
        if individual.getLocalId() == new_bio_sample.getLocalId():
          new_bio_sample.setIndividualId(str(individual.getId()))
      repo.insertBioSample(new_bio_sample)
      dataset.addBioSample(new_bio_sample)
      new_bio_samples.append(new_bio_sample)
    repo.commit()
    print("Adding reference set (takes a while)")
    reference_set = references.HtslibReferenceSet("NCBI37")
    reference_set.populateFromFile(reference_set_path)
    reference_set.setAssemblyId("hg37")
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
    repo.commit()
    vcf_directory = variant_set_location
    annotation_directory = variant_annotation_set_location
	#TODO add ontology, gencode, and variantSet
    seq_ontology = ontologies.Ontology("so-xp")
    ontology_file_path = ontology_location
    seq_ontology.populateFromFile(ontology_file_path)
    seq_ontology._id = "so-xp"
    repo.insertOntology(seq_ontology)
    repo.addOntology(seq_ontology)
    gencode_file_path = feature_set_location
    gencode = sequenceAnnotations.Gff3DbFeatureSet(dataset, "gencode_v24lift37")
    gencode.setOntology(seq_ontology)
    gencode.populateFromFile(gencode_file_path)
    gencode.setReferenceSet(reference_set)
    dataset.addFeatureSet(gencode)
    repo.insertFeatureSet(gencode)
    name = "phase3-release"
    variant_set = variants.HtslibVariantSet(dataset, name)
    variant_set.setReferenceSet(reference_set)
    variant_set.populateFromDirectory(vcf_directory)
    #variant_set.checkConsistency()
    name_biosample_id_map = {}
    for bio_sample in new_bio_samples:
        name_biosample_id_map[bio_sample.getLocalId()] = bio_sample.getId()
    for call_set in variant_set.getCallSets():
        bio_sample_id = name_biosample_id_map.get(call_set.getLocalId(), None)
        if bio_sample_id:
            call_set.setBioSampleId(bio_sample_id)
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
    repo.commit()


    # with open(index_list_path) as merged:
    #     data = json.load(merged)
    #     print("Found {} read group sets".format(len(data)))
    #     if download_indexes:
    #       save_files_locally(data)
    #     # TODO might have to do something smart about pointing to different index locations
    #     for row in data:
    #         print("Adding {}".format(row['name']))
    #         download_url = make_address(row['name'], os.path.basename(row['dataUrl']))
    #         name = row['name']
    #         read_group_set = reads.HtslibReadGroupSet(dataset, name)
    #         # read_group_set.populateFromFile(download_url, os.path.join(base, 'indexes', row['indexUrl']))
    #         # could optimize by storing biodata in a name:value dictionary
    #         #for read_group in read_group_set.getReadGroups():
    #         #  for bio_sample in new_bio_samples:
    #         #      if bio_sample.getLocalId() == read_group.getSampleName():
    #         #          read_group.setBioSampleId(bio_sample.getId())
    #         read_group_set.setReferenceSet(reference_set)
    #         try:
    #             repo.insertReadGroupSet(read_group_set)
    #             repo.commit()
    #         except Exception as e:
    #             print("already had it {}".format(e))
    rna_base = rna_quantification_set_location
    quant_location = os.path.join(rna_base, 'sqlite/rnaseq.db')
    kallisto_location = os.path.join(rna_base, 'kallisto')
    store = rnaseq2ga.RnaSqliteStore(quant_location)
    store.createTables()
    directory_contents = os.listdir(kallisto_location)

    featureNameIdMap = {}

    @utils.Timed()
    def add_directory(directory):
        print("Adding RNA for {}".format(directory))
        filename_location = os.path.join(kallisto_location, directory,
                                         'abundance.tsv')
        return rnaseq2ga.rnaseq2ga(
            filename_location, quant_location, directory,
            'kallisto', dataset=dataset, featureType='transcript',
            description='RNA seq data from lymphoblastoid cell lines in the 1000 Genome Project, '
                        'http://www.ebi.ac.uk/arrayexpress/experiments/E-GEUV-1/samples/',
            programs=None,
            featureSetNames='gencode_v24lift37',
            readGroupSetNames=None,
            bioSampleId=dataset.getBioSampleByName(directory).getLocalId(),
            featureNameIdMap=featureNameIdMap)

    for directory in directory_contents:
        filename_location = os.path.join(kallisto_location, directory,
                                         'abundance.tsv')
        load_tsv(location=filename_location,
                 description='RNA seq data from lymphoblastoid cell lines in the 1000 Genome Project, '
                             'http://www.ebi.ac.uk/arrayexpress/experiments/E-GEUV-1/samples/',
                 bio_sample_id=dataset.getBioSampleByName(directory).getLocalId(),
                 feature_set_ids=gencode.getId(),
                 rna_quantification_id=directory,
                 dblocation=quant_location,
                 name=directory)
    rnaQuantificationSet = rna_quantification.SqliteRnaQuantificationSet(dataset, "E-GEUV-1 RNA Quantification")
    rnaQuantificationSet.setReferenceSet(reference_set)
    rnaQuantificationSet.populateFromFile(quant_location)
    repo.insertRnaQuantificationSet(rnaQuantificationSet)
    repo.commit()
    print ( "database filled!")			

if __name__ == "__main__":
    main()
