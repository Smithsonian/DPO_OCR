#!/usr/bin/env python3
# 
# Identify blocks of text in OCR
#

import io, json, sys, os, psycopg2, logging
from pathlib import Path
from psycopg2.extras import RealDictCursor
from time import localtime, strftime
from fuzzywuzzy import fuzz


ver = 0.1

##Import settings from settings.py file
import settings



############################################
# Logging
############################################
if not os.path.exists('logs'):
    os.makedirs('logs')
current_time = strftime("%Y%m%d%H%M%S", localtime())
logfile_name = '{}.log'.format(current_time)
logfile = 'logs/{logfile_name}'.format(logfile_name = logfile_name)
# from http://stackoverflow.com/a/9321890
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M:%S',
                    filename=logfile,
                    filemode='a')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logger1 = logging.getLogger("block_id")
logging.getLogger('block_id').addHandler(console)
logger1.info("block_id version {}".format(ver))
############################################


#Insert query
insert_q = "INSERT INTO ocr_interpreted_blocks (document_id, block_id, data_type, interpreted_value) VALUES (%(document_id)s, %(block_id)s, %(data_type)s, %(interpreted_value)s)"


#OCR Database
conn = psycopg2.connect(host = settings.ocr_host, database = settings.ocr_db, user = settings.ocr_user, password = settings.ocr_password, connect_timeout = 60)
conn.autocommit = True
db_cursor = conn.cursor(cursor_factory=RealDictCursor)



#Delete previous id's
db_cursor.execute("DELETE FROM ocr_interpreted_blocks WHERE document_id IN (SELECT document_id FROM ocr_documents WHERE project_id = %(project_id)s)", {'project_id': settings.project_id})
logger1.debug(db_cursor.query.decode("utf-8"))


#Get entries with confidence value over the threshold from settings
db_cursor.execute("SELECT document_id, block, string_agg(word_text, ' ') as block_text, avg(confidence) as block_confidence FROM ocr_entries WHERE confidence > %(confidence)s AND document_id IN (SELECT document_id FROM ocr_documents WHERE project_id = %(project_id)s) group by document_id, block", {'confidence': settings.confidence, 'project_id': settings.project_id})
ocr_blocks = db_cursor.fetchall()
logger1.debug(db_cursor.query.decode("utf-8"))


#Iterate for words for collector
for ocr_block in ocr_blocks:
    #print(ocr_block['block_text'])
    #Identify Collector
    for coll in settings.collector_strings:
        if coll in ocr_block['block_text']:
            interpreted_value = ocr_block['block_text'].replace('Collector', '').replace('collector', '').strip()
            if interpreted_value != "":
                db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'collector', 'interpreted_value': interpreted_value})
                print('Collector: {}'.format(interpreted_value))
                continue



#GIS database
conn2 = psycopg2.connect(host = settings.gis_host, database = settings.gis_db, user = settings.gis_user, password = settings.gis_password, connect_timeout = 60)
db_cursor2 = conn2.cursor(cursor_factory=RealDictCursor)

#Get sub-state/province localities from GIS database
db_cursor2.execute("SELECT name_2 || ', ' || name_1 || ', ' || name_0 as name FROM gadm2")
sub_states = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))
#Get state/provinces from GIS database
db_cursor2.execute("SELECT name_1, name_1 || ', ' || name_0 as name FROM gadm1")
states = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))
#Get countries from GIS database
db_cursor2.execute("SELECT name_0 as name FROM gadm0")
countries = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))


#Iterate for localities
for ocr_block in ocr_blocks:
    #print(ocr_block['block_text'])
    interpreted_value = ""
    #Check in sub-state/province localities
    for locality in sub_states:
        sim_value = fuzz.token_set_ratio(ocr_block['block_text'], locality['name'])
        if (sim_value > settings.sim_threshold):
            interpreted_value = locality['name']
            db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'locality:sub-state', 'interpreted_value': interpreted_value})
            logger1.debug(db_cursor.query.decode("utf-8"))
            print('Locality:sub-state: {}'.format(interpreted_value))
            break
    #Check in state/provinces
    if interpreted_value == "":
        for state in states:
            sim_value = fuzz.token_set_ratio(ocr_block['block_text'], state['name'])
            if (sim_value > settings.sim_threshold):
                interpreted_value = state['name']
                db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'locality:state', 'interpreted_value': interpreted_value})
                logger1.debug(db_cursor.query.decode("utf-8"))
                print('Locality:state: {}'.format(interpreted_value))
                break
    #Locality was not found using state/province, try country
    if interpreted_value == "":
        for country in countries:
            sim_value = fuzz.token_set_ratio(ocr_block['block_text'], country['name'])
            if (sim_value > settings.sim_threshold):
                interpreted_value = country['name']
                db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'locality:country', 'interpreted_value': interpreted_value})
                logger1.debug(db_cursor.query.decode("utf-8"))
                print('Locality:country: {}'.format(interpreted_value))
                break


#Close GIS database connection
db_cursor2.close()
conn2.close()



#Get taxonomy info from OCR database
db_cursor.execute("SELECT *, genus || ' ' || species as sciname, left(genus, 1) || '. ' || species as sciname_abbr FROM ocr_taxonomy WHERE project_id = %(project_id)s", {'project_id': settings.project_id})
taxonomy = db_cursor.fetchall()


#Iterate for scinames
for ocr_block in ocr_blocks:
    #print(ocr_block['block_text'])
    interpreted_value = ""
    #Check species
    for taxo in taxonomy:
        sim_value = fuzz.token_set_ratio(ocr_block['block_text'], taxo['sciname'])
        if (sim_value > settings.sim_threshold):
            interpreted_value = taxo['sciname']
            db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'taxonomy:sciname', 'interpreted_value': interpreted_value})
            logger1.debug(db_cursor.query.decode("utf-8"))
            print('taxonomy:sciname: {}'.format(interpreted_value))
            break
    #Name was not found using species, try genus species with genus abbreviated
    if interpreted_value == "":
        for taxo in taxonomy:
            sim_value = fuzz.token_set_ratio(ocr_block['block_text'], taxo['sciname_abbr'])
            if (sim_value > settings.sim_threshold):
                interpreted_value = taxo['sciname_abbr']
                db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'taxonomy:sciname_abbr', 'interpreted_value': interpreted_value})
                logger1.debug(db_cursor.query.decode("utf-8"))
                print('taxonomy:sciname_abbr: {}'.format(interpreted_value))
                break
    #Name was not found, try next rank
    if interpreted_value == "":
        for taxo in taxonomy:
            if taxo['genus'] != "":
                sim_value = fuzz.token_set_ratio(ocr_block['block_text'], taxo['genus'])
                if (sim_value > settings.sim_threshold):
                    interpreted_value = taxo['genus']
                    db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'taxonomy:genus', 'interpreted_value': interpreted_value})
                    logger1.debug(db_cursor.query.decode("utf-8"))
                    print('taxonomy:genus: {}'.format(interpreted_value))
                    break
    #Name was not found, try next rank
    if interpreted_value == "":
        for taxo in taxonomy:
            if taxo['family'] != "":
                sim_value = fuzz.token_set_ratio(ocr_block['block_text'], taxo['family'])
                if (sim_value > settings.sim_threshold):
                    interpreted_value = taxo['family']
                    db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'taxonomy:family', 'interpreted_value': interpreted_value})
                    logger1.debug(db_cursor.query.decode("utf-8"))
                    print('taxonomy:family: {}'.format(interpreted_value))
                    break






#Close database connection
db_cursor.close()
conn.close()




#Compress log files
script_dir = os.getcwd()
os.chdir('logs')
for file in glob.glob('*.log'):
    subprocess.run(["zip", "{}.zip".format(file), file])
    os.remove(file)
os.chdir(script_dir)



sys.exit(0)