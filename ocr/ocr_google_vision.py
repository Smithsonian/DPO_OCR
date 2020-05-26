#!/usr/bin/env python3
#
# Adapted from the Google Cloud Vision API Python Beta Snippets
#  https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/vision/cloud-client/detect/README.rst
#
# Store the creds json in a file named creds.json
#
import io, sys, os
import pandas as pd

#Check if there is a creds.json file
if os.path.isfile("{}/creds.json".format(os.getcwd())) == False:
    print("Error: creds.json missing.")
    sys.exit(1)
else:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "{}/creds.json".format(os.getcwd())

from google.cloud import vision_v1p3beta1 as vision
client = vision.ImageAnnotatorClient()


def ocr_google_vision(filename = None):
    if filename == None:
        return False
    #Open file
    with io.open(filename, 'rb') as image_file:
        content = image_file.read()
    image = vision.types.Image(content=content)
    # Language codes for handwritten OCR
    image_context = vision.types.ImageContext(language_hints = ['en-t-i0-handwrit'])
    response = client.document_text_detection(image = image, image_context = image_context)
    #Dataframe
    df = pd.DataFrame(columns = ['word_text', 'confidence', 'page_no', 'block_no', 'word_line', 'word_no', 'vertices_x_0', 'vertices_y_0', 'vertices_x_1', 'vertices_y_1', 'vertices_x_2', 'vertices_y_2', 'vertices_x_3', 'vertices_y_3'])
    #Counters
    block_no = 0
    page_no = 0
    word_no = 0
    #Iterate over response
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                word_line = 0
                for word in paragraph.words:
                    word_text = ''.join([
                        symbol.text for symbol in word.symbols
                    ])
                    #Get vertices of bounding box
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
                    #Find which line
                    for i in range(word_line, len(ocr_text)):
                        if word_text in ocr_text[i]:
                            word_line = i
                            break
                    wordfile.write("\"%s\",%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (word_text, block_no, page_no, word_no, word_line, word.confidence, wrd_vertices_x_0, wrd_vertices_y_0, wrd_vertices_x_1, wrd_vertices_y_1, wrd_vertices_x_2, wrd_vertices_y_2, wrd_vertices_x_3, wrd_vertices_y_3))
                    df.append(word_text, word.confidence, page_no, block_no, word_line, word_no, wrd_vertices_x_0, wrd_vertices_y_0, wrd_vertices_x_1, wrd_vertices_y_1, wrd_vertices_x_2, wrd_vertices_y_2, wrd_vertices_x_3, wrd_vertices_y_3)
                    word_no += 1
                page_no += 1
            block_no += 1
        page_no += 1
    res['response'] = response
    res['ocr_text'] = response.full_text_annotation.text
    res['df'] = df
    return res

