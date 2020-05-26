#!/usr/bin/env python3
#
# How to run: python3 ocr_to_csv.py [filename]
#

import io, json, sys, os, psycopg2
from PIL import Image, ImageDraw 
from PIL import ImagePath
from pathlib import Path
import pandas as pd
from ocr import ocr_tesseract
from ocr import ocr_google_vision
import csv


if len(sys.argv) != 2:
    print("Error: filename missing.")
    sys.exit(1)


filename = sys.argv[1]


crop_buffer = 30
line_buffer = 4
color_breaks = [0.90, 0.80, 0.70]


res = ocr_tesseract.ocr_tesseract(filename)

im = Image.open(filename)
data_file = '{}.csv'.format(Path(filename).stem)
res['df'].to_csv(data_file, quoting = csv.QUOTE_NONNUMERIC, index = False)

df = res['df'].copy()

for index, row in df.iterrows():
    #write box to image
    if row["confidence"] > color_breaks[0]:
        linecolor = "#66ff33"
    elif row["confidence"] <= color_breaks[0] and row["confidence"] > color_breaks[1]:
        linecolor = "#ffdb4d"
    elif row["confidence"] <= color_breaks[1] and row["confidence"] > color_breaks[2]:
        linecolor = "#ffa366"
    elif row["confidence"] <= color_breaks[2]:
        linecolor = "#ff6666"
    draw = ImageDraw.Draw(im)
    draw.line([(int(row["vertices_x_0"]) - line_buffer, int(row["vertices_y_0"]) - line_buffer), (int(row["vertices_x_1"]) + line_buffer, int(row["vertices_y_1"]) + line_buffer)], fill = linecolor, width = 3)
    draw.line([(int(row["vertices_x_1"]) - line_buffer, int(row["vertices_y_1"]) - line_buffer), (int(row["vertices_x_2"]) + line_buffer, int(row["vertices_y_2"]) + line_buffer)], fill = linecolor, width = 3)
    draw.line([(int(row["vertices_x_2"]) - line_buffer, int(row["vertices_y_2"]) - line_buffer), (int(row["vertices_x_3"]) + line_buffer, int(row["vertices_y_3"]) + line_buffer)], fill = linecolor, width = 3)
    draw.line([(int(row["vertices_x_3"]) - line_buffer, int(row["vertices_y_3"]) - line_buffer), (int(row["vertices_x_0"]) + line_buffer, int(row["vertices_y_0"]) + line_buffer)], fill = linecolor, width = 3)
    del draw



results_minx = min(df["vertices_x_0"])
results_miny = min(df["vertices_y_0"])

results_maxx = max(df["vertices_x_1"])
results_maxy = max(df["vertices_y_2"])

if results_minx > crop_buffer:
    results_minx = results_minx - crop_buffer
if results_miny > crop_buffer:
    results_miny = results_miny - crop_buffer
if (results_maxx + crop_buffer) < im.size[0]:
    results_maxx = results_maxx + crop_buffer
if (results_maxy + crop_buffer) < im.size[1]:
    results_maxy = results_maxy + crop_buffer

print("Cropping image to ({},{}), ({},{})".format(results_minx, results_miny, results_maxx, results_maxy))


im1 = im.crop((results_minx, results_miny, results_maxx, results_maxy))


if os.path.exists('extracted') == False:
    os.mkdir('extracted')

img_file = 'extracted/{}.jpg'.format(Path(filename).stem)

#Save cropped image
im1.save(img_file, "JPEG")

