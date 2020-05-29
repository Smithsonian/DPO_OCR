#!/usr/bin/env python3
# 
# Identify blocks of text in OCR
#

import io, json, sys, os, psycopg2, logging, subprocess, swifter
from glob import glob
from pathlib import Path
from psycopg2.extras import RealDictCursor
from time import localtime, strftime
from fuzzywuzzy import fuzz
import pandas as pd

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
insert_q = "INSERT INTO ocr_interpreted_blocks (document_id, block_id, data_type, interpreted_value, verbatim_value) VALUES (%(document_id)s, %(block_id)s, %(data_type)s, %(interpreted_value)s, %(verbatim_value)s) ON CONFLICT (document_id, block_id, data_type) DO UPDATE SET interpreted_value = %(interpreted_value)s, verbatim_value = %(verbatim_value)s"


#OCR Database
conn = psycopg2.connect(host = settings.ocr_host, database = settings.ocr_db, user = settings.ocr_user, password = settings.ocr_password, connect_timeout = 60)
conn.autocommit = True
db_cursor = conn.cursor(cursor_factory=RealDictCursor)

#GIS database
conn2 = psycopg2.connect(host = settings.gis_host, database = settings.gis_db, user = settings.gis_user, password = settings.gis_password, connect_timeout = 60)
db_cursor2 = conn2.cursor(cursor_factory=RealDictCursor)



#Delete previous id's
db_cursor.execute("DELETE FROM ocr_interpreted_blocks WHERE document_id IN (SELECT document_id FROM ocr_documents WHERE project_id = %(project_id)s)", {'project_id': settings.project_id})
logger1.debug(db_cursor.query.decode("utf-8"))


#Get entries with confidence value over the threshold from settings
#db_cursor.execute("SELECT document_id, block, string_agg(word_text, ' ') as block_text, avg(confidence) as block_confidence FROM (SELECT * FROM ocr_entries WHERE confidence > %(confidence)s AND document_id IN (SELECT document_id FROM ocr_documents WHERE project_id = %(project_id)s) order by word) b GROUP BY document_id, block", {'confidence': settings.confidence, 'project_id': settings.project_id})
db_cursor.execute("SELECT document_id, block, string_agg(word_text, ' ') as block_text, avg(confidence) as block_confidence FROM (SELECT * FROM ocr_entries WHERE confidence > %(confidence)s AND document_id = '1cd95f9a-a99f-4888-b967-b96c1c2a79fa'  ORDER BY word) a GROUP BY document_id, block", {'confidence': settings.confidence})


ocr_blocks = db_cursor.fetchall()
logger1.debug(db_cursor.query.decode("utf-8"))



#Get sub-state/province localities from GIS database
db_cursor2.execute("SELECT name_2 || ', ' || name_1 || ', ' || name_0 as name, 'locality:sub-state' as name_type, uid FROM gadm2")
sub_states = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))
#Get state/provinces from GIS database
db_cursor2.execute("SELECT name_1 || ', ' || name_0 as name, 'locality:state' as name_type, uid FROM gadm1")
states = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))
#Get countries from GIS database
db_cursor2.execute("SELECT name_0 as name, 'locality:country' as name_type, uid FROM gadm0")
countries = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))


#Iterate for localities
for ocr_block in ocr_blocks:
    logger1.info("Block text: {}".format(ocr_block['block_text']))
    #Countries
    countries_match = pd.DataFrame(countries)
    states_match = pd.DataFrame(states)
    sub_states_match = pd.DataFrame(sub_states)
    countries_match = countries_match.append(states_match, ignore_index=True).append(sub_states_match, ignore_index=True)
    countries_match['score'] = countries_match.apply(lambda row : fuzz.token_sort_ratio(ocr_block['block_text'], row['name']), axis = 1)
    top_row = countries_match.sort_values(by = 'score', ascending = False)[0:1].copy()
    if (int(top_row.iloc[0]['score']) >= settings.sim_threshold):
        interpreted_value = top_row.iloc[0]['name']
        block_text = ocr_block['block_text']
        block_text_words = block_text.split(' ')
        block_df = pd.DataFrame(columns = ['text'])
        #Build a df with pieces of the string to find the best match
        for i in range(len(block_text_words)):
            for j in range(1, len(block_text_words) + 1):
                if j > i:
                    block_df.loc[len(block_df)] = [" ".join(block_text_words[i:j])]
        block_df['score'] = block_df.apply(lambda row : fuzz.token_sort_ratio(interpreted_value, row['text']), axis = 1)
        block_df_top_row = block_df.sort_values(by = 'score', ascending = False)[0:1].copy()
        db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': top_row.iloc[0]['name_type'], 'interpreted_value': interpreted_value, 'verbatim_value': block_df_top_row.iloc[0]['text']})
        logger1.debug(db_cursor.query.decode("utf-8"))
        logger1.info('Locality: {} (uid: gadm0:{}, token_set_ratio: {})'.format(interpreted_value, top_row.iloc[0]['uid'], top_row.iloc[0]['score']))
    




#Close GIS database connection
db_cursor2.close()
conn2.close()



#Get taxonomy info from OCR database
db_cursor.execute("""
                SELECT sciname, sortorder, name_type FROM
                (
                SELECT DISTINCT genus || ' ' || species as sciname, 1 as sortorder, 'taxonomy:species' as name_type FROM ocr_taxonomy WHERE project_id = %(project_id)s
                UNION
                SELECT DISTINCT species as sciname, 2 as sortorder, 'taxonomy:species_abbr' as name_type FROM ocr_taxonomy WHERE project_id = %(project_id)s
                UNION
                SELECT DISTINCT genus as sciname, 3 as sortorder, 'taxonomy:genus' as name_type FROM ocr_taxonomy WHERE project_id = %(project_id)s
                UNION
                SELECT DISTINCT family as sciname, 4 as sortorder, 'taxonomy:family' as name_type FROM ocr_taxonomy WHERE project_id = %(project_id)s
                ) a 
                ORDER BY sciname, sortorder
                """, {'project_id': settings.project_id})
taxonomy = db_cursor.fetchall()
taxo_match = pd.DataFrame(taxonomy)

countries_match = countries_match.append(states_match, ignore_index=True).append(sub_states_match, ignore_index=True)



#Iterate for scinames
for ocr_block in ocr_blocks:
    logger1.info("Block text: {}".format(ocr_block['block_text']))
    interpreted_value = ""
    #Check species
    taxo_match = pd.DataFrame(taxonomy)
    taxo_match['score'] = taxo_match.apply(lambda row : fuzz.token_sort_ratio(ocr_block['block_text'], row['sciname']), axis = 1)
    top_row = taxo_match.sort_values(by = ['score', 'sortorder'], ascending = False)[0:1].copy()
    if (int(top_row.iloc[0]['score']) >= settings.sim_threshold):
        interpreted_value = top_row.iloc[0]['sciname']
        db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': top_row.iloc[0]['name_type'], 'interpreted_value': interpreted_value, 'verbatim_value': ""})
        logger1.debug(db_cursor.query.decode("utf-8"))
        logger1.info('taxonomy:sciname: {} (token_set_ratio: {})'.format(interpreted_value, top_row.iloc[0]['score']))







# #Iterate for words for collector
for ocr_block in ocr_blocks:
    logger1.info("Block text: {}".format(ocr_block['block_text']))
    #Identify Collector
    for coll in settings.collector_strings:
        if coll in ocr_block['block_text']:
            interpreted_value = ocr_block['block_text']
            #Remove interpreted values in other fields
            db_cursor.execute("SELECT verbatim_value FROM ocr_interpreted_blocks WHERE document_id = %(document_id)s AND block_id = %(block_id)s AND data_type != 'collector'", {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block']})
            other_vals = db_cursor.fetchall()
            for row in other_vals:
                interpreted_value = interpreted_value.replace(row['verbatim_value'], '').strip()
                print("{}|{}".format(row['verbatim_value'], interpreted_value))
            interpreted_value = interpreted_value.replace(coll, '').strip()
            db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'collector', 'interpreted_value': interpreted_value, 'verbatim_value': ""})
            logger1.info('Collector ({}): {}'.format(coll, interpreted_value))
            break





#Close database connection
db_cursor.close()
conn.close()




#Compress log files
script_dir = os.getcwd()
os.chdir('logs')
for file in glob('*.log'):
    subprocess.run(["zip", "{}.zip".format(file), file])
    os.remove(file)
os.chdir(script_dir)



sys.exit(0)