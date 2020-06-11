#!/bin/bash
#
#
for i in images/*.jpg; do
    python3 ocr_to_db.py $i
done
