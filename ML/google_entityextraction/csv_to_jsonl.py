#!/usr/bin/env python3

# Prepare data from an Excel file to jsonl files
#  as required by entity detection in Google Cloud
# https://cloud.google.com/natural-language/automl/docs/quickstart
# https://cloud.google.com/natural-language/automl/docs/prepare

import pandas as pd
import edan
import settings
import os
import shutil

# os.remove('list.csv')
# shutil.rmtree('training_data')

# os.mkdir('training_data')

data = pd.read_excel('Alembo_import_set79_simplified.xlsx')

template_pre = "{\"annotations\":["

template_entry = "{{\"text_extraction\": {{\"text_segment\": {{\"end_offset\": {end_offset}, \"start_offset\": {start_offset}}}}},\"display_name\": \"{display_name}\"}}"

template_post = "],\"text_snippet\":{{\"content\": \"{content}\"}}}}"


#Write data back to file, as tsv
data.to_csv("Alembo_import_set79_simplified.csv", sep=" ", encoding="utf-8", header = False)

file1 = open('Alembo_import_set79_simplified.csv', 'r', encoding="utf-8")
Lines = file1.readlines()

i = 0

for line in Lines:
    # if i > 11000:
    #     break
    print(str(i))
    if os.path.isfile('training_data/data_{}.jsonl'.format(i)):
        i += 1
        continue
    this_line = line.strip().replace("\"", "")
    jsonl_string = template_pre

    #Edan info
    print("\n Barcode: {}".format(data.iloc[i][1]))
    sciname = ""
    edan_info = edan.searchEDAN("{}".format(data.iloc[i][1]), settings.AppID, settings.AppKey)
    if edan_info['rowCount']==1:
        print("  Sciname: {}".format(edan_info['rows'][0]['title']))
        # Sciname
        field_label = "sciname"
        sciname = edan_info['rows'][0]['title']
        field_from = len(this_line.replace("\"", "")) + 1
        field_to = field_from + len(sciname)
        entry = template_entry.format(end_offset=field_to, start_offset=field_from, display_name=field_label)
        jsonl_string = jsonl_string + entry + ","

    # Collectors
    col = 0
    field_label = "collectors"
    if pd.isnull(data.iloc[i][col]) == False:
        data_block_len = len(data.iloc[i][col])
        field_from = this_line.find(data.iloc[i][col])
        if field_from > 0:
            field_to = field_from + data_block_len
            entry = template_entry.format(end_offset=field_to, start_offset=field_from, display_name=field_label)
            jsonl_string = jsonl_string + entry + ","

    # Collectors2
    col = 2
    field_label = "collectors"
    if pd.isnull(data.iloc[i][col]) == False:
        data_block_len = len(data.iloc[i][col])
        field_from = this_line.find(data.iloc[i][col])
        if field_from > 0:
            field_to = field_from + data_block_len
            entry = template_entry.format(end_offset=field_to, start_offset=field_from, display_name=field_label)
            jsonl_string = jsonl_string + entry + ","

    # Date
    col = 14
    field_label = "date"
    if pd.isnull(data.iloc[i][col]) == False:
        data_block_len = len(data.iloc[i][col])
        field_from = this_line.find(data.iloc[i][col])
        if field_from > 0:
            field_to = field_from + data_block_len
            entry = template_entry.format(end_offset=field_to, start_offset=field_from, display_name=field_label)
            jsonl_string = jsonl_string + entry + ","

    # country
    col = 15
    field_label = "country"
    if pd.isnull(data.iloc[i][col]) == False:
        data_block_len = len(data.iloc[i][col])
        field_from = this_line.find(data.iloc[i][col])
        if field_from > 0:
            field_to = field_from + data_block_len
            entry = template_entry.format(end_offset=field_to, start_offset=field_from, display_name=field_label)
            jsonl_string = jsonl_string + entry + ","

    # stateprovince
    col = 16
    field_label = "stateprovince"
    if pd.isnull(data.iloc[i][col]) == False:
        data_block_len = len(data.iloc[i][col])
        field_from = this_line.find(data.iloc[i][col])
        if field_from > 0:
            field_to = field_from + data_block_len
            entry = template_entry.format(end_offset=field_to, start_offset=field_from, display_name=field_label)
            jsonl_string = jsonl_string + entry + ","

    # precise_locality
    col = 17
    field_label = "precise_locality"
    if pd.isnull(data.iloc[i][col]) == False:
        data_block_len = len(data.iloc[i][col])
        field_from = this_line.find(data.iloc[i][col])
        if field_from > 0:
            field_to = field_from + data_block_len
            entry = template_entry.format(end_offset=field_to, start_offset=field_from, display_name=field_label)
            jsonl_string = jsonl_string + entry + ","

    # Remove trailing comma
    if jsonl_string[-1] == ",":
        jsonl_string = jsonl_string[:-1]

    jsonl_string = jsonl_string + template_post.format(content=this_line.replace("\"", "") + " " + sciname)

    output_file = open('training_data/data_{}.jsonl'.format(i), 'w', encoding="utf-8")
    # Writing a string to file
    output_file.write(jsonl_string)
    output_file.close()
    output_file = open('list.csv', 'a', encoding="utf-8")
    output_file.write(",gs://botany_test/training_data/data_{}.jsonl\n".format(i))
    output_file.close()
    i += 1
