#!/usr/bin/env python3
# 
# Compare automatic block id using "training" set from human transcription
#

import io, json, sys, os, psycopg2, logging, subprocess, swifter, re, dateparser
from glob import glob
from pathlib import Path
from psycopg2.extras import RealDictCursor
from time import localtime, strftime
from fuzzywuzzy import fuzz
import pandas as pd
from datetime import date
from tqdm import tqdm
import numpy as np
from multiprocessing import Pool

ver = "0.2.1"

##Import settings from settings.py file
import settings



############################################
# Logging
############################################
if not os.path.exists('logs'):
    os.makedirs('logs')

current_time = strftime("%Y%m%d%H%M%S", localtime())
logfile_name = 'comparison_{}.log'.format(current_time)
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
logger1 = logging.getLogger("compare")
logging.getLogger('compare').addHandler(console)
logger1.info("compare version {}".format(ver))
############################################


#OCR Database
conn = psycopg2.connect(host = settings.ocr_host, database = settings.ocr_db, user = settings.ocr_user, password = settings.ocr_password, connect_timeout = 60)
conn.autocommit = True
db_cursor = conn.cursor(cursor_factory=RealDictCursor)



query_transcription = """
            SELECT 
                DISTINCT collector as data,
                'collector' as field
            FROM
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') IN (
                    SELECT 
                        filename
                    FROM 
                        ocr_auto_sample
                    WHERE 
                        reference_size = %(refsize)s AND
                        ref_or_test = 'ref'
                )

            UNION

            SELECT 
                DISTINCT verbatim_date as data,
                'verbatim_date' as field
            FROM
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') IN (
                    SELECT 
                        filename
                    FROM 
                        ocr_auto_sample
                    WHERE 
                        reference_size = %(refsize)s AND
                        ref_or_test = 'ref'
                )

            UNION

            SELECT 
                DISTINCT verbatim_locality as data,
                'verbatim_locality' as field
            FROM
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') IN (
                    SELECT 
                        filename
                    FROM 
                        ocr_auto_sample
                    WHERE 
                        reference_size = %(refsize)s AND
                        ref_or_test = 'ref'
                )

            UNION

            SELECT 
                DISTINCT country as data,
                'country' as field
            FROM
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') IN (
                    SELECT 
                        filename
                    FROM 
                        ocr_auto_sample
                    WHERE 
                        reference_size = %(refsize)s AND
                        ref_or_test = 'ref'
                )

            UNION

            SELECT 
                DISTINCT state_territory as data,
                'state_territory' as field
            FROM
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') IN (
                    SELECT 
                        filename
                    FROM 
                        ocr_auto_sample
                    WHERE 
                        reference_size = %(refsize)s AND
                        ref_or_test = 'ref'
                )

            UNION

            SELECT 
                DISTINCT district_county as data,
                'district_county' as field
            FROM
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') IN (
                    SELECT 
                        filename
                    FROM 
                        ocr_auto_sample
                    WHERE 
                        reference_size = %(refsize)s AND
                        ref_or_test = 'ref'
                )

            UNION

            SELECT 
                DISTINCT precise_locality as data,
                'precise_locality' as field
            FROM
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') IN (
                    SELECT 
                        filename
                    FROM 
                        ocr_auto_sample
                    WHERE 
                        reference_size = %(refsize)s AND
                        ref_or_test = 'ref'
                )

            UNION

            SELECT 
                DISTINCT elevation as data,
                'elevation' as field
            FROM
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') IN (
                    SELECT 
                        filename
                    FROM 
                        ocr_auto_sample
                    WHERE 
                        reference_size = %(refsize)s AND
                        ref_or_test = 'ref'
                )
        """



query_test = """
            SELECT
                b.document_id, 
                replace(d.filename, '.jpg', '') as filename,
                b.block::text, 
                string_agg(a.word_text, ' ') as block_text
            FROM
                ocr_blocks b,
                ocr_documents d,
                (
                SELECT 
                    document_id, 
                    block,
                    word_line,
                    word,
                    word_text
                FROM 
                    ocr_entries
                WHERE
                    document_id IN
                        (
                            SELECT document_id FROM ocr_documents WHERE replace(filename, '.jpg', '') IN 
                                (
                                    SELECT
                                        filename
                                    FROM
                                        ocr_auto_sample
                                    WHERE 
                                        ref_or_test = 'test' AND
                                        reference_size = %(refsize)s
                                )
                        )
                    ORDER BY 
                        page, block, word_line, word
                ) a
            WHERE
                d.document_id = b.document_id AND
                a.document_id = b.document_id AND
                a.block = b.block AND
                b.confidence >= 0.85
            GROUP BY 
                b.document_id, 
                b.block,
                d.filename
        """



# db_cursor.execute("DELETE FROM ocr_transcription_ento_auto")
# db_cursor.execute("VACUUM ocr_transcription_ento_auto")


# #for refsize in ['0.05', '0.1', '0.2', '0.3', '0.4', '0.5']:
# for refsize in ['0.05', '0.1', '0.2']:
#     print(refsize)
#     db_cursor.execute(query_transcription, {'refsize': refsize})
#     logger1.debug(db_cursor.query.decode("utf-8"))
#     transcription_data = pd.DataFrame(db_cursor.fetchall())
#     db_cursor.execute(query_test, {'refsize': refsize})
#     logger1.debug(db_cursor.query.decode("utf-8"))
#     test_data = pd.DataFrame(db_cursor.fetchall())
#     for data_type in transcription_data['field'].unique():
#         print("Processing {}...\n".format(data_type))
#         for index, record in test_data.iterrows():
#             #split string into all possible sequences
#             logger1.debug(record['block_text'])
#             block_text = record['block_text'].split(' ')
#             len_block_text = len(block_text)
#             text_to_test = pd.DataFrame(columns=('document_id', 'block', 'text', 'string_len'))
#             for i in range(len_block_text-1):
#                 for j in range(i+1, len_block_text):
#                     #print(i, j)
#                     this_text = ' '.join(block_text[i:j])
#                     #Get alpha chars only
#                     alpha_block = re.sub(r'\W+ ,-/', '', this_text)
#                     #Add space after periods
#                     alpha_block = ' '.join(alpha_block.split()).replace(' .', '.').replace('.', '. ').strip()
#                     if len(alpha_block) > 3:
#                         #print(this_text)
#                         text_to_test = text_to_test.append([{'document_id':  record['document_id'], 'block': record['block'], 'text': this_text, 'string_len': len(alpha_block)}], ignore_index=True)
#                         logger1.debug(this_text)
#             results_df = pd.DataFrame(columns=('data', 'field', 'text', 'score1', 'score2', 'score3', 'score', 'string_len'))
#             for ind, rcrd in text_to_test.iterrows():
#                 #tr_data = transcription_data.copy()
#                 tr_data = transcription_data[transcription_data.field == data_type].copy()
#                 tr_data['score1'] = tr_data.apply(lambda row : fuzz.partial_ratio(rcrd['text'].lower(), row['data'].lower()), axis = 1)
#                 tr_data['score2'] = tr_data.apply(lambda row : fuzz.ratio(rcrd['text'].lower(), row['data'].lower()), axis = 1)
#                 tr_data['score'] = tr_data.apply(lambda row : row['score1'] + row['score2'], axis = 1).astype(int)
#                 tr_data['score3'] = tr_data.apply(lambda row : fuzz.token_set_ratio(rcrd['text'].lower(), row['data'].lower()), axis = 1)
#                 tr_data['text'] = rcrd['text']
#                 tr_data['string_len'] = rcrd['string_len']
#                 results_df = results_df.append(tr_data)
#             results_df['score'] = pd.to_numeric(results_df['score'])
#             results_df['score3'] = pd.to_numeric(results_df['score3'])
#             results_df['string_len'] = pd.to_numeric(results_df['string_len'])
#             res = results_df.nlargest(1, ['score', 'string_len'])
#             if res.shape[0] > 0:
#                 if res.iloc[0]['score'] > settings.insert_min:
#                     db_cursor.execute("INSERT INTO ocr_transcription_ento_auto (filename, {field}, reference_size) VALUES (%(document_id)s, %(text)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s".format(field = res.iloc[0]['field']), {'document_id': record['filename'], 'text': res.iloc[0]['text'], 'reference_size': refsize})
#                     logger1.info(db_cursor.query.decode("utf-8"))
#                 else:
#                     #Check for token_set_ratio
#                     max_score = results_df['score3'].max()
#                     res_top = results_df[results_df.score3 == max_score]
#                     #Choose string with the least number of words that has the max score
#                     res = results_df.nsmallest(1, 'string_len')
#                     if res.shape[0] > 0:
#                         if res.iloc[0]['score3'] > settings.token_set_ratio_min:
#                             db_cursor.execute("INSERT INTO ocr_transcription_ento_auto (filename, {field}, reference_size) VALUES (%(document_id)s, %(text)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s".format(field = res.iloc[0]['field']), {'document_id': record['filename'], 'text': res.iloc[0]['text'], 'reference_size': refsize})
#                             logger1.info(db_cursor.query.decode("utf-8"))



# #Cleanup
# for refsize in ['0.05', '0.1', '0.2']:
#     db_cursor.execute(query_transcription, {'refsize': refsize})
#     transcription_data = pd.DataFrame(db_cursor.fetchall())
# for data_type in transcription_data['field'].unique():
#     db_cursor.execute("UPDATE ocr_transcription_ento_auto SET {field} = REPLACE({field}, '. , ', '., ')".format(field = data_type))
#     logger1.info(db_cursor.query.decode("utf-8"))



##################
#GIS database
conn2 = psycopg2.connect(host = settings.gis_host, database = settings.gis_db, user = settings.gis_user, password = settings.gis_password, connect_timeout = 60)
db_cursor2 = conn2.cursor(cursor_factory=RealDictCursor)




# #Get state/provinces from GIS database
# db_cursor2.execute("SELECT name_1 as name, name_0 as country, 'locality:state' as name_type, uid FROM gadm1")
# states = pd.DataFrame(db_cursor2.fetchall())
# logger1.debug(db_cursor2.query.decode("utf-8"))
# #Get countries from GIS database
db_cursor2.execute("SELECT name_0 as name, 'locality:country' as name_type, uid FROM gadm0")
countries = pd.DataFrame(db_cursor2.fetchall())
logger1.debug(db_cursor2.query.decode("utf-8"))
# #Get counties, state
# db_cursor2.execute("SELECT name_2 || ' Co., ' || name_1 as name, 'locality:county' as name_type, uid FROM gadm2 WHERE name_0 = 'United States' AND type_2 = 'County'")
# counties = pd.DataFrame(db_cursor2.fetchall())
# logger1.debug(db_cursor2.query.decode("utf-8"))
# counties_list = pd.DataFrame(counties)
# db_cursor2.execute("SELECT name_2 || ' ' || type_2 || ', ' || name_1 as name, 'locality:county' as name_type, uid FROM gadm2 WHERE name_0 = 'United States'")
# counties = pd.DataFrame(db_cursor2.fetchall())
# logger1.debug(db_cursor2.query.decode("utf-8"))
# counties_list = counties_list.append(counties, ignore_index=True)
# db_cursor2.execute("SELECT DISTINCT g.name_2 || ', ' || s.abbreviation as name, 'locality:county' as name_type, g.uid FROM gadm2 g, us_state_abbreviations s WHERE g.name_1 = s.state AND g.name_0 = 'United States'")
# counties = pd.DataFrame(db_cursor2.fetchall())
# logger1.debug(db_cursor2.query.decode("utf-8"))
# counties_list = counties_list.append(counties, ignore_index=True)
# db_cursor2.execute("SELECT DISTINCT g.name_2 || ' Co., ' || s.abbreviation as name, 'locality:county' as name_type, g.name_1 AS state, g.name_0 as country, g.uid FROM gadm2 g, us_state_abbreviations s WHERE g.name_1 = s.state AND g.name_0 = 'United States'")
# counties = pd.DataFrame(db_cursor2.fetchall())
# logger1.debug(db_cursor2.query.decode("utf-8"))
# counties_list = counties_list.append(counties, ignore_index=True)


# #Close GIS database connection
db_cursor2.close()
conn2.close()
# ##################


# db_cursor.execute("DROP TABLE ocr_transcription_ento_auto_geo")
# db_cursor.execute("CREATE TABLE ocr_transcription_ento_auto_geo AS SELECT * FROM ocr_transcription_ento_auto")
# db_cursor.execute("ALTER TABLE ocr_transcription_ento_auto_geo ADD CONSTRAINT ocr_tra_ento_auto_geo_c UNIQUE (filename, reference_size)")



# #country
query_country = """
            SELECT
                b.document_id, 
                replace(d.filename, '.jpg', '') as filename,
                b.block::text, 
                string_agg(a.word_text, ' ') as block_text
            FROM
                ocr_blocks b,
                ocr_documents d,
                (
                SELECT 
                    document_id, 
                    block,
                    word_line,
                    word,
                    word_text
                FROM 
                    ocr_entries
                WHERE
                    document_id IN
                        (
                            SELECT document_id FROM ocr_documents WHERE replace(filename, '.jpg', '') IN 
                                (
                                    SELECT
                                        filename
                                    FROM
                                        ocr_auto_sample
                                    WHERE 
                                        ref_or_test = 'test' AND
                                        reference_size = %(refsize)s
                                )
                        ) 
                    ORDER BY 
                        page, block, word_line, word
                ) a
            WHERE
                d.document_id = b.document_id AND
                a.document_id = b.document_id AND
                a.block = b.block AND
                b.confidence >= 0.85
            GROUP BY 
                b.document_id, 
                b.block,
                d.filename
        """



# query_state = """
#             SELECT
#                 b.document_id, 
#                 replace(d.filename, '.jpg', '') as filename,
#                 b.block::text, 
#                 string_agg(a.word_text, ' ') as block_text
#             FROM
#                 ocr_blocks b,
#                 ocr_documents d,
#                 (
#                 SELECT 
#                     document_id, 
#                     block,
#                     word_line,
#                     word,
#                     word_text
#                 FROM 
#                     ocr_entries
#                 WHERE
#                     document_id IN
#                         (
#                             SELECT document_id FROM ocr_documents WHERE replace(filename, '.jpg', '') IN 
#                                 (
#                                     SELECT
#                                         filename
#                                     FROM
#                                         ocr_auto_sample
#                                     WHERE 
#                                         ref_or_test = 'test' AND
#                                         reference_size = %(refsize)s
#                                 )
#                         ) 
#                     ORDER BY 
#                         page, block, word_line, word
#                 ) a
#             WHERE
#                 d.document_id = b.document_id AND
#                 a.document_id = b.document_id AND
#                 a.block = b.block AND
#                 b.confidence >= 0.85
#             GROUP BY 
#                 b.document_id, 
#                 b.block,
#                 d.filename
#         """



# query_county = """
#             SELECT
#                 b.document_id, 
#                 replace(d.filename, '.jpg', '') as filename,
#                 b.block::text, 
#                 string_agg(a.word_text, ' ') as block_text
#             FROM
#                 ocr_blocks b,
#                 ocr_documents d,
#                 (
#                 SELECT 
#                     document_id, 
#                     block,
#                     word_line,
#                     word,
#                     word_text
#                 FROM 
#                     ocr_entries
#                 WHERE
#                     document_id IN
#                         (
#                             SELECT document_id FROM ocr_documents WHERE replace(filename, '.jpg', '') IN 
#                                 (
#                                     SELECT
#                                         filename
#                                     FROM
#                                         ocr_auto_sample
#                                     WHERE 
#                                         ref_or_test = 'test' AND
#                                         reference_size = %(refsize)s
#                                 )
#                         ) 
#                     ORDER BY 
#                         page, block, word_line, word
#                 ) a
#             WHERE
#                 d.document_id = b.document_id AND
#                 a.document_id = b.document_id AND
#                 a.block = b.block AND
#                 b.confidence >= 0.85
#             GROUP BY 
#                 b.document_id, 
#                 b.block,
#                 d.filename
#         """



def match_country(this_record):
    try:
        record = this_record.iloc[0]
    except:
        return
    logger1.debug(record['block_text'])
    block_text = record['block_text'].split(' ')
    len_block_text = len(block_text)
    text_to_test = pd.DataFrame(columns=('document_id', 'block', 'text', 'string_len'))
    for i in range(len_block_text-1):
        for j in range(i+1, len_block_text):
            #print(i, j)
            #this_text = ' '.join(block_text[i:j])
            this_text = ' '.join(map(str, block_text[i:j]))
            alpha_block = re.sub(r'\W+ ,-/', '', this_text)
            #Add space after periods
            alpha_block = ' '.join(alpha_block.split()).replace(' .', '.').replace('.', '. ').strip()
            if len(alpha_block) > 3:
                #print(this_text)
                text_to_test = text_to_test.append([{'document_id':  record['document_id'], 'block': record['block'], 'text': this_text, 'string_len': len(alpha_block)}], ignore_index=True)
                logger1.debug(this_text)
    results_df = pd.DataFrame(columns=('text', 'score1', 'score2', 'score3', 'score', 'string_len'))
    results_df['score2'] = pd.to_numeric(results_df['score2'])
    results_df['string_len'] = pd.to_numeric(results_df['string_len'])
    for idx, rcrd in text_to_test.iterrows():
        tr_data = countries[['name', 'uid']].copy()
        tr_data['score2'] = tr_data.apply(lambda row : fuzz.ratio(rcrd['text'].lower(), row['name'].lower()), axis = 1)
        tr_data['text'] = rcrd['text']
        tr_data['string_len'] = rcrd['string_len']
        results_df = results_df.append(tr_data)
    res = results_df.nlargest(1, ['score2', 'string_len'])
    if res.shape[0] > 0:
        logger1.info(res)
        if res.iloc[0]['score2'] > settings.geo_min:
            db_cursor.execute("INSERT INTO ocr_transcription_ento_auto (filename, {field}, reference_size) VALUES (%(filename)s, %(text)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s".format(field = 'country'), {'filename': record['filename'], 'text': res.iloc[0]['name'], 'reference_size': refsize})
            logger1.info(db_cursor.query.decode("utf-8"))
    return res


#match_country(record)

#Check for country
#for refsize in ['0.05', '0.1', '0.2', '0.3', '0.4', '0.5']:
for refsize in ['0.05', '0.1', '0.2']:
    print(refsize)
    db_cursor.execute(query_country, {'refsize': refsize})
    logger1.debug(db_cursor.query.decode("utf-8"))
    test_data = pd.DataFrame(db_cursor.fetchall())
    df_split = np.array_split(test_data, test_data.size)
    pool = Pool(settings.pool_workers)
    df = pd.concat(pool.map(match_country, df_split))
    pool.close()
    pool.join()
#     # for index, record in test_data.iterrows():
#     #     #split string into all possible sequences
#     #     logger1.info(record['block_text'])
#     #     block_text = record['block_text'].split(' ')
#     #     len_block_text = len(block_text)
#     #     text_to_test = pd.DataFrame(columns=('document_id', 'block', 'text', 'string_len'))
#     #     for i in range(len_block_text-1):
#     #         for j in range(i+1, len_block_text):
#     #             #print(i, j)
#     #             this_text = ' '.join(block_text[i:j])
#     #             alpha_block = re.sub(r'\W+ ,-/', '', this_text).strip()
#     #             if len(alpha_block) > 3:
#     #                 #print(this_text)
#     #                 text_to_test = text_to_test.append([{'document_id':  record['document_id'], 'block': record['block'], 'text': this_text, 'string_len': len(alpha_block)}], ignore_index=True)
#     #                 logger1.debug(this_text)
#     #     results_df = pd.DataFrame(columns=('text', 'score1', 'score2', 'score3', 'score', 'string_len'))
#     #     results_df['score2'] = pd.to_numeric(results_df['score2'])
#     #     results_df['string_len'] = pd.to_numeric(results_df['string_len'])
#     #     for idx, rcrd in text_to_test.iterrows():
#     #         tr_data = countries[['name', 'uid']].copy()
#     #         tqdm.pandas()
#     #         tr_data['score2'] = tr_data.progress_apply(lambda row : fuzz.ratio(rcrd['text'], row['name']), axis = 1)
#     #         tr_data['text'] = rcrd['text']
#     #         tr_data['string_len'] = rcrd['string_len']
#     #         results_df = results_df.append(tr_data)
#     #     res = results_df.nlargest(1, ['score2', 'string_len'])
#     #     if res.shape[0] > 0:
#     #         print(res)
#     #         if res.iloc[0]['score'] > settings.geo_min:
#     #             db_cursor.execute("INSERT INTO ocr_transcription_ento_auto_geo (filename, {field}, reference_size) VALUES (%(document_id)s, %(text)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s".format(field = 'country'), {'document_id': record['filename'], 'text': res.iloc[0]['text'], 'reference_size': refsize})
#     #             logger1.info(db_cursor.query.decode("utf-8"))




# def match_state(record):
#     logger1.debug(record['block_text'])
#     block_text = record['block_text'].str.split(' ').tolist()[0]
#     len_block_text = len(block_text)
#     text_to_test = pd.DataFrame(columns=('document_id', 'block', 'text', 'string_len'))
#     for i in range(len_block_text-1):
#         for j in range(i+1, len_block_text):
#             #print(i, j)
#             #this_text = ' '.join(block_text[i:j])
#             this_text = ' '.join(map(str, block_text[i:j]))
#             alpha_block = re.sub(r'\W+ ,-/', '', this_text)
#             #Add space after periods
#             alpha_block = ' '.join(alpha_block.split()).replace(' .', '.').replace('.', '. ').strip()
#             if len(alpha_block) > 3:
#                 #print(this_text)
#                 text_to_test = text_to_test.append([{'document_id':  record['document_id'], 'block': record['block'], 'text': this_text, 'string_len': len(alpha_block)}], ignore_index=True)
#                 logger1.debug(this_text)
#     results_df = pd.DataFrame(columns=('text', 'score1', 'score2', 'score3', 'score', 'string_len'))
#     results_df['score2'] = pd.to_numeric(results_df['score2'])
#     results_df['string_len'] = pd.to_numeric(results_df['string_len'])
#     for idx, rcrd in text_to_test.iterrows():
#             tr_data = states[['name', 'uid', 'country']].copy()
#             tr_data['score2'] = tr_data.apply(lambda row : fuzz.ratio(rcrd['text'], row['name']), axis = 1)
#             tr_data['text'] = rcrd['text']
#             tr_data['string_len'] = rcrd['string_len']
#             results_df = results_df.append(tr_data)
#     res = results_df.nlargest(1, ['score2', 'string_len'])
#     if res.shape[0] > 0:
#         logger1.info(res)
#         if res.iloc[0]['score'] > settings.geo_min:
#             db_cursor.execute("INSERT INTO ocr_transcription_ento_auto_geo (filename, state_territory, country, reference_size) VALUES (%(document_id)s, %(text)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s", {'document_id': record['filename'], 'text': res.iloc[0]['text'], 'reference_size': refsize, 'country': res.iloc[0]['country']})
#             logger1.info(db_cursor.query.decode("utf-8"))
#     return res




# #Check for state/province
# #for refsize in ['0.05', '0.1', '0.2', '0.3', '0.4', '0.5']:
# for refsize in ['0.05', '0.1', '0.2']:
#     print(refsize)
#     db_cursor.execute(query_state, {'refsize': refsize})
#     logger1.debug(db_cursor.query.decode("utf-8"))
#     test_data = pd.DataFrame(db_cursor.fetchall())
#     df_split = np.array_split(test_data, settings.pool_workers * 4)
#     pool = Pool(settings.pool_workers)
#     df = pd.concat(pool.map(match_state, df_split))
#     pool.close()
#     pool.join()
#     # for index, record in test_data.iterrows():
#     #     #split string into all possible sequences
#     #     logger1.info(record['block_text'])
#     #     block_text = record['block_text'].split(' ')
#     #     len_block_text = len(block_text)
#     #     text_to_test = pd.DataFrame(columns=('document_id', 'block', 'text', 'string_len'))
#     #     for i in range(len_block_text-1):
#     #         for j in range(i+1, len_block_text):
#     #             #print(i, j)
#     #             this_text = ' '.join(block_text[i:j])
#     #             alpha_block = re.sub(r'\W+ ,-/', '', this_text).strip()
#     #             if len(alpha_block) > 3:
#     #                 #print(this_text)
#     #                 text_to_test = text_to_test.append([{'document_id':  record['document_id'], 'block': record['block'], 'text': this_text, 'string_len': len(alpha_block)}], ignore_index=True)
#     #                 logger1.debug(this_text)
#     #     results_df = pd.DataFrame(columns=('text', 'score1', 'score2', 'score3', 'score', 'string_len'))
#     #     results_df['score2'] = pd.to_numeric(results_df['score2'])
#     #     results_df['string_len'] = pd.to_numeric(results_df['string_len'])
#     #     for idx, rcrd in text_to_test.iterrows():
#     #         tr_data = states[['name', 'uid']].copy()
#     #         tqdm.pandas()
#     #         tr_data['score2'] = tr_data.progress_apply(lambda row : fuzz.ratio(rcrd['text'], row['name']), axis = 1)
#     #         tr_data['text'] = rcrd['text']
#     #         tr_data['string_len'] = rcrd['string_len']
#     #         results_df = results_df.append(tr_data)
#     #     res = results_df.nlargest(1, ['score2', 'string_len'])
#     #     if res.shape[0] > 0:
#     #         print(res)
#     #         if res.iloc[0]['score'] > settings.geo_min:
#     #             db_cursor.execute("INSERT INTO ocr_transcription_ento_auto_geo (filename, {field}, reference_size) VALUES (%(document_id)s, %(text)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s".format(field = 'state_territory'), {'document_id': record['filename'], 'text': res.iloc[0]['text'], 'reference_size': refsize})
#     #             logger1.info(db_cursor.query.decode("utf-8"))



# def match_county(record):
#     logger1.debug(record['block_text'])
#     block_text = record['block_text'].str.split(' ').tolist()[0]
#     len_block_text = len(block_text)
#     text_to_test = pd.DataFrame(columns=('document_id', 'block', 'text', 'string_len'))
#     for i in range(len_block_text-1):
#         for j in range(i+1, len_block_text):
#             #print(i, j)
#             #this_text = ' '.join(block_text[i:j])
#             this_text = ' '.join(map(str, block_text[i:j]))
#             alpha_block = re.sub(r'\W+ ,-/', '', this_text)
#             #Add space after periods
#             alpha_block = ' '.join(alpha_block.split()).replace(' .', '.').replace('.', '. ').strip()
#             if len(alpha_block) > 3:
#                 #print(this_text)
#                 text_to_test = text_to_test.append([{'document_id':  record['document_id'], 'block': record['block'], 'text': this_text, 'string_len': len(alpha_block)}], ignore_index=True)
#                 logger1.debug(this_text)
#     results_df = pd.DataFrame(columns=('text', 'score1', 'score2', 'score3', 'score', 'string_len'))
#     results_df['score2'] = pd.to_numeric(results_df['score2'])
#     results_df['string_len'] = pd.to_numeric(results_df['string_len'])
#     for idx, rcrd in text_to_test.iterrows():
#             tr_data = counties_list[['name', 'uid', 'state', 'country']].copy()
#             tr_data['score2'] = tr_data.apply(lambda row : fuzz.ratio(rcrd['text'], row['name']), axis = 1)
#             tr_data['text'] = rcrd['text']
#             tr_data['string_len'] = rcrd['string_len']
#             results_df = results_df.append(tr_data)
#     res = results_df.nlargest(1, ['score2', 'string_len'])
#     if res.shape[0] > 0:
#         logger1.info(res)
#         if res.iloc[0]['score'] > settings.geo_min:
#             db_cursor.execute("INSERT INTO ocr_transcription_ento_auto_geo (filename, district_county, state_territory, country, reference_size) VALUES (%(document_id)s, %(text)s, %(state)s, %(country)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s", {'document_id': record['filename'], 'text': res.iloc[0]['text'], 'reference_size': refsize, 'state': res.iloc[0]['state'], 'country': res.iloc[0]['country']})
#             logger1.info(db_cursor.query.decode("utf-8"))
#     return res


# #Check for Counties_list 
# #for refsize in ['0.05', '0.1', '0.2', '0.3', '0.4', '0.5']:
# for refsize in ['0.05', '0.1', '0.2']:
#     print(refsize)
#     db_cursor.execute(query_county, {'refsize': refsize})
#     logger1.debug(db_cursor.query.decode("utf-8"))
#     test_data = pd.DataFrame(db_cursor.fetchall())
#     df_split = np.array_split(test_data, settings.pool_workers * 4)
#     pool = Pool(settings.pool_workers)
#     df = pd.concat(pool.map(match_state, df_split))
#     pool.close()
#     pool.join()
#     # for index, record in test_data.iterrows():
#     #     #split string into all possible sequences
#     #     logger1.info(record['block_text'])
#     #     block_text = record['block_text'].split(' ')
#     #     len_block_text = len(block_text)
#     #     text_to_test = pd.DataFrame(columns=('document_id', 'block', 'text', 'string_len'))
#     #     for i in range(len_block_text-1):
#     #         for j in range(i+1, len_block_text):
#     #             #print(i, j)
#     #             this_text = ' '.join(block_text[i:j])
#     #             alpha_block = re.sub(r'\W+ ,-/', '', this_text).strip()
#     #             if len(alpha_block) > 3:
#     #                 #print(this_text)
#     #                 text_to_test = text_to_test.append([{'document_id':  record['document_id'], 'block': record['block'], 'text': this_text, 'string_len': len(alpha_block)}], ignore_index=True)
#     #                 logger1.debug(this_text)
#     #     results_df = pd.DataFrame(columns=('text', 'score1', 'score2', 'score3', 'score', 'string_len'))
#     #     results_df['score2'] = pd.to_numeric(results_df['score2'])
#     #     results_df['string_len'] = pd.to_numeric(results_df['string_len'])
#     #     for idx, rcrd in text_to_test.iterrows():
#     #         tr_data = counties_list[['name', 'uid']].copy()
#     #         tqdm.pandas()
#     #         tr_data['score2'] = tr_data.progress_apply(lambda row : fuzz.ratio(rcrd['text'], row['name']), axis = 1)
#     #         tr_data['text'] = rcrd['text']
#     #         tr_data['string_len'] = rcrd['string_len']
#     #         results_df = results_df.append(tr_data)
#     #     res = results_df.nlargest(1, ['score2', 'string_len'])
#     #     if res.shape[0] > 0:
#     #         print(res)
#     #         if res.iloc[0]['score'] > settings.geo_min:
#     #             db_cursor.execute("INSERT INTO ocr_transcription_ento_auto_geo (filename, {field}, reference_size) VALUES (%(document_id)s, %(text)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s".format(field = 'district_county'), {'document_id': record['filename'], 'text': res.iloc[0]['text'], 'reference_size': refsize})
#     #             logger1.info(db_cursor.query.decode("utf-8"))





# #Date
# from_year = 1800

# #Iterate blocks
# for ocr_block in ocr_blocks:
#     logger1.info("Block text: {}".format(ocr_block['block_text']))
#     #Identify year
#     #This year
#     today = date.today()
#     cur_year = today.strftime("%Y")
#     interpreted_value = ""
#     alpha_block = re.sub(r'\W+ ,-/', '', ocr_block['block_text']).strip()
#     if len(alpha_block) < 5 or len(re.sub(r'\W+', '', ocr_block['block_text']).strip()) < 5:
#         #Too short to parse
#         alpha_block_yr = re.sub(r'\W+', '', alpha_block).strip()
#         if len(alpha_block_yr) == 4:
#             #Year
#             try:
#                 for y in range(from_year, int(cur_year)):
#                     if int(alpha_block_yr) == y:
#                         interpreted_value = "{}".format(alpha_block_yr)
#                         db_cursor.execute(insert_q, {'document_id': ocr_block['document_id'], 'block_id': ocr_block['block'], 'data_type': 'verbatim_date', 'data_format': 'Date (year)', 'interpreted_value': interpreted_value, 'verbatim_value': alpha_block, 'data_source': '', 'match_score': 0})
#                         logger1.info('Date (year): {}'.format(interpreted_value))

#     for i in range(from_year, int(cur_year)):
#         if interpreted_value == "":
#             if str(i) in ocr_block['block_text']:
#                 #Check if can directly parse the date
#                 for d_format in ['DMY', 'YMD', 'MDY']:
#                     if dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']}) != None:
#                         this_date = dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']})
#                         interpreted_value = this_date.strftime("%Y-%m-%d")
#                         verbatim_value = alpha_block
#                         continue
#             #Check if there is a month in roman numerals
#             roman_month = {"I": "Jan", "II": "Feb", "III": "Mar", "IV": "Apr", "V": "May", "VI": "Jun", "VII": "Jul", "VIII": "Aug", "IX": "Sep", "X": "Oct", "XI": "Nov", "X11": "Dec"}
#             for m in roman_month:
#                 if m in ocr_block['block_text']:
#                     #Possible year and month found
#                     this_text = ocr_block['block_text'].replace(m, roman_month[m])
#                     alpha_block = re.sub(r'\W+ ,-/', '', this_text).strip()
#                     #Try to parse date
#                     for d_format in ['DMY', 'YMD', 'MDY']:
#                         if dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']}) != None:
#                             this_date = dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']})
#                             interpreted_value = this_date.strftime("%Y-%m-%d")
#                             verbatim_value = alpha_block
#                             continue
#     if interpreted_value == "":
#         for i in range(99):
#             if interpreted_value == "":
#                 if i < 10:
#                     i = "0{}".format(i)
#                 else:
#                     i = str(i)
#                 if "-{}".format(i) in ocr_block['block_text'] or "\'{}".format(i) in ocr_block['block_text'] or " {}".format(i) in ocr_block['block_text'] or "/{}".format(i) in ocr_block['block_text']:
#                     #Check if can directly parse the date
#                     alpha_block = re.sub(r'\W+ ,-/', '', ocr_block['block_text']).strip()
#                     for d_format in ['DMY', 'YMD', 'MDY']:
#                         if dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']}) != None:
#                             this_date = dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']})
#                             if int(this_date.strftime("%Y")) > int(cur_year):
#                                 #If it interprets year 64 as 2064
#                                 this_date_year = int(this_date.strftime("%Y")) - 1000
#                             else:
#                                 this_date_year = this_date.strftime("%Y")
#                             interpreted_value = "{}-{}".format(this_date_year, this_date.strftime("%m-%d"))
#                             verbatim_value = alpha_block
#                             break
#                     #Check if there is a month in roman numerals
#                     roman_month = {"I": "Jan", "II": "Feb", "III": "Mar", "IV": "Apr", "V": "May", "VI": "Jun", "VII": "Jul", "VIII": "Aug", "IX": "Sep", "X": "Oct", "XI": "Nov", "X11": "Dec"}
#                     for m in roman_month:
#                         if m in ocr_block['block_text']:
#                             #Possible year and month found
#                             this_text = ocr_block['block_text'].replace(m, roman_month[m])
#                             alpha_block = re.sub(r'\W+ ,-/', '', this_text).strip()
#                             #Try to parse date
#                             for d_format in ['DMY', 'YMD', 'MDY']:
#                                 if dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']}) != None:
#                                     this_date = dateparser.parse(alpha_block, settings={'DATE_ORDER': d_format, 'PREFER_DATES_FROM': 'past', 'PREFER_DAY_OF_MONTH': 'first', 'REQUIRE_PARTS': ['month', 'year']})
#                                     if int(this_date.strftime("%Y")) > int(cur_year):
#                                         #If it interprets year 64 as 2064
#                                         this_date_year = int(this_date.strftime("%Y")) - 1000
#                                     else:
#                                         this_date_year = this_date.strftime("%Y")
#                                     interpreted_value = "{}-{}".format(this_date_year, this_date.strftime("%m-%d"))
#                                     verbatim_value = alpha_block


# def parse_dates(record):
#     logger1.debug(record['block_text'])
#     block_text = record['block_text'].str.split(' ').tolist()[0]
#     len_block_text = len(block_text)
#     text_to_test = pd.DataFrame(columns=('document_id', 'block', 'text', 'string_len'))
#     for i in range(len_block_text-1):
#         for j in range(i+1, len_block_text):
#             #print(i, j)
#             #this_text = ' '.join(block_text[i:j])
#             this_text = ' '.join(map(str, block_text[i:j]))
#             alpha_block = re.sub(r'\W+ ,-/', '', this_text)
#             #Add space after periods
#             alpha_block = ' '.join(alpha_block.split()).replace(' .', '.').replace('.', '. ').strip()
#             if len(alpha_block) > 3:
#                 #print(this_text)
#                 text_to_test = text_to_test.append([{'document_id':  record['document_id'], 'block': record['block'], 'text': this_text, 'string_len': len(alpha_block)}], ignore_index=True)
#                 logger1.debug(this_text)
#     results_df = pd.DataFrame(columns=('text', 'score1', 'score2', 'score3', 'score', 'string_len'))
#     results_df['score2'] = pd.to_numeric(results_df['score2'])
#     results_df['string_len'] = pd.to_numeric(results_df['string_len'])
#     for idx, rcrd in text_to_test.iterrows():
#             tr_data = counties_list[['name', 'uid', 'state', 'country']].copy()
#             tr_data['score2'] = tr_data.apply(lambda row : fuzz.ratio(rcrd['text'], row['name']), axis = 1)
#             tr_data['text'] = rcrd['text']
#             tr_data['string_len'] = rcrd['string_len']
#             results_df = results_df.append(tr_data)
#     res = results_df.nlargest(1, ['score2', 'string_len'])
#     if res.shape[0] > 0:
#         logger1.info(res)
#         if res.iloc[0]['score'] > settings.geo_min:
#             db_cursor.execute("INSERT INTO ocr_transcription_ento_auto_geo (filename, district_county, state_territory, country, reference_size) VALUES (%(document_id)s, %(text)s, %(state)s, %(country)s, %(reference_size)s) ON CONFLICT (filename, reference_size) DO UPDATE SET {field} = %(text)s", {'document_id': record['filename'], 'text': res.iloc[0]['text'], 'reference_size': refsize, 'state': res.iloc[0]['state'], 'country': res.iloc[0]['country']})
#             logger1.info(db_cursor.query.decode("utf-8"))
#     return res


# #Check for Counties_list 
# for refsize in ['0.05', '0.1', '0.2']:
#     print(refsize)
#     db_cursor.execute(query_county, {'refsize': refsize})
#     logger1.debug(db_cursor.query.decode("utf-8"))
#     test_data = pd.DataFrame(db_cursor.fetchall())
#     df_split = np.array_split(test_data, settings.pool_workers * 4)
#     pool = Pool(settings.pool_workers)
#     df = pd.concat(pool.map(parse_dates, df_split))
#     pool.close()
#     pool.join()







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