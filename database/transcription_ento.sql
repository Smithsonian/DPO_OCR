create table ocr_transcription_ento
(
filename text PRIMARY KEY,
collector text,
verbatim_date text,
verbatim_locality text,
country text,
state_territory text,
district_county text,
precise_locality text,
latitude_longitude text,
elevation text,
other_numbers text,
label_notes text,
v_notes text,
nmnh_notes text,
svstaff_notes text
);

CREATE INDEX ocr_transcription_ento_fid_idx ON ocr_transcription_ento USING BTREE(filename);
