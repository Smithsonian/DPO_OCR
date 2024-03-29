CREATE DATABASE ocr;
/*ALTER DATABASE ocr SET TABLESPACE [TABLESPACE];*/

\connect ocr;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS unaccent;

--pg_trgm extension
CREATE EXTENSION pg_trgm;


--Postgres function to update the column last_update on files when the row is updated
CREATE FUNCTION updated_at_files() RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$;



--ocr_projects
DROP TABLE IF EXISTS ocr_projects CASCADE;
CREATE TABLE ocr_projects
(
    project_id uuid NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_title text NOT NULL,
    project_shorttitle text NOT NULL,
    updated_at timestamp with time zone DEFAULT NOW()
);
CREATE INDEX ocr_projects_pid_idx ON ocr_projects USING BTREE(project_id);

CREATE TRIGGER trigger_updated_at_ocr_projects
  BEFORE UPDATE ON ocr_projects
  FOR EACH ROW
  EXECUTE PROCEDURE updated_at_files();


--ocr_documents
DROP TABLE IF EXISTS ocr_documents CASCADE;
CREATE TABLE ocr_documents
(
    document_id uuid NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id uuid REFERENCES ocr_projects(project_id) ON DELETE CASCADE ON UPDATE CASCADE,
    doc_version text DEFAULT 'default',
    doc_section text DEFAULT 'default',
    filename text NOT NULL,
    document_title text,
    ocr_source text NOT NULL,
    doc_width int,
    doc_height int,
    updated_at timestamp with time zone DEFAULT NOW()
);
CREATE INDEX ocr_documents_did_idx ON ocr_documents USING BTREE(document_id);
CREATE INDEX ocr_documents_pid_idx ON ocr_documents USING BTREE(project_id);
CREATE INDEX ocr_documents_fname_idx ON ocr_documents USING BTREE(filename);

CREATE TRIGGER trigger_updated_at_ocr_documents
  BEFORE UPDATE ON ocr_documents
  FOR EACH ROW
  EXECUTE PROCEDURE updated_at_files();


--ocr_entries
DROP TABLE IF EXISTS ocr_entries CASCADE;
CREATE TABLE ocr_entries
(
    entry_id uuid NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id uuid REFERENCES ocr_documents(document_id) ON DELETE CASCADE ON UPDATE CASCADE,
    word_text text NOT NULL,
    block integer,
    page integer,
    word integer,
    word_line integer,
    confidence float,
    vertices_x_0 integer,
    vertices_y_0 integer,
    vertices_x_1 integer,
    vertices_y_1 integer,
    vertices_x_2 integer,
    vertices_y_2 integer,
    vertices_x_3 integer,
    vertices_y_3 integer,
    updated_at timestamp with time zone DEFAULT NOW()
);
CREATE INDEX ocr_entries_eid_idx ON ocr_entries USING BTREE(entry_id);
CREATE INDEX ocr_entries_did_idx ON ocr_entries USING BTREE(document_id);
CREATE INDEX ocr_entries_conf_idx ON ocr_entries USING BTREE(confidence);

CREATE TRIGGER trigger_updated_at_ocr_entries
  BEFORE UPDATE ON ocr_entries
  FOR EACH ROW
  EXECUTE PROCEDURE updated_at_files();



--ocr_interpreted_blocks
DROP TABLE IF EXISTS ocr_interpreted_blocks CASCADE;
CREATE TABLE ocr_interpreted_blocks
(
    interpreted_id uuid NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id uuid REFERENCES ocr_documents(document_id) ON DELETE CASCADE ON UPDATE CASCADE,
    block_id int NOT NULL,
    data_type text,
    data_format text,
    interpreted_value text,
    verbatim_value text,
    data_source text,
    match_score numeric,
    feature_uid uuid,
    updated_at timestamp with time zone DEFAULT NOW()
);
ALTER TABLE ocr_interpreted_blocks ADD CONSTRAINT ocr_interpreted_blocks_did_bid_inval UNIQUE (document_id, block_id, data_type);

CREATE INDEX ocr_interpreted_blocks_iid_idx ON ocr_interpreted_blocks USING BTREE(interpreted_id);
CREATE INDEX ocr_interpreted_blocks_did_idx ON ocr_interpreted_blocks USING BTREE(document_id);
CREATE INDEX ocr_interpreted_blocks_bid_idx ON ocr_interpreted_blocks USING BTREE(block_id);
CREATE INDEX ocr_interpreted_blocks_intval_idx ON ocr_interpreted_blocks USING gin (interpreted_value gin_trgm_ops);
CREATE INDEX ocr_interpreted_blocks_verval_idx ON ocr_interpreted_blocks USING gin (verbatim_value gin_trgm_ops);

CREATE TRIGGER trigger_updated_at_ocr_interpreted_blocks
  BEFORE UPDATE ON ocr_interpreted_blocks
  FOR EACH ROW
  EXECUTE PROCEDURE updated_at_files();



--ocr_taxonomy table
DROP TABLE IF EXISTS ocr_taxonomy CASCADE;
CREATE TABLE ocr_taxonomy
(
    taxo_id uuid NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id uuid REFERENCES ocr_projects(project_id) ON DELETE CASCADE ON UPDATE CASCADE,
    kingdom text,
    phylum text,
    class text,
    _order text,
    family text,
    genus text,
    subgenus text,
    species text,
    subspecies text,
    author text,
    updated_at timestamp with time zone DEFAULT NOW()
);
CREATE INDEX ocr_taxonomy_pid_idx ON ocr_taxonomy USING BTREE(project_id);
CREATE INDEX ocr_taxonomy_species_idx ON ocr_taxonomy USING BTREE(species);
CREATE INDEX ocr_taxonomy_sgenus_idx ON ocr_taxonomy USING BTREE(subgenus);
CREATE INDEX ocr_taxonomy_genus_idx ON ocr_taxonomy USING BTREE(genus);
CREATE INDEX ocr_taxonomy_family_idx ON ocr_taxonomy USING BTREE(family);
CREATE INDEX ocr_taxonomy_order_idx ON ocr_taxonomy USING BTREE(_order);
CREATE INDEX ocr_taxonomy_class_idx ON ocr_taxonomy USING BTREE(class);
CREATE INDEX ocr_taxonomy_phylum_idx ON ocr_taxonomy USING BTREE(phylum);
CREATE INDEX ocr_taxonomy_kingdom_idx ON ocr_taxonomy USING BTREE(kingdom);

CREATE TRIGGER trigger_updated_at_ocr_taxonomy
  BEFORE UPDATE ON ocr_taxonomy
  FOR EACH ROW
  EXECUTE PROCEDURE updated_at_files();






--ocr_blocks
DROP TABLE IF EXISTS ocr_blocks CASCADE;
CREATE TABLE ocr_blocks
(
    document_id uuid REFERENCES ocr_documents(document_id) ON DELETE CASCADE ON UPDATE CASCADE,
    block int NOT NULL,
    confidence float,
    vertices_x_0 integer,
    vertices_y_0 integer,
    vertices_x_1 integer,
    vertices_y_1 integer,
    vertices_x_2 integer,
    vertices_y_2 integer,
    vertices_x_3 integer,
    vertices_y_3 integer,
    updated_at timestamp with time zone DEFAULT NOW()
);
CREATE INDEX ocr_block_did_idx ON ocr_blocks USING BTREE(document_id);
CREATE INDEX ocr_block_bid_idx ON ocr_blocks USING BTREE(block);

CREATE TRIGGER trigger_updated_at_ocr_block
  BEFORE UPDATE ON ocr_blocks
  FOR EACH ROW
  EXECUTE PROCEDURE updated_at_files();








--ocr_zones
DROP TABLE IF EXISTS ocr_zones CASCADE;
CREATE TABLE ocr_zones
(
    project_id uuid REFERENCES ocr_projects(project_id) ON DELETE CASCADE ON UPDATE CASCADE,
    zone_id uuid NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_version text DEFAULT 'default',
    doc_section text DEFAULT 'default',
    field_name text NOT NULL,
    field_order int DEFAULT 1,
    word_separator text DEFAULT ' ',
    row_no integer DEFAULT 1,
    vertices_x_0 integer,
    vertices_x_1 integer,
    vertices_y_0 integer,
    vertices_y_1 integer,
    updated_at timestamp with time zone DEFAULT NOW()
);
CREATE INDEX ocr_zones_pid_idx ON ocr_zones USING BTREE(project_id);
CREATE INDEX ocr_zones_zid_idx ON ocr_zones USING BTREE(zone_id);
CREATE INDEX ocr_zones_fname_idx ON ocr_zones USING BTREE(field_name);

CREATE TRIGGER trigger_updated_at_ocr_zones
  BEFORE UPDATE ON ocr_zones
  FOR EACH ROW
  EXECUTE PROCEDURE updated_at_files();



  --ocr_zonal_data
  DROP TABLE IF EXISTS ocr_zonal_data CASCADE;
  CREATE TABLE ocr_zonal_data
  (
      row_id uuid NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
      document_id uuid REFERENCES ocr_documents(document_id) ON DELETE CASCADE ON UPDATE CASCADE,
      entry_id text,
      zone_id uuid REFERENCES ocr_zones(zone_id) ON DELETE CASCADE ON UPDATE CASCADE,
      min_confidence numeric,
      word_text text,
      updated_at timestamp with time zone DEFAULT NOW()
  );
  ALTER TABLE ocr_zonal_data ADD CONSTRAINT ocr_zonal_data_did_bid_inval UNIQUE (document_id, entry_id, zone_id);

  CREATE INDEX ocr_zonal_data_rid_idx ON ocr_zonal_data USING BTREE(row_id);
  CREATE INDEX ocr_zonal_data_did_idx ON ocr_zonal_data USING BTREE(document_id);
  CREATE INDEX ocr_zonal_data_eid_idx ON ocr_zonal_data USING BTREE(entry_id);
  CREATE INDEX ocr_zonal_data_zid_idx ON ocr_zonal_data USING BTREE(zone_id);

  CREATE TRIGGER trigger_updated_at_ocr_zonal_data
    BEFORE UPDATE ON ocr_zonal_data
    FOR EACH ROW
    EXECUTE PROCEDURE updated_at_files();
