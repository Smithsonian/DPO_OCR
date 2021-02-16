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


create table ocr_transcription_ento_auto as select * from ocr_transcription_ento where 1=2; 
CREATE INDEX ocr_transcription_ento_auto_fid_idx ON ocr_transcription_ento_auto USING BTREE(filename);
ALTER TABLE ocr_transcription_ento_auto ADD COLUMN reference_size text;
CREATE INDEX ocr_transcription_ento_auto_ref_idx ON ocr_transcription_ento_auto USING BTREE(reference_size);
ALTER TABLE ocr_transcription_ento_auto ADD CONSTRAINT ocrt_entoauto UNIQUE (filename);



--drop table if exists ocr_auto_sample;
create table ocr_auto_sample 
(
    project_id uuid, 
    filename text,
    reference_size text, 
    ref_or_test text
);




--0.05
--Reference
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            project_id, 
            replace(filename, '.jpg', ''),
            '0.05',
            'ref'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07'
        ORDER BY RANDOM()
        LIMIT 50
    );

--Test
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            '960d9a59-81a6-45c7-8392-eef830b3ba07'::uuid,
            replace(filename, '.jpg', ''),
            '0.05',
            'test'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07' AND
            replace(filename, '.jpg', '') NOT IN (SELECT filename FROM ocr_auto_sample WHERE reference_size = '0.05')
    );




--0.1
--Reference
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            project_id, 
            replace(filename, '.jpg', ''),
            '0.1',
            'ref'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07'
        ORDER BY RANDOM()
        LIMIT 100
    );

--Test
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            '960d9a59-81a6-45c7-8392-eef830b3ba07'::uuid,
            replace(filename, '.jpg', ''),
            '0.1',
            'test'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07' AND
            replace(filename, '.jpg', '') NOT IN (SELECT filename FROM ocr_auto_sample WHERE reference_size = '0.1')
    );




--0.2
--Reference
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            project_id, 
            replace(filename, '.jpg', ''),
            '0.2',
            'ref'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07'
        ORDER BY RANDOM()
        LIMIT 200
    );

--Test
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            '960d9a59-81a6-45c7-8392-eef830b3ba07'::uuid,
            replace(filename, '.jpg', ''),
            '0.2',
            'test'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07' AND
            replace(filename, '.jpg', '') NOT IN (SELECT filename FROM ocr_auto_sample WHERE reference_size = '0.2')
    );




--0.3
--Reference
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            project_id, 
            replace(filename, '.jpg', ''),
            '0.3',
            'ref'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07'
        ORDER BY RANDOM()
        LIMIT 300
    );

--Test
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            '960d9a59-81a6-45c7-8392-eef830b3ba07'::uuid,
            replace(filename, '.jpg', ''),
            '0.3',
            'test'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07' AND
            replace(filename, '.jpg', '') NOT IN (SELECT filename FROM ocr_auto_sample WHERE reference_size = '0.3')
    );



--0.4
--Reference
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            project_id, 
            replace(filename, '.jpg', ''),
            '0.4',
            'ref'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07'
        ORDER BY RANDOM()
        LIMIT 400
    );

--Test
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            '960d9a59-81a6-45c7-8392-eef830b3ba07'::uuid,
            replace(filename, '.jpg', ''),
            '0.4',
            'test'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07' AND
            replace(filename, '.jpg', '') NOT IN (SELECT filename FROM ocr_auto_sample WHERE reference_size = '0.4')
    );




--0.5
--Reference
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            project_id, 
            replace(filename, '.jpg', ''),
            '0.5',
            'ref'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07'
        ORDER BY RANDOM()
        LIMIT 500
    );

--Test
INSERT INTO ocr_auto_sample 
    (project_id, filename, reference_size, ref_or_test) 
    (
        SELECT
            '960d9a59-81a6-45c7-8392-eef830b3ba07'::uuid,
            replace(filename, '.jpg', ''),
            '0.5',
            'test'
        FROM 
            ocr_documents
        WHERE
            project_id = '960d9a59-81a6-45c7-8392-eef830b3ba07' AND
            replace(filename, '.jpg', '') NOT IN (SELECT filename FROM ocr_auto_sample WHERE reference_size = '0.5')
    );


select reference_size, count(*) from ocr_auto_sample group by reference_size;


