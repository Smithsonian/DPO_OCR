#!/usr/bin/env python3
#
# OCR Using Google Vision API and saves the results to a database
# 
# To run: python3 ocr_to_db.py [path to jpg files]
#



import io, json, sys, os, psycopg2, glob
from PIL import Image, ImageDraw 
from PIL import ImagePath
from pathlib import Path
from pyfiglet import Figlet


#Script variables
script_title = "Google Vision OCR"
subtitle = "Digitization Program Office\nOffice of the Chief Information Officer\nSmithsonian Institution\nhttps://dpo.si.edu"
ver = "0.1"
#2020-06-11
vercheck = "https://raw.githubusercontent.com/Smithsonian/DPO_OCR/master/google_vision/toolversion.txt"
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



if len(sys.argv) != 2:
    print("Error: path to JPG files missing.")
    sys.exit(1)
else:
    path = sys.argv[1]



#Check if there is a creds.json file
if os.path.isfile("{}/creds.json".format(os.getcwd())) == False:
    print("Error: creds.json missing.")
    sys.exit(1)
else:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "{}/creds.json".format(os.getcwd())

#Load google vision
from google.cloud import vision_v1p3beta1 as vision
client = vision.ImageAnnotatorClient()



##Import database settings from settings.py file
import settings


conn = psycopg2.connect(host = settings.ocr_host, database = settings.ocr_db, user = settings.ocr_user, password = settings.ocr_password, connect_timeout = 60)
conn.autocommit = True
db_cursor = conn.cursor()


#Get images
list_of_files = glob.glob('{}/*.jpg'.format(path))
print("\n\nFound {} files.".format(len(list_of_files)))


for filename in list_of_files:
    #Create entry for file
    print("\n\nCreating database record for {}...".format(filename))
    db_cursor.execute("INSERT INTO ocr_documents (project_id, filename, ocr_source) VALUES (%(project_id)s, %(filename)s, %(source)s) RETURNING document_id", {'project_id': settings.project_id, 'filename': Path(filename).name, 'source': settings.source})
    document_id = db_cursor.fetchone()

    #Open file
    print("Reading image...")
    with io.open(filename, 'rb') as image_file:
        content = image_file.read()

    image = vision.types.Image(content=content)

    # Language hint codes for handwritten OCR:
    # en-t-i0-handwrit, mul-Latn-t-i0-handwrit
    # Note: Use only one language hint code per request for handwritten OCR.
    image_context = vision.types.ImageContext(
        language_hints=['en-t-i0-handwrit'])

    print("Waiting for API response...")
    response = client.document_text_detection(image=image, image_context=image_context)


    if os.path.exists('response') == False:
        os.mkdir('response')

    with open('response/{}.txt'.format(Path(filename).stem), 'w') as out:
        out.write(str(response))

    ocr_text = response.full_text_annotation.text.split("\n")

    print('Full Text: \n=============\n{}\n=============\n'.format(response.full_text_annotation.text))

    if os.path.exists('fulltext') == False:
        os.mkdir('fulltext')

    with open('fulltext/{}.txt'.format(Path(filename).stem), 'w') as out:
        out.write(response.full_text_annotation.text)


    #word, confidence, coords
    if os.path.exists('csv') == False:
        os.mkdir('csv')

    data_file = 'csv/{}.csv'.format(Path(filename).stem)

    if os.path.exists('images_annotated') == False:
        os.mkdir('images_annotated')
    img_file = 'images_annotated/{}.jpg'.format(Path(filename).stem)


    wordfile = open(data_file, "w")
    wordfile.write("word_text,block,page,word,word_line,confidence,vertices_x_0,vertices_y_0,vertices_x_1,vertices_y_1,vertices_x_2,vertices_y_2,vertices_x_3,vertices_y_3\n")



    #image for PIL
    im = Image.open(filename)


    word_list = []
    p = 0
    b = 0
    w = 0

    print("Parsing blocks of text...")
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            #print('\nBlock confidence: {}\n'.format(block.confidence))
            b += 1
            for paragraph in block.paragraphs:
                #print('Paragraph confidence: {}'.format(
                    #paragraph.confidence))
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
                    #print([word_text, word.confidence, [[wrd_vertices_x_0, wrd_vertices_y_0], [wrd_vertices_x_1, wrd_vertices_y_1], [wrd_vertices_x_2, wrd_vertices_y_2], [wrd_vertices_x_3, wrd_vertices_y_3]]])
                    #Find which line
                    for i in range(word_line, len(ocr_text)):
                        #print("{}-{}-{} {}".format(i, word_text, ocr_text[i], word_text in ocr_text[i]))
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
                    draw = ImageDraw.Draw(im)
                    draw.line([(int(wrd_vertices_x_0) - settings.line_width, int(wrd_vertices_y_0) - settings.line_width), (int(wrd_vertices_x_1) + settings.line_width, int(wrd_vertices_y_1) - settings.line_width)], fill = linecolor, width = settings.line_width)
                    draw.line([(int(wrd_vertices_x_1) + settings.line_width, int(wrd_vertices_y_1) - settings.line_width), (int(wrd_vertices_x_2) + settings.line_width, int(wrd_vertices_y_2) + settings.line_width)], fill = linecolor, width = settings.line_width)
                    draw.line([(int(wrd_vertices_x_2) + settings.line_width, int(wrd_vertices_y_2) + settings.line_width), (int(wrd_vertices_x_3) - settings.line_width, int(wrd_vertices_y_3) + settings.line_width)], fill = linecolor, width = settings.line_width)
                    draw.line([(int(wrd_vertices_x_3) - settings.line_width, int(wrd_vertices_y_3) + settings.line_width), (int(wrd_vertices_x_0) - settings.line_width, int(wrd_vertices_y_0) - settings.line_width)], fill = linecolor, width = settings.line_width)
                    del draw
                    word_list.append([word_text, word.confidence, [[wrd_vertices_x_0, wrd_vertices_y_0], [wrd_vertices_x_1, wrd_vertices_y_1], [wrd_vertices_x_2, wrd_vertices_y_2], [wrd_vertices_x_3, wrd_vertices_y_3]]])
                    db_cursor.execute("INSERT INTO ocr_entries (document_id, word_text, block, page, word, word_line, confidence, vertices_x_0, vertices_y_0, vertices_x_1, vertices_y_1, vertices_x_2, vertices_y_2, vertices_x_3, vertices_y_3) VALUES (%(document_id)s, %(word_text)s, %(block)s, %(page)s, %(word)s, %(word_line)s, %(confidence)s, %(vertices_x_0)s, %(vertices_y_0)s, %(vertices_x_1)s, %(vertices_y_1)s, %(vertices_x_2)s, %(vertices_y_2)s, %(vertices_x_3)s, %(vertices_y_3)s)", {'document_id': document_id, 'word_text': word_text, 'block': b, 'page': p, 'word': w, 'word_line': word_line, 'confidence': word.confidence, 'vertices_x_0': wrd_vertices_x_0, 'vertices_y_0': wrd_vertices_y_0, 'vertices_x_1': wrd_vertices_x_1, 'vertices_y_1': wrd_vertices_y_1, 'vertices_x_2': wrd_vertices_x_2, 'vertices_y_2': wrd_vertices_y_2, 'vertices_x_3': wrd_vertices_x_3, 'vertices_y_3': wrd_vertices_y_3})

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


sys.exit(0)
