#!/usr/bin/env python3
#
# Google Document AI based on their reference docs at:
#  [to replace]
#  https://github.com/googleapis/python-vision/blob/HEAD/samples/snippets/detect/detect.py
#
# To run: python3 run_docai.py <path to tif files>
#

import glob
import os
import re
import sys
# import psycopg2
# from PIL import ImagePath
from pathlib import Path

# Load Google Cloud
from google.cloud import documentai_v1beta3 as documentai
from google.cloud.documentai_v1beta3 import Document
# from pyfiglet import Figlet

# Import project settings
import settings

# Script variables
script_title = "Google Document AI Data Extraction"
subtitle = "Digitization Program Office\nOffice of the Chief Information Officer\nSmithsonian Institution\nhttps://dpo.si.edu"
ver = "0.1"
vercheck = "https://raw.githubusercontent.com/Smithsonian/DPO_OCR/master/ML/google_documentai/toolversion.txt"
repo = "https://github.com/Smithsonian/DPO_OCR/"
lic = "Available under the Apache 2.0 License"


# Check for updates to the script
# try:
#     with urllib.request.urlopen(vercheck) as response:
#         current_ver = response.read()
#     cur_ver = current_ver.decode('ascii').replace('\n', '')
#     if cur_ver != ver:
#         msg_text = "{subtitle}\n\n{repo}\n{lic}\n\nver. {ver}\nThis version is outdated. Current version is {cur_ver}.\nPlease download the updated version at: {repo}"
#     else:
#         msg_text = "{subtitle}\n\n{repo}\n{lic}\n\nver. {ver}"
# except:
#     msg_text = "{subtitle}\n\n{repo}\n{lic}\n\nver. {ver}"
#     cur_ver = ver

# f = Figlet(font='slant')
# print("\n")
# print(f.renderText(script_title))
# # print(script_title)
# print(msg_text.format(subtitle=subtitle, ver=ver, repo=repo, lic=lic, cur_ver=cur_ver))


if len(sys.argv) != 2:
    print("Error: arguments missing. Usage:\n\n ./run_docai.py <folder with tifs>")
    sys.exit(1)
else:
    if not os.path.isdir(sys.argv[1]):
        print("Error: path to TIF files does not exists.")
        sys.exit(1)
    else:
        path = sys.argv[1]


# Check if there is a creds.json file
if not os.path.isfile("{}/creds.json".format(os.getcwd())):
    print("Error: creds.json missing.")
    sys.exit(1)
else:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "{}/creds.json".format(os.getcwd())


# Load google vision
opts = {}
client = documentai.DocumentProcessorServiceClient(client_options=opts)

name = f"projects/{settings.project_id}/locations/{settings.location}/processors/{settings.processor_id}"


# https://github.com/googleapis/python-documentai/blob/master/samples/snippets/parse_form_v1beta2.py
def _get_text(el):
    """Convert text offset indexes into text snippets."""
    response = ""
    # If a text segment spans several lines, it will
    # be stored in different text segments.
    for segment in el.text_anchor.text_segments:
        start_index = segment.start_index
        end_index = segment.end_index
        response += document.text[start_index:end_index]
    return response


# Get images
list_of_files = glob.glob('{}/*.tif'.format(path))
print("\n\nFound {} files.".format(len(list_of_files)))


# Run each file
for filename in list_of_files:
    file_stem = Path(filename).stem
    # Open file
    print("Reading image {}...".format(filename))
    with open(filename, "rb") as image:
        image_content = image.read()
    document = {"content": image_content, "mime_type": "image/tiff"}
    request = {"name": name, "document": document}
    print(" Sending image to the cloud...")
    result = client.process_document(request=request)
    print(" Writing results to {}.json\n\n".format(file_stem))
    with open('{}/{}.json'.format(path, file_stem), 'w') as out:
        out.write(Document.to_json(result.document, preserving_proto_field_name=True))
    # Save values to csv
    data_file = '{}/{}.csv'.format(path, file_stem)
    document = result.document
    for page in document.pages:
        print("Page number: {}".format(page.page_number))
        for form_field in page.form_fields:
            print(
                "Field Name: {}\tConfidence: {}".format(
                    _get_text(form_field.field_name), form_field.field_name.confidence
                )
            )
            print(
                "Field Value: {}\tConfidence: {}".format(
                    _get_text(form_field.field_value), form_field.field_value.confidence
                )
            )
    # for page in result.document.pages:
    #     print("Page number: {}".format(page.page_number))
    #     for form_field in page.form_fields:
    #         print(
    #             "{} ({}): {} ({})".format(
    #                 re.sub(r'\W+ ,-/', '', _get_text(form_field.field_name, result.document)).strip().replace('\n', ''),
    #                 round(form_field.field_name.confidence, 4),
    #                 re.sub(r'\W+ ,-/', '', _get_text(form_field.field_value, result.document)).strip().replace('\n', ''),
    #                 round(form_field.field_value.confidence, 4)
    #             )
    #         )


sys.exit(0)
