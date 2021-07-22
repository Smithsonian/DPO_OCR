#!/usr/bin/env python3

#prepare ledgers from NMAH
# 2021-03-02

import sys, os, glob
from PIL import Image
from autocrop import *
from pathlib import Path

folder = sys.argv[1]


os.mkdir("{folder}/{folder}_left".format(folder = folder))
os.mkdir("{folder}/{folder}_right".format(folder = folder))


#Get images
list_of_files = glob.glob('{}/*.jpg'.format(folder))
print("\n\nFound {} files.".format(len(list_of_files)))


for file in list_of_files:
    filename = Path(file).name
    print(filename)
    #remove border
    img = autocrop(file, 0)
    #split in half
    half_width = round(img.size[0]/2)
    #(left, upper, right, lower)
    im_left = img.crop((0, 0, half_width, img.size[1]))
    im_right = img.crop((half_width, 0, img.size[0], img.size[1]))
    im_left.save("{folder}/{folder}_left/{filename}".format(folder = folder, filename = filename))
    im_right.save("{folder}/{folder}_right/{filename}".format(folder = folder, filename = filename))
