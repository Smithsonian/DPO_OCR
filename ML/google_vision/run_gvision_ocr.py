#!/usr/bin/env python3
#
# OCR Using Google Vision API and saves the results to a database
#
# To run: python3 ocr_to_db.py [path to jpg files]
#

import io, json, sys, os, psycopg2, glob, shutil
from PIL import Image, ImageDraw
from PIL import ImagePath
from pathlib import Path
from pyfiglet import Figlet


#Script variables
script_title = "OCR using Google Vision"
subtitle = "Digitization Program Office\nOffice of the Chief Information Officer\nSmithsonian Institution\nhttps://dpo.si.edu"
ver = "0.4"
#2021-06-30
vercheck = "https://raw.githubusercontent.com/Smithsonian/DPO_OCR/master/ML/google_vision/toolversion.txt"
repo = "https://github.com/Smithsonian/DPO_OCR/"
lic = "Available under the Apache 2.0 License"


#Check for updates to the script
try:
    with urllib.request.urlopen(vercheck) as response:
       current_ver = response.read()
    cur_ver = current_ver.decode('ascii').replace('\n','')
    if cur_ver != ver:
        msg_text = "{subtitle}\n\n{repo}\n{lic}\n\nver. {ver}\nThis version is outdated. Current version is {cur_ver}.\nPlease download the updated version at: {repo}"
    else:
        msg_text = "{subtitle}\n\n{repo}\n{lic}\n\nver. {ver}"
except:
    msg_text = "{subtitle}\n\n{repo}\n{lic}\n\nver. {ver}"
    cur_ver = ver




f = Figlet(font='slant')
print("\n")
print (f.renderText(script_title))
#print(script_title)
print(msg_text.format(subtitle = subtitle, ver = ver, repo = repo, lic = lic, cur_ver = cur_ver))



if len(sys.argv) != 4:
    print("Error: arguments missing. Usage:\n\n ./run_gvision_ocr.py <folder with jpgs> <doc_version> <doc_section>")
    sys.exit(1)
else:
    if os.path.isdir(sys.argv[1]) == False:
        print("Error: path to JPG files does not exists.")
        sys.exit(1)
    else:
        path = sys.argv[1]
        doc_version = sys.argv[2]
        doc_section = sys.argv[3]



#Check if there is a creds.json file
if os.path.isfile("{}/creds.json".format(os.getcwd())) == False:
    print("Error: creds.json missing.")
    sys.exit(1)
else:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "{}/creds.json".format(os.getcwd())


#Load google vision
from google.cloud import vision_v1p3beta1 as vision
client = vision.ImageAnnotatorClient()
from google.protobuf.json_format import MessageToJson


#Import database settings from settings.py file
import settings

conn = psycopg2.connect(host = settings.ocr_host, database = settings.ocr_db, user = settings.ocr_user, password = settings.ocr_password, connect_timeout = 60)
conn.autocommit = True
db_cursor = conn.cursor()

#Delete old data from project
#db_cursor.execute("DELETE FROM ocr_documents WHERE project_id = %(project_id)s and doc_version = %(doc_version)s", {'project_id': settings.project_id, 'doc_version': doc_version})
#Delete manually

#Get images
list_of_files = glob.glob('{}/*.jpg'.format(path))
print("\n\nFound {} files.".format(len(list_of_files)))


#Prepare folders
#Create project folder
if os.path.exists(settings.project_id) == False:
    os.mkdir(settings.project_id)

#Create subfolders
ver_folder = "{}/{}".format(settings.project_id, doc_version)
if os.path.exists(ver_folder) == False:
    os.mkdir(ver_folder)
version_folder = "{}/{}".format(ver_folder, doc_section)
if os.path.exists(version_folder) == False:
    os.mkdir(version_folder)

response_folder = "{}/response".format(version_folder)
if os.path.exists(response_folder) == False:
    os.mkdir(response_folder)

fulltext_folder = "{}/fulltext".format(version_folder)
if os.path.exists(fulltext_folder) == False:
    os.mkdir(fulltext_folder)

csv_folder = "{}/csv".format(version_folder)
if os.path.exists(csv_folder) == False:
    os.mkdir(csv_folder)

annotated_folder = "{}/images_annotated".format(version_folder)
if os.path.exists(annotated_folder) == False:
    os.mkdir(annotated_folder)

original_folder = "{}/images_original".format(version_folder)
if os.path.exists(original_folder) == False:
    os.mkdir(original_folder)


#Run each file
for filename in list_of_files:
    file_stem = Path(filename).stem

    #Open file
    print("Reading image...")
    with io.open(filename, 'rb') as image_file:
        content = image_file.read()

    #Open image using PIL
    im = Image.open(filename)

    #Create entry for file
    print("\n\nCreating database record for {}...".format(filename))
    db_cursor.execute("INSERT INTO ocr_documents (project_id, filename, doc_version, doc_section, ocr_source, doc_width, doc_height) VALUES (%(project_id)s, %(filename)s, %(doc_version)s, %(doc_section)s, %(source)s, %(doc_width)s, %(doc_height)s) RETURNING document_id", {'project_id': settings.project_id, 'filename': Path(filename).name, 'doc_version': doc_version, 'doc_section': doc_section, 'source': 'Google Vision API', 'doc_width': im.size[0], 'doc_height': im.size[1]})
    document_id = db_cursor.fetchone()
    print(db_cursor.query)

    #Make a copy of the original
    shutil.copy(filename, "{}/{}.jpg".format(original_folder, file_stem))

    image = vision.types.Image(content = content)
    # From google vision api beta snippets--
    # Language hint codes for handwritten OCR:
    # en-t-i0-handwrit, mul-Latn-t-i0-handwrit
    image_context = vision.types.ImageContext(language_hints=['en-t-i0-handwrit'])

    print("Waiting for API response...")
    response = client.document_text_detection(image = image, image_context = image_context)

    #Write response to json
    jsonObj = json.loads(MessageToJson(response, preserving_proto_field_name=True))
    with open('{}/{}.json'.format(response_folder, file_stem), 'w') as out:
        out.write(json.dumps(jsonObj))

    ocr_text = response.full_text_annotation.text.split("\n")

    print('Full Text: \n=============\n{}\n=============\n'.format(response.full_text_annotation.text))
    with open('{}/{}.txt'.format(fulltext_folder, file_stem), 'w') as out:
        out.write(response.full_text_annotation.text)

    #word, confidence, coords
    data_file = '{}/{}.csv'.format(csv_folder, file_stem)
    wordfile = open(data_file, "w")
    wordfile.write("word_text,block,page,word,word_line,confidence,vertices_x_0,vertices_y_0,vertices_x_1,vertices_y_1,vertices_x_2,vertices_y_2,vertices_x_3,vertices_y_3\n")

    img_file = '{}/{}.jpg'.format(annotated_folder, file_stem)

    word_list = []
    p = 0
    b = 0
    w = 0

    print("Parsing blocks of text...")
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            #print('\nBlock confidence: {}\n'.format(block.confidence))
            b += 1
            #write box to image
            if block.confidence > 0.9:
                linecolor = "#66ff33"
            elif block.confidence <= 0.9 and block.confidence > 0.8:
                linecolor = "#ffdb4d"
            elif block.confidence <= 0.8 and block.confidence > 0.7:
                linecolor = "#ffa366"
            elif block.confidence <= 0.7:
                linecolor = "#ff6666"
            wrd_vertices = [str(block.bounding_box.vertices[0]).split('\n')]
            wrd_vertices_x_0 = wrd_vertices[0][0].replace('x: ', '')
            wrd_vertices_y_0 = wrd_vertices[0][1].replace('y: ', '')
            #1
            wrd_vertices = [str(block.bounding_box.vertices[1]).split('\n')]
            wrd_vertices_x_1 = wrd_vertices[0][0].replace('x: ', '')
            wrd_vertices_y_1 = wrd_vertices[0][1].replace('y: ', '')
            #2
            wrd_vertices = [str(block.bounding_box.vertices[2]).split('\n')]
            wrd_vertices_x_2 = wrd_vertices[0][0].replace('x: ', '')
            wrd_vertices_y_2 = wrd_vertices[0][1].replace('y: ', '')
            #3
            wrd_vertices = [str(block.bounding_box.vertices[3]).split('\n')]
            wrd_vertices_x_3 = wrd_vertices[0][0].replace('x: ', '')
            wrd_vertices_y_3 = wrd_vertices[0][1].replace('y: ', '')
            if settings.box_draw == "blocks":
                if wrd_vertices_x_0 == "" or wrd_vertices_y_0 == "" or wrd_vertices_x_1 == "" or wrd_vertices_y_1 == "" or wrd_vertices_x_2 == "" or wrd_vertices_y_2 == "" or wrd_vertices_x_3 == "" or wrd_vertices_y_3 == "":
                    continue
                draw = ImageDraw.Draw(im)
                if int(wrd_vertices_y_0) - settings.line_width < 0:
                    wrd_vertices_y_0_line = 0
                else:
                    wrd_vertices_y_0_line = int(wrd_vertices_y_0) - settings.line_width
                if int(wrd_vertices_x_1) + settings.line_width > im.size[0]:
                    wrd_vertices_x_1_line = im.size[0]
                else:
                    wrd_vertices_x_1_line = int(wrd_vertices_x_1) + settings.line_width
                if int(wrd_vertices_y_1) - settings.line_width < 0:
                    wrd_vertices_y_1_line = 0
                else:
                    wrd_vertices_y_1_line = int(wrd_vertices_y_1) - settings.line_width
                if int(wrd_vertices_x_2) + settings.line_width > im.size[0]:
                    wrd_vertices_x_2_line = im.size[0]
                else:
                    wrd_vertices_x_2_line = int(wrd_vertices_x_2) + settings.line_width
                if int(wrd_vertices_y_2) + settings.line_width > im.size[1]:
                    wrd_vertices_y_2_line = im.size[1]
                else:
                    wrd_vertices_y_2_line = int(wrd_vertices_y_2) + settings.line_width
                if int(wrd_vertices_x_3) - settings.line_width < 0:
                    wrd_vertices_x_3_line = 0
                else:
                    wrd_vertices_x_3_line = int(wrd_vertices_x_3) - settings.line_width
                if int(wrd_vertices_y_3) + settings.line_width > im.size[1]:
                    wrd_vertices_y_3_line = im.size[1]
                else:
                    wrd_vertices_y_3_line = int(wrd_vertices_y_3) + settings.line_width
                if int(wrd_vertices_x_0) - settings.line_width < 0:
                    wrd_vertices_x_0_line = 0
                else:
                    wrd_vertices_x_0_line = int(wrd_vertices_x_0) - settings.line_width
                draw.line([(wrd_vertices_x_0_line, wrd_vertices_y_0_line), (wrd_vertices_x_1_line, wrd_vertices_y_1_line)], fill = linecolor, width = settings.line_width)
                draw.line([(wrd_vertices_x_1_line, wrd_vertices_y_1_line), (wrd_vertices_x_2_line, wrd_vertices_y_2_line)], fill = linecolor, width = settings.line_width)
                draw.line([(wrd_vertices_x_2_line, wrd_vertices_y_2_line), (wrd_vertices_x_3_line, wrd_vertices_y_3_line)], fill = linecolor, width = settings.line_width)
                draw.line([(wrd_vertices_x_3_line, wrd_vertices_y_3_line), (wrd_vertices_x_0_line, wrd_vertices_y_0_line)], fill = linecolor, width = settings.line_width)
                del draw
            db_cursor.execute("INSERT INTO ocr_blocks (document_id, block, confidence, vertices_x_0, vertices_y_0, vertices_x_1, vertices_y_1, vertices_x_2, vertices_y_2, vertices_x_3, vertices_y_3) VALUES (%(document_id)s,%(block)s, %(confidence)s, %(vertices_x_0)s, %(vertices_y_0)s, %(vertices_x_1)s, %(vertices_y_1)s, %(vertices_x_2)s, %(vertices_y_2)s, %(vertices_x_3)s, %(vertices_y_3)s)", {'document_id': document_id, 'block': b, 'confidence': block.confidence, 'vertices_x_0': wrd_vertices_x_0, 'vertices_y_0': wrd_vertices_y_0, 'vertices_x_1': wrd_vertices_x_1, 'vertices_y_1': wrd_vertices_y_1, 'vertices_x_2': wrd_vertices_x_2, 'vertices_y_2': wrd_vertices_y_2, 'vertices_x_3': wrd_vertices_x_3, 'vertices_y_3': wrd_vertices_y_3})
            for paragraph in block.paragraphs:
                print('Paragraph confidence: {}'.format(paragraph.confidence))
                p += 1
                word_line = 0
                for word in paragraph.words:
                    word_text = ''.join([
                        symbol.text for symbol in word.symbols
                    ])
                    #Should ignore?
                    if word_text in settings.text_ignore:
                        continue
                    if settings.ignore_text(word_text, Path(filename).stem):
                        continue
                    w += 1
                    #0
                    wrd_vertices = [str(word.bounding_box.vertices[0]).split('\n')]
                    wrd_vertices_x_0 = wrd_vertices[0][0].replace('x: ', '')
                    wrd_vertices_y_0 = wrd_vertices[0][1].replace('y: ', '')
                    #1
                    wrd_vertices = [str(word.bounding_box.vertices[1]).split('\n')]
                    wrd_vertices_x_1 = wrd_vertices[0][0].replace('x: ', '')
                    wrd_vertices_y_1 = wrd_vertices[0][1].replace('y: ', '')
                    #2
                    wrd_vertices = [str(word.bounding_box.vertices[2]).split('\n')]
                    wrd_vertices_x_2 = wrd_vertices[0][0].replace('x: ', '')
                    wrd_vertices_y_2 = wrd_vertices[0][1].replace('y: ', '')
                    #3
                    wrd_vertices = [str(word.bounding_box.vertices[3]).split('\n')]
                    wrd_vertices_x_3 = wrd_vertices[0][0].replace('x: ', '')
                    wrd_vertices_y_3 = wrd_vertices[0][1].replace('y: ', '')
                    #Missing x vertex:
                    if wrd_vertices_x_3[0:2] == "y:":
                        wrd_vertices_y_3 = wrd_vertices[0][0].replace('y: ', '')
                        wrd_vertices_x_3 = 0
                    #Find which line
                    for i in range(word_line, len(ocr_text)):
                        if word_text in ocr_text[i]:
                            word_line = i
                            break
                    print("{}-{}-{}-{} {}".format(i, word_line, word_text, ocr_text[i], word_text in ocr_text[i]))
                    wordfile.write("\"%s\",%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (word_text, b, p, w, word_line, word.confidence, wrd_vertices_x_0, wrd_vertices_y_0, wrd_vertices_x_1, wrd_vertices_y_1, wrd_vertices_x_2, wrd_vertices_y_2, wrd_vertices_x_3, wrd_vertices_y_3))
                    #write box to image
                    if word.confidence > 0.9:
                        linecolor = "#66ff33"
                    elif word.confidence <= 0.9 and word.confidence > 0.8:
                        linecolor = "#ffdb4d"
                    elif word.confidence <= 0.8 and word.confidence > 0.7:
                        linecolor = "#ffa366"
                    elif word.confidence <= 0.7:
                        linecolor = "#ff6666"
                    if settings.box_draw == "words":
                        if wrd_vertices_x_0 == "" or wrd_vertices_y_0 == "" or wrd_vertices_x_1 == "" or wrd_vertices_y_1 == "" or wrd_vertices_x_2 == "" or wrd_vertices_y_2 == "" or wrd_vertices_x_3 == "" or wrd_vertices_y_3 == "":
                            continue
                        draw = ImageDraw.Draw(im)
                        if int(wrd_vertices_y_0) - settings.line_width < 0:
                            wrd_vertices_y_0_line = 0
                        else:
                            wrd_vertices_y_0_line = int(wrd_vertices_y_0) - settings.line_width
                        if int(wrd_vertices_x_1) + settings.line_width > im.size[0]:
                            wrd_vertices_x_1_line = im.size[0]
                        else:
                            wrd_vertices_x_1_line = int(wrd_vertices_x_1) + settings.line_width
                        if int(wrd_vertices_y_1) - settings.line_width < 0:
                            wrd_vertices_y_1_line = 0
                        else:
                            wrd_vertices_y_1_line = int(wrd_vertices_y_1) - settings.line_width
                        if int(wrd_vertices_x_2) + settings.line_width > im.size[0]:
                            wrd_vertices_x_2_line = im.size[0]
                        else:
                            wrd_vertices_x_2_line = int(wrd_vertices_x_2) + settings.line_width
                        if int(wrd_vertices_y_2) + settings.line_width > im.size[1]:
                            wrd_vertices_y_2_line = im.size[1]
                        else:
                            wrd_vertices_y_2_line = int(wrd_vertices_y_2) + settings.line_width
                        if int(wrd_vertices_x_3) - settings.line_width < 0:
                            wrd_vertices_x_3_line = 0
                        else:
                            wrd_vertices_x_3_line = int(wrd_vertices_x_3) - settings.line_width
                        if int(wrd_vertices_y_3) + settings.line_width > im.size[1]:
                            wrd_vertices_y_3_line = im.size[1]
                        else:
                            wrd_vertices_y_3_line = int(wrd_vertices_y_3) + settings.line_width
                        if int(wrd_vertices_x_0) - settings.line_width < 0:
                            wrd_vertices_x_0_line = 0
                        else:
                            wrd_vertices_x_0_line = int(wrd_vertices_x_0) - settings.line_width
                        draw.line([(wrd_vertices_x_0_line, wrd_vertices_y_0_line), (wrd_vertices_x_1_line, wrd_vertices_y_1_line)], fill = linecolor, width = settings.line_width)
                        draw.line([(wrd_vertices_x_1_line, wrd_vertices_y_1_line), (wrd_vertices_x_2_line, wrd_vertices_y_2_line)], fill = linecolor, width = settings.line_width)
                        draw.line([(wrd_vertices_x_2_line, wrd_vertices_y_2_line), (wrd_vertices_x_3_line, wrd_vertices_y_3_line)], fill = linecolor, width = settings.line_width)
                        draw.line([(wrd_vertices_x_3_line, wrd_vertices_y_3_line), (wrd_vertices_x_0_line, wrd_vertices_y_0_line)], fill = linecolor, width = settings.line_width)
                        del draw
                    word_list.append([word_text, word.confidence, [[wrd_vertices_x_0, wrd_vertices_y_0], [wrd_vertices_x_1, wrd_vertices_y_1], [wrd_vertices_x_2, wrd_vertices_y_2], [wrd_vertices_x_3, wrd_vertices_y_3]]])
                    db_cursor.execute("INSERT INTO ocr_entries (document_id, word_text, block, page, word, word_line, confidence, vertices_x_0, vertices_y_0, vertices_x_1, vertices_y_1, vertices_x_2, vertices_y_2, vertices_x_3, vertices_y_3) VALUES (%(document_id)s, %(word_text)s, %(block)s, %(page)s, %(word)s, %(word_line)s, %(confidence)s, %(vertices_x_0)s, %(vertices_y_0)s, %(vertices_x_1)s, %(vertices_y_1)s, %(vertices_x_2)s, %(vertices_y_2)s, %(vertices_x_3)s, %(vertices_y_3)s)", {'document_id': document_id, 'word_text': word_text, 'block': b, 'page': p, 'word': w, 'word_line': word_line, 'confidence': word.confidence, 'vertices_x_0': wrd_vertices_x_0, 'vertices_y_0': wrd_vertices_y_0, 'vertices_x_1': wrd_vertices_x_1, 'vertices_y_1': wrd_vertices_y_1, 'vertices_x_2': wrd_vertices_x_2, 'vertices_y_2': wrd_vertices_y_2, 'vertices_x_3': wrd_vertices_x_3, 'vertices_y_3': wrd_vertices_y_3})

    #If cropping is true and if there is something to crop
    if settings.crop == True and len(response.text_annotations) > 0:
        #Crop image
        results_poly = response.text_annotations[0].bounding_poly
        results_minx = min(results_poly.vertices[0].x, results_poly.vertices[1].x, results_poly.vertices[2].x, results_poly.vertices[3].x)
        results_miny = min(results_poly.vertices[0].y, results_poly.vertices[1].y, results_poly.vertices[2].y, results_poly.vertices[3].y)
        results_maxx = max(results_poly.vertices[0].x, results_poly.vertices[1].x, results_poly.vertices[2].x, results_poly.vertices[3].x)
        results_maxy = max(results_poly.vertices[0].y, results_poly.vertices[1].y, results_poly.vertices[2].y, results_poly.vertices[3].y)

        if results_minx > settings.crop_buffer:
            results_minx = results_minx - settings.crop_buffer
        if results_miny > settings.crop_buffer:
            results_miny = results_miny - settings.crop_buffer
        if (results_maxx + settings.crop_buffer) < im.size[0]:
            results_maxx = results_maxx + settings.crop_buffer
        if (results_maxy + settings.crop_buffer) < im.size[1]:
            results_maxy = results_maxy + settings.crop_buffer
        print("Cropping image to ({},{}), ({},{})".format(results_minx, results_miny, results_maxx, results_maxy))
        im1 = im.crop((results_minx, results_miny, results_maxx, results_maxy))
        #Save cropped image
        im1.save(img_file, "JPEG")
    else:
        im.save(img_file, "JPEG")

    wordfile.close()


sys.exit(0)
