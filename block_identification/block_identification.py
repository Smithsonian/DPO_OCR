#!/usr/bin/env python3
# 
# Identify blocks of text in OCR
#

import io, json, sys, os, psycopg2
from pathlib import Path
from psycopg2.extras import RealDictCursor
from fuzzywuzzy import fuzz


##Import settings from settings.py file
import settings


#OCR Database
conn = psycopg2.connect(host = settings.ocr_host, database = settings.ocr_db, user = settings.ocr_user, password = settings.ocr_password, connect_timeout = 60)
conn.autocommit = True
db_cursor = conn.cursor(cursor_factory=RealDictCursor)

#GIS database
conn2 = psycopg2.connect(host = settings.gis_host, database = settings.gis_db, user = settings.gis_user, password = settings.gis_password, connect_timeout = 60)
db_cursor2 = conn2.cursor(cursor_factory=RealDictCursor)



#Get entries over confidence value from settings
db_cursor.execute("SELECT document_id, block, string_agg(word_text, ' ') as block_text, avg(confidence) as block_confidence FROM ocr_entries WHERE confidence > %(confidence)s AND document_id IN (SELECT document_id FROM ocr_documents WHERE project_id = %(project_id)s) group by document_id, block", {'confidence': settings.confidence, 'project_id': settings.project_id})
ocr_blocks = db_cursor.fetchall()


#Get state/provinces from GIS database
db_cursor2.execute("SELECT name_1, name_1 || ', ' || name_0 as name FROM gadm1")
states = db_cursor2.fetchall()
#Get countries from GIS database
db_cursor2.execute("SELECT name_0 as name FROM gadm0")
countries = db_cursor2.fetchall()


#Iterate for words for collector
for ocr_block in ocr_blocks:
    print(ocr_block['block_text'])
    #Identify Collector
    if 'Collector' in ocr_block['block_text']:
        interpreted_value = ocr_block['block_text'].replace('Collector', '').replace('collector', '').strip()
        if interpreted_value != "":
            db_cursor.execute("INSERT INTO ocr_interpreted_blocks (document_id, block_id, data_type, interpreted_value) VALUES (%(document_id)s, %(block_id)s, %(data_type)s, %(interpreted_value)s)", {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'collector', 'interpreted_value': interpreted_value})
            print(interpreted_value)
            continue
    if 'coll.' in ocr_block['block_text'].lower():
        interpreted_value = ocr_block['block_text'].replace('coll.', '').replace('Coll.', '').strip()
        if interpreted_value != "":
            db_cursor.execute("INSERT INTO ocr_interpreted_blocks (document_id, block_id, data_type, interpreted_value) VALUES (%(document_id)s, %(block_id)s, %(data_type)s, %(interpreted_value)s)", {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'collector', 'interpreted_value': interpreted_value})
            print(interpreted_value)
            continue
    if 'coll ' in ocr_block['block_text'].lower() or ocr_block['block_text'].lower() == 'coll':
        interpreted_value = ocr_block['block_text'].replace('coll', '').replace('Coll', '').strip()
        if interpreted_value != "":
            db_cursor.execute("INSERT INTO ocr_interpreted_blocks (document_id, block_id, data_type, interpreted_value) VALUES (%(document_id)s, %(block_id)s, %(data_type)s, %(interpreted_value)s)", {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'collector', 'interpreted_value': interpreted_value})
            print(interpreted_value)
            continue



#Iterate for localities
for ocr_block in ocr_blocks:
    print(ocr_block['block_text'])
    interpreted_value = ""
    for state in states:
        sim_value = fuzz.token_set_ratio(ocr_block['block_text'], state['name_1'])
        if (sim_value > settings.sim_threshold):
            interpreted_value = state['name']
            db_cursor.execute("INSERT INTO ocr_interpreted_blocks (document_id, block_id, data_type, interpreted_value) VALUES (%(document_id)s, %(block_id)s, %(data_type)s, %(interpreted_value)s)", {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'locality', 'interpreted_value': interpreted_value})
            print(interpreted_value)
            continue
    #Locality was not found using state/province, try country
    if interpreted_value == "":
        for country in countries:
            sim_value = fuzz.token_set_ratio(ocr_block['block_text'], country['name'])
            if (sim_value > settings.sim_threshold):
                interpreted_value = country['name']
                db_cursor.execute("INSERT INTO ocr_interpreted_blocks (document_id, block_id, data_type, interpreted_value) VALUES (%(document_id)s, %(block_id)s, %(data_type)s, %(interpreted_value)s)", {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'locality', 'interpreted_value': interpreted_value})
                print(interpreted_value)
                continue



db_cursor.close()
conn.close()

db_cursor2.close()
conn2.close()
