echo "
-- Kallisto for 1kgenomes

-- let's start by initializing the rnaseqdb, these are copied from rnaseq2ga

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

-- make a table for the TSV

create table tsvdump(
                        target_id text,
                        length int,
                        eff_length real,
                        est_counts real,
                        tpm real);

-- then load some data into it
-- the TSV needs to have head its first line of column names removed
.separator \"\t\"
.import /home/david/data/rna_quantifications/kallisto/HG00096/abundance.tsv tsvdump


-- Then insert the new things into our table
insert into Expression select
                       target_id as id,
                       \"HG00096\" as rna_quantification_id,
                       target_id as name,
                       target_id as feature_id,
                       est_counts as expression,
                       1 as is_normalized,
                       est_counts as raw_read_count,
                       target_id as score,
                       2 as units,
                       0 as conf_low,
                       0 as conf_hi from tsvdump;
" > out
sqlite3 rnaseq.db < out
