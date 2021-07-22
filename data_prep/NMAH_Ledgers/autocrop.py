#!/usr/bin/env python3
#
# Autocrop images
# Version 0.2
# 2021-03-02
#
#Import modules
from PIL import Image, ImageChops
import os, sys

#Import settings from settings.py file
#import settings








#Code inspired by https://stackoverflow.com/a/48605963
def trim(im, edge_size):
    bg = Image.new(im.mode, im.size, im.getpixel((0,0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if edge_size != 0:
        bbox2 = (bbox[0] - edge_size, bbox[1] - edge_size, bbox[2] + edge_size, bbox[3] + edge_size)
        return(im.crop(bbox2))
    else:
        return(im.crop(bbox))



#Try cropping and small rotations
def autocrop(filename, edge_size):
    #Add iterative way to choose best rotation instead of hardcoded
    img = Image.open(filename)
    #Basic trim
    new_im = trim(img, edge_size)
    #Rotate
    rotated_1 = img.rotate(0.1)
    new_im_1 = trim(rotated_1, edge_size)
    #Rotate in the other direction
    rotated_2 = img.rotate(-0.1)
    new_im_2 = trim(rotated_2, edge_size)
    if new_im.size[0] < new_im_1.size[0] and new_im.size[0] < new_im_2.size[0]:
        #No rotation
        return(new_im)
    else:
        if new_im_1.size[0] < new_im_2.size[0]:
            #First
            return(new_im_1)
        else:
            return(new_im_2)



if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Error: arguments missing. Usage:\n\n ./autocrop.py <image> <edge_size>")
        sys.exit(1)
    else:
        filename = sys.argv[1]
        edge_size = int(sys.argv[2])

    new_im = autocrop(filename, edge_size)
    if os.path.exists("output") == False:
        os.mkdir("output")
    new_im.save("output/{}".format(filename))
