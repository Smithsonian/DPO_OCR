#!/usr/bin/env python3
# 
# Identify blocks of text in OCR
#

import io, json, sys, os, psycopg2, logging, subprocess, swifter, re, dateparser
from glob import glob
from pathlib import Path
from psycopg2.extras import RealDictCursor
from time import localtime, strftime
from fuzzywuzzy import fuzz
import pandas as pd
from datetime import date

ver = "0.2.1"

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
insert_q = "INSERT INTO ocr_interpreted_blocks (document_id, block_id, data_type, data_format, interpreted_value, verbatim_value, data_source, match_score) VALUES (%(document_id)s, %(block_id)s, %(data_type)s, %(data_format)s, %(interpreted_value)s, %(verbatim_value)s, %(data_source)s, %(match_score)s) ON CONFLICT (document_id, block_id, data_type) DO UPDATE SET interpreted_value = %(interpreted_value)s, verbatim_value = %(verbatim_value)s"

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
db_cursor.execute("SELECT document_id, block, string_agg(word_text, ' ') as block_text, avg(confidence) as block_confidence FROM (SELECT * FROM ocr_entries WHERE confidence > %(confidence)s AND document_id IN (SELECT document_id FROM ocr_documents WHERE project_id = %(project_id)s) order by word) b GROUP BY document_id, block, word_line", {'confidence': settings.confidence, 'project_id': settings.project_id})


ocr_blocks = db_cursor.fetchall()
logger1.debug(db_cursor.query.decode("utf-8"))





#Iterate for dates
from_year = 1800



#Iterate blocks
for ocr_block in ocr_blocks:
    logger1.info("Block text: {}".format(ocr_block['block_text']))
    #Identify year
    #This year
    today = date.today()
    cur_year = today.strftime("%Y")
    interpreted_value = ""
    alpha_block = re.sub(r'\W+ ,-/', '', ocr_block['block_text']).strip()
    if len(alpha_block) < 5 or len(re.sub(r'\W+', '', ocr_block['block_text']).strip()) < 5:
        #Too short to parse
        alpha_block_yr = re.sub(r'\W+', '', alpha_block).strip()
        if len(alpha_block_yr) == 4:
            #Year
            try:
                for y in range(from_year, int(cur_year)):
                    if int(alpha_block_yr) == y:
                        interpreted_value = "{}".format(alpha_block_yr)
                        db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'verbatim_date', 'data_format': 'Date (year)', 'interpreted_value': interpreted_value, 'verbatim_value': alpha_block, 'data_source': '', 'match_score': 0})
                        logger1.info('Date (year): {}'.format(interpreted_value))
                        break
            except:
                continue
        else:
            continue
    if interpreted_value != "":
        continue
    if alpha_block in settings.collector_strings:
        #Codeword that indicates this is a collector
        continue
    if "No." in alpha_block:
        #Codeword that indicates this is not a date
        continue
    if alpha_block[-1] == "\'":
        #Ends in quote, so it should be an elevation, not a date
        elev_text = alpha_block.split(' ')
        elev_text = elev_text[len(elev_text) - 1].strip()
        interpreted_value = "{}\'".format(re.findall(r'\d+', elev_text))
        db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'elevation', 'data_format': 'elevation', 'interpreted_value': interpreted_value, 'verbatim_value': elev_text, 'data_source': '', 'match_score': 0})
        logger1.info('Elevation: {}'.format(interpreted_value))
        continue
    if alpha_block[-1] == "m" or alpha_block[-1] == "masl":
        #Ends in quote, so it should be an elevation, not a date
        elev_text = alpha_block.split(' ')
        elev_text = elev_text[len(elev_text) - 1].strip()
        interpreted_value = "{}m".format(re.findall(r'\d+', elev_text))
        db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'elevation', 'data_format': 'elevation', 'interpreted_value': interpreted_value, 'verbatim_value': elev_text, 'data_source': '', 'match_score': 0})
        logger1.info('Elevation: {}'.format(interpreted_value))
        continue
    for i in range(from_year, int(cur_year)):
        if interpreted_value == "":
            if str(i) in ocr_block['block_text']:
                #Check if can directly parse the date
                for d_format in ['DMY', 'YMD', 'MDY']:
                    if dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']}) != None:
                        this_date = dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']})
                        interpreted_value = this_date.strftime("%Y-%m-%d")
                        verbatim_value = alpha_block
                        continue
            #Check if there is a month in roman numerals
            roman_month = {"I": "Jan", "II": "Feb", "III": "Mar", "IV": "Apr", "V": "May", "VI": "Jun", "VII": "Jul", "VIII": "Aug", "IX": "Sep", "X": "Oct", "XI": "Nov", "X11": "Dec"}
            for m in roman_month:
                if m in ocr_block['block_text']:
                    #Possible year and month found
                    this_text = ocr_block['block_text'].replace(m, roman_month[m])
                    alpha_block = re.sub(r'\W+ ,-/', '', this_text).strip()
                    #Try to parse date
                    for d_format in ['DMY', 'YMD', 'MDY']:
                        if dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']}) != None:
                            this_date = dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']})
                            interpreted_value = this_date.strftime("%Y-%m-%d")
                            verbatim_value = alpha_block
                            continue
    if interpreted_value == "":
        for i in range(99):
            if interpreted_value == "":
                if i < 10:
                    i = "0{}".format(i)
                else:
                    i = str(i)
                if "-{}".format(i) in ocr_block['block_text'] or "\'{}".format(i) in ocr_block['block_text'] or " {}".format(i) in ocr_block['block_text'] or "/{}".format(i) in ocr_block['block_text']:
                    #Check if can directly parse the date
                    alpha_block = re.sub(r'\W+ ,-/', '', ocr_block['block_text']).strip()
                    for d_format in ['DMY', 'YMD', 'MDY']:
                        if dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']}) != None:
                            this_date = dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']})
                            if int(this_date.strftime("%Y")) > int(cur_year):
                                #If it interprets year 64 as 2064
                                this_date_year = int(this_date.strftime("%Y")) - 1000
                            else:
                                this_date_year = this_date.strftime("%Y")
                            interpreted_value = "{}-{}".format(this_date_year, this_date.strftime("%m-%d"))
                            verbatim_value = alpha_block
                            break
                    #Check if there is a month in roman numerals
                    roman_month = {"I": "Jan", "II": "Feb", "III": "Mar", "IV": "Apr", "V": "May", "VI": "Jun", "VII": "Jul", "VIII": "Aug", "IX": "Sep", "X": "Oct", "XI": "Nov", "X11": "Dec"}
                    for m in roman_month:
                        if m in ocr_block['block_text']:
                            #Possible year and month found
                            this_text = ocr_block['block_text'].replace(m, roman_month[m])
                            alpha_block = re.sub(r'\W+ ,-/', '', this_text).strip()
                            #Try to parse date
                            for d_format in ['DMY', 'YMD', 'MDY']:
                                if dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']}) != None:
                                    this_date = dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']})
                                    if int(this_date.strftime("%Y")) > int(cur_year):
                                        #If it interprets year 64 as 2064
                                        this_date_year = int(this_date.strftime("%Y")) - 1000
                                    else:
                                        this_date_year = this_date.strftime("%Y")
                                    interpreted_value = "{}-{}".format(this_date_year, this_date.strftime("%m-%d"))
                                    verbatim_value = alpha_block
                                    break
    if interpreted_value != "":
        #Remove interpreted values in other fields
        db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'verbatim_date', 'data_format': 'Date (Y-M-D)', 'interpreted_value': interpreted_value, 'verbatim_value': verbatim_value, 'data_source': '', 'match_score': 0})
        logger1.info('Date: {}'.format(interpreted_value))
        continue




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
#Get counties, state
db_cursor2.execute("SELECT name_2 || ' Co., ' || name_1 as name, 'locality:county' as name_type, uid FROM gadm2 WHERE name_0 = 'United States' AND type_2 = 'County'")
counties = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))
counties_list = pd.DataFrame(counties)
db_cursor2.execute("SELECT name_2 || ' ' || type_2 || ', ' || name_1 as name, 'locality:county' as name_type, uid FROM gadm2 WHERE name_0 = 'United States'")
counties = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))
counties_list = counties_list.append(counties, ignore_index=True)
db_cursor2.execute("SELECT DISTINCT g.name_2 || ', ' || s.abbreviation as name, 'locality:county' as name_type, g.uid FROM gadm2 g, us_state_abbreviations s WHERE g.name_1 = s.state AND g.name_0 = 'United States'")
counties = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))
counties_list = counties_list.append(counties, ignore_index=True)
db_cursor2.execute("SELECT DISTINCT g.name_2 || ' Co., ' || s.abbreviation as name, 'locality:county' as name_type, g.uid FROM gadm2 g, us_state_abbreviations s WHERE g.name_1 = s.state AND g.name_0 = 'United States'")
counties = db_cursor2.fetchall()
logger1.debug(db_cursor2.query.decode("utf-8"))
counties_list = counties_list.append(counties, ignore_index=True)



#Close GIS database connection
db_cursor2.close()
conn2.close()



#Iterate for localities
for ocr_block in ocr_blocks:
    logger1.info("Block text: {}".format(ocr_block['block_text']))
    #Countries
    localities_match = pd.DataFrame(counties_list)
    localities_match = localities_match.append(pd.DataFrame(states), ignore_index=True).append(pd.DataFrame(sub_states), ignore_index=True).append(pd.DataFrame(countries), ignore_index=True)
    localities_match['score'] = localities_match.apply(lambda row : fuzz.token_sort_ratio(ocr_block['block_text'], row['name']), axis = 1)
    top_row = localities_match.sort_values(by = 'score', ascending = False)[0:1].copy()
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
        db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'verbatim_locality', 'data_format': top_row.iloc[0]['name_type'], 'interpreted_value': interpreted_value, 'verbatim_value': block_df_top_row.iloc[0]['text'], 'data_source': '', 'match_score': 0})
        logger1.debug(db_cursor.query.decode("utf-8"))
        logger1.info('Locality: {} (uid: gadm0:{}, token_set_ratio: {})'.format(interpreted_value, top_row.iloc[0]['uid'], top_row.iloc[0]['score']))
    


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
        db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'taxonomy', 'data_format': top_row.iloc[0]['name_type'], 'interpreted_value': interpreted_value, 'verbatim_value': "", 'data_source': '', 'match_score': 0})
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
            coll2 = [col.replace(interpreted_value, '') for col in settings.collector_strings]
            if interpreted_value in coll2:
                continue
            else:
                if len(interpreted_value) > 3:
                    db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'collector', 'data_format': 'collector', 'interpreted_value': interpreted_value, 'verbatim_value': ocr_block['block_text'], 'data_source': '', 'match_score': 0})
                    logger1.info('Collector ({}): {}'.format(coll, interpreted_value))
                    break



#Assign by similarity
#Get entries with confidence value over the threshold from settings
db_cursor.execute("SELECT document_id, block, string_agg(word_text, ' ') as block_text, avg(confidence) as block_confidence FROM (SELECT * FROM ocr_entries WHERE confidence > %(confidence)s AND document_id IN (SELECT document_id FROM ocr_documents WHERE project_id = %(project_id)s) order by word) b GROUP BY document_id, block, word_line", {'confidence': settings.confidence, 'project_id': settings.project_id})

ocr_blocks = db_cursor.fetchall()
logger1.debug(db_cursor.query.decode("utf-8"))


db_cursor.execute("SELECT distinct data_type FROM ocr_interpreted_blocks WHERE document_id IN (SELECT document_id FROM ocr_documents WHERE project_id = %(project_id)s)", {'project_id': settings.project_id})
data_types = db_cursor.fetchall()
logger1.debug(db_cursor.query.decode("utf-8"))

similarity_query = "SELECT data_type, data_format, interpreted_value, word_similarity(interpreted_value, %(text_block)s) as sml FROM ocr_interpreted_blocks ORDER BY sml DESC LIMIT 1"

#Iterate data_types
for data_type in data_types:
    #Iterate blocks
    for ocr_block in ocr_blocks:
        logger1.info("Block text: {}".format(ocr_block['block_text']))
        alpha_block = re.sub(r'\W+ ,-/', '', ocr_block['block_text']).strip()
        db_cursor.execute("SELECT count(*) as no_records FROM ocr_interpreted_blocks WHERE document_id = %(document_id)s AND block_id = %(block_id)s AND data_type = %(data_type)s", {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': data_type['data_type']})
        no_records = db_cursor.fetchone()
        logger1.debug(db_cursor.query.decode("utf-8"))
        if no_records['no_records'] == 0:
            if len(alpha_block) < 5 or len(re.sub(r'\W+', '', ocr_block['block_text']).strip()) < 5:
                #Too short
                continue
            else:
                #Nothing found, try matching with known data_types
                db_cursor.execute(similarity_query, {'text_block': ocr_block['block_text']})
                record = db_cursor.fetchone()
                logger1.debug(db_cursor.query.decode("utf-8"))
                if record['sml'] > 0.8:
                    db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': record['data_type'], 'data_format': record['data_format'], 'interpreted_value': ocr_block['block_text'], 'verbatim_value': ocr_block['block_text'], 'data_source': 'similarity', 'match_score': record['sml']})
                    logger1.debug(db_cursor.query.decode("utf-8"))




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