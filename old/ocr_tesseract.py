#!/usr/bin/env python3
#
# Adapted from 
#  https://github.com/madmaze/pytesseract
#
import io, sys
from PIL import Image
import pandas as pd
import subprocess
from subprocess import Popen,PIPE
from io import StringIO


tessdata_lib = "/mnt/c/Github/tessdata_best/"


def ocr_tesseract(filename = None):
    if filename == None:
        return False
    #im = Image.open(filename)
    p = subprocess.Popen(['tesseract', filename, 'stdout', '--tessdata-dir', tessdata_lib, '-l', 'eng', '-c', 'tessedit_create_tsv=1', '--psm', '11'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    b = StringIO(p.communicate()[0].decode('utf-8'))
    response = pd.read_csv(b, sep="\t")
    res = dict()
    res['response'] = response
    p = subprocess.Popen(['tesseract', filename, 'stdout', '--tessdata-dir', tessdata_lib, '-l', 'eng', '-c', 'tessedit_create_tsv=1', '--psm', '11'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    b = StringIO(p.communicate()[0].decode('utf-8'))
    ocr_text = pd.read_csv(b, sep="\t")
    response = response[response.conf > 0].copy()
    response = response[response.text != " "].copy()
    response['vertices_x_0'] = response['left']
    response['vertices_y_0'] = response['top']
    response['vertices_x_1'] = response['left'] + response['width']
    response['vertices_y_1'] = response['top']
    response['vertices_x_2'] = response['left'] + response['width']
    response['vertices_y_2'] = response['top'] + response['height']
    response['vertices_x_3'] = response['left']
    response['vertices_y_3'] = response['top'] + response['height']
    response['confidence'] = round((response['conf'] / 100), 2)
    response = response[['text', 'confidence', 'page_num', 'block_num', 'line_num', 'word_num', 'vertices_x_0', 'vertices_y_0', 'vertices_x_1', 'vertices_y_1', 'vertices_x_2', 'vertices_y_2', 'vertices_x_3', 'vertices_y_3']]
    response.columns = ['word_text', 'confidence', 'page_no', 'block_no', 'word_line', 'word_no', 'vertices_x_0', 'vertices_y_0', 'vertices_x_1', 'vertices_y_1', 'vertices_x_2', 'vertices_y_2', 'vertices_x_3', 'vertices_y_3']
    res['ocr_text'] = ocr_text
    res['df'] = response    
    return res

