
library(DBI)
library(shiny)
library(dplyr)
library(readr)
library(plotly)
library(DT)
#library(tm)
#library(wordcloud)
#library(memoise)

# Settings ----
source("settings.R")
ui_ver <- "0.2.0"


#UI----
ui <- fluidPage(
  
  # Application title
  #titlePanel("OCR test"),
  uiOutput("selectfile"),
  hr(),
  fluidRow(
    column(width = 2,
           uiOutput("filetext"),
           uiOutput("summary"),
           plotlyOutput("plot")
    ),
    column(width = 6,
           uiOutput("results_h"),
           DT::dataTableOutput("results"),
           # uiOutput("results2_h"),
           # DT::dataTableOutput("results2"),
           uiOutput("image")
    ),
   column(width = 4,
          #uiOutput("ocr_transcript", style = "font-size: 80%;")
          DT::dataTableOutput("ocr_transcript")
   )
   # column(width = 2,
   #        uiOutput("transcript", style = "font-size: 80%;")
   # ),
  ),
  uiOutput("main"),
  hr(),
  #footer ----
  uiOutput("footer")
)

#server----
# Define server logic
server <- function(input, output, session) {

  #Connect to the database ----
  if (Sys.info()["nodename"] == "shiny.si.edu"){
    #For RHEL7 odbc driver
    pg_driver = "PostgreSQL"
  }else if (Sys.info()["nodename"] == "OCIO-2SJKVD22"){
    #For RHEL7 odbc driver
    pg_driver = "PostgreSQL Unicode(x64)"
  }else{
    pg_driver = "PostgreSQL Unicode"
  }
  
  db <- dbConnect(odbc::odbc(),
                  driver = pg_driver,
                  database = pg_db,
                  uid = pg_user,
                  pwd = pg_pass,
                  server = pg_host,
                  port = 5432)
  
  #Encoding
  n <- dbSendQuery(db, "SET CLIENT_ENCODING TO 'UTF-8';")
  dbClearResult(n)
  
  project <- dbGetQuery(db, paste0("SELECT * FROM ocr_projects WHERE project_id = '", project_id, "'::uuid"))
  proj_name <- project$project_title
  
  
  #summary----
  output$summary <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    
    if (filename != "NULL"){req(FALSE)} 
    
    summary_query <- paste0("SELECT string_agg(DISTINCT d.ocr_source, ',') AS ocr_source, COUNT(DISTINCT d.filename)::int as no_files FROM ocr_documents d WHERE project_id = '", project_id, "'::uuid")
    summary <- dbGetQuery(db, summary_query)
    
    
    summary_query <- paste0("WITH docs AS 
                (
                    SELECT
                        document_id 
                    FROM 
                        ocr_documents 
                    WHERE
                        project_id = '", project_id, "'::uuid
                )
                    SELECT 
                        count(DISTINCT o.document_id)::int as no_docs
                    FROM 
                        ocr_blocks o,
                        docs
                    WHERE   
                        o.document_id = docs.document_id AND
                        o.confidence >= 0.7")
    summary_docs <- dbGetQuery(db, summary_query)
    
    
    summary_query <- paste0("WITH docs AS 
          (
              SELECT
                  document_id 
              FROM 
                  ocr_documents 
              WHERE
                  project_id = '", project_id, "'::uuid
          )
              SELECT 
                  count(o.*)::int as no_blocks
              FROM 
                  docs left join 
                  ocr_blocks o on (docs.document_id = o.document_id)
              WHERE   
                  o.confidence >= 0.7")
    blocks <- dbGetQuery(db, summary_query)
    
    summary_query <- paste0("WITH docs AS 
          (
              SELECT
                  document_id 
              FROM 
                  ocr_documents 
              WHERE
                  project_id = '", project_id, "'::uuid
          )
              SELECT 
                  count(o.document_id)::int as no_blocks
              FROM 
                  ocr_interpreted_blocks o,
                  docs
              WHERE   
                  o.document_id = docs.document_id")
    int_blocks <- dbGetQuery(db, summary_query)
    
    tagList(
      h3("Summary"),
      HTML(paste0("<p>OCR Source: ", summary$ocr_source, br(), "<small>Min confidence allowed: 0.70</small></p>")),
      p(paste0("Number of files: ", summary$no_files)),
      p(paste0("Number of files with successful OCR: ", summary_docs$no_docs, " (", round((summary_docs$no_docs/summary$no_files) * 100 ,2), "%)")),
      hr(),
      p(paste0("Number of total blocks of text: ", blocks$no_blocks)),
      p(paste0("Number of blocks with field assigned: ", int_blocks$no_blocks, " (", round((int_blocks$no_blocks/blocks$no_blocks) * 100 ,2), "%)"))
      
    )
  })
  
  
  
  
  
  #selectfile----
  output$selectfile <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    
    #if (filename != "NULL"){req(FALSE)}
    
    files_query <- paste0("SELECT d.filename, ROUND(AVG(e.confidence)::numeric, 4) as mean_confidence FROM ocr_documents d LEFT JOIN ocr_entries e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid GROUP BY d.filename ORDER BY mean_confidence DESC")
    filelist <- dbGetQuery(db, files_query)
    
    files <- stringr::str_replace(filelist$filename, '.jpg', '')
    
    if (length(files) > 1){
      names(files) <- paste0(filelist$filename, " (", filelist$mean_confidence, ")")
    }
    
    if (filename == "NULL"){
      sel_list <- selectInput("filename", "Select a file:", files)
    }else{
      sel_list <- selectInput("filename", "Select a file:", files, filename)
    }
    
    tagList(
      HTML(paste0("<h2><a href=\"./\">", proj_name, "</a></h2>")),
      sel_list,
      actionButton("submit_filename", "View Image")
    )
  })
  
  
  
  
  # submit_filename react ----
  observeEvent(input$submit_filename, {
    
    req(input$filename)

    output$main <- renderUI({
      HTML(paste0("<script>$(location).attr('href', './?filename=", input$filename, "')</script>"))
    })
  })
  
  
  #filetext----
  output$filetext <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    
    if (filename == "NULL"){req(FALSE)}
    
    doc_query <- paste0("SELECT document_id FROM ocr_documents WHERE project_id = '", project_id, "'::uuid AND filename = '", filename, ".jpg' LIMIT 1")
    #print(doc_query)
    doc_id <- dbGetQuery(db, doc_query)[1]

    if (length(doc_id$document_id) == 0){
      output$main <- renderUI({
        HTML(paste0("<script>$(location).attr('href', './?')</script>"))
      })
      req(FALSE)
    }
    
    file_query <- paste0("SELECT * FROM ocr_entries WHERE document_id = '", doc_id$document_id, "'::uuid")
    print(file_query)
    file_data <- dbGetQuery(db, file_query)
    
    block_html <- paste0("<small><em>Mouseover for word confidence;<br>Mean line confidence in parenthesis</em></small>")
    
    for (b in seq(min(file_data$block), max(file_data$block))){
      print(b)
      block_data <- filter(file_data, block == b)
      
      if (dim(block_data)[1] > 0){
        
        block_c_q <- paste0("SELECT confidence FROM ocr_blocks WHERE document_id = '", doc_id$document_id, "'::uuid and block = ", b)
        print(block_c_q)
        block_conf <- dbGetQuery(db, block_c_q)
        
        #blk_conf <- round(mean(as.numeric(block_data$confidence)), 4)
        blk_conf <- round(mean(as.numeric(block_conf$confidence)), 4)
        
        if (blk_conf > 0.9){
          header_color <- "success"
        }else if (blk_conf <= 0.9 && blk_conf > 0.8){
          header_color <- "warning"
        }else if (blk_conf <= 0.8 && blk_conf > 0.7){
          header_color <- "warning"
        }else{
          header_color <- "danger"
        }
        
        if (blk_conf > 0.9){
          header_color <- "#66ff33"
        }else if (blk_conf <= 0.9 && blk_conf > 0.8){
          header_color <- "#ffdb4d"
        }else if (blk_conf <= 0.8 && blk_conf > 0.7){
          header_color <- "#ffa366"
        }else{
          header_color <- "#ff6666"
        }
        
        block_q <- paste0("SELECT block_id, string_agg(data_type, ',') as data_type FROM ocr_interpreted_blocks WHERE document_id = '", doc_id$document_id, "'::uuid and block_id = ", b, " GROUP BY block_id")
        print(block_q)
        block_types <- dbGetQuery(db, block_q)
        blk_types <- "<em>NA</em>"
        if (dim(block_types)[1] == 1){
          blk_types <- paste0("<em>", block_types$data_type, "</em>")
        }
        
        #pre_txt <- paste0("<div class=\"panel panel-", header_color, "\"><div class=\"panel-heading\"><h3 class=\"panel-title\">Block type: [", blk_types, "] <small>(mean confidence: ", blk_conf, ")</small></h3></div><div class=\"panel-body\">")
        #pre_txt <- paste0("<div class=\"panel\"><div class=\"panel-heading\" style=\"background:", header_color, ";\"><h3 class=\"panel-title\">Block type: [", blk_types, "] <small>(block confidence: ", blk_conf, ")</small></h3></div><div class=\"panel-body\">")
        pre_txt <- paste0("<div class=\"panel\"><div class=\"panel-heading\" style=\"background:", header_color, ";\"><h3 class=\"panel-title\">Block confidence: ", blk_conf, "</small></h3></div><div class=\"panel-body\">")
        
        post_box <- paste0("</div></div></div>")
        line_text <- ""
        
        for (i in seq(min(block_data$word_line), max(block_data$word_line))){
          print(i)
          line_data <- filter(block_data, word_line == i)
          print(line_data)
          
          if (dim(line_data)[1] == 0){
            next
          }
          #if (dim(line_data)[1] > 1){
          
          conf <- round(mean(as.numeric(line_data$confidence)), 2)
          
          if (conf > 0.9){
            text_color <- "green"
          }else if (conf <= 0.9 && conf > 0.8){
            text_color <- "orange"
          }else{
            text_color <- "red"
          }
          
          for (j in seq(min(line_data$word), max(line_data$word))){
            this_word <- line_data[line_data$word == j,]
            line_text <- paste0(line_text, "<abbr title =\"", round(this_word$confidence, 2), "\">", this_word$word_text, "</abbr> ")
          }
          
          line_text <- paste0(line_text, " (<span style=\"color: ", text_color, "\">", conf, '</span>)<br>')
          
        }
        
        #pre_lines <- paste0(pre_lines, pre_txt, line_text, "</p>")
        
        block_html <- paste0(block_html, pre_txt, line_text)
        
        #Interpreted
        block_q <- paste0("SELECT initcap(data_type) as data_type, interpreted_value FROM ocr_interpreted_blocks WHERE document_id = '", doc_id$document_id, "'::uuid and block_id = ", b)
        print(block_q)
        int_data <- dbGetQuery(db, block_q)
        #block_info <- "Interpreted data: NA"
        if (dim(int_data)[1] > 0){
          block_info <- "Interpreted data:<ul>"
          for (n in seq(1, dim(int_data)[1])){
            block_info <- paste0(block_info, "<li>", int_data$data_type[n], ":", int_data$interpreted_value[n], "</li>")
          }
          block_info <- paste0("<em>", block_info, "</ul></em>")
          
          block_html <- paste0(block_html, "<br>", block_info)
          
        }
        
        block_html <- paste0(block_html, post_box)
      }
    }
  
    HTML(block_html)
  })
  
  
  #image----
  output$image <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    
    if (filename == "NULL"){req(FALSE)}
    
    #img <- readJPEG("www/images/bee2.jpg")
    
    tagList(
      p("Text identified in image:"),
      HTML(paste0("<img src=\"images/", filename, ".jpg\" width = \"100%\">")),
      br(),
      br(),
      p("Original image:"),
      HTML(paste0("<img src=\"images_sm/", filename, ".jpg\" width = \"100%\">"))
    )
    
    
  })
  
  
  #ocr_transcript----
  output$ocr_transcript <- DT::renderDataTable({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    
    if (filename == "NULL"){req(FALSE)}
    
    transcript_query1 <- paste0("SELECT 
                string_agg(DISTINCT a.collector, ',') as collector, 
                string_agg(DISTINCT a.verbatim_date, ',') as verbatim_date, 
                string_agg(DISTINCT a.verbatim_locality, ',') as verbatim_locality, 
                string_agg(DISTINCT a.country, ',') as country, 
                string_agg(DISTINCT a.state_territory, ',') as state_territory, 
                string_agg(DISTINCT a.district_county, ',') as district_county, 
                string_agg(DISTINCT a.precise_locality, ',') as precise_locality, 
                string_agg(DISTINCT a.elevation, ',') as elevation
            FROM 
                ocr_transcription_ento o LEFT JOIN 
                        ocr_transcription_ento_auto a ON (replace(o.filename, '.jpg', '') = a.filename)
            WHERE 
                replace(o.filename, '.jpg', '') = '", filename, "' 
            GROUP BY o.filename")
    transcript_query2 <- paste0("
            SELECT 
                collector, 
                verbatim_date, 
                verbatim_locality, 
                country, 
                state_territory, 
                district_county, 
                precise_locality, 
                elevation
            FROM 
                ocr_transcription_ento
            WHERE 
                replace(filename, '.jpg', '') = '", filename, "'")
    
    transcript_data1 <- data.frame(t(dbGetQuery(db, transcript_query1)))
    
    names(transcript_data1) <- c("Automatic Matching")
    
    transcript_data2 <- data.frame(t(dbGetQuery(db, transcript_query2)))
    
    names(transcript_data2) <- c("Manual Transcription")
    
    t_data <- cbind(transcript_data2, transcript_data1)
    
    DT::datatable(
      t_data,
      escape = FALSE,
      options = list(
        searching = FALSE,
        ordering = TRUE, 
        paging = FALSE
      ),
      rownames = TRUE,
      selection = 'none'
    ) %>% formatStyle(
      c('Automatic Matching', 'Manual Transcription'),
      backgroundColor = styleEqual(c(NA), c('#ECECEC'))
    ) 
    
    
    # 
    # #if (dim(transcript_data)[1] == 1){
    #   block_html <- paste0("<div class=\"panel panel-success\"><div class=\"panel-heading\"><h3 class=\"panel-title\">Data from Auto Detection</h3></div><div class=\"panel-body\">",
    #                        "<dl>
    #                           <dt>Collector</dt>
    #                           <dd>", transcript_data$collector, "</dd>
    #                           <dt>Date</dt>
    #                           <dd>", transcript_data$verbatim_date, "</dd>
    #                           <dt>Locality</dt>
    #                           <dd>", transcript_data$verbatim_locality, "</dd>
    #                           <dt>Country</dt>
    #                           <dd>", transcript_data$country, "</dd>
    #                           <dt>State/Territory</dt>
    #                           <dd>", transcript_data$state_territory, "</dd>
    #                           <dt>District/County</dt>
    #                           <dd>", transcript_data$district_county, "</dd>
    #                           <dt>Precise Locality</dt>
    #                           <dd>", transcript_data$precise_locality, "</dd>
    #                           <dt>Lat/Lon</dt>
    #                           <dd>", transcript_data$latitude_longitude, "</dd>
    #                           <dt>Elevation</dt>
    #                           <dd>", transcript_data$elevation, "</dd>
    #                           <dt>Other Numbers</dt>
    #                           <dd>", transcript_data$other_numbers, "</dd>
    #                         </dl>",
    #                        "</div></div></div>")
    #   
    #   HTML(block_html)
    #}
  })
  
  
  
  # #transcript----
  # output$transcript <- renderUI({
  #   query <- parseQueryString(session$clientData$url_search)
  #   filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
  #   
  #   if (filename == "NULL"){req(FALSE)}
  #   
  #   transcript_query <- paste0("SELECT * FROM ocr_transcription_ento WHERE filename = '", filename, ".jpg'")
  #   print(transcript_query)
  #   transcript_data <- dbGetQuery(db, transcript_query)
  #   
  #   if (dim(transcript_data)[1] == 1){
  #     block_html <- paste0("<div class=\"panel panel-info\"><div class=\"panel-heading\"><h3 class=\"panel-title\">Data from Transcription</h3></div><div class=\"panel-body\">",
  #                          "<dl>
  #                             <dt>Collector</dt>
  #                             <dd>", transcript_data$collector, "</dd>
  #                             <dt>Date</dt>
  #                             <dd>", transcript_data$verbatim_date, "</dd>
  #                             <dt>Locality</dt>
  #                             <dd>", transcript_data$verbatim_locality, "</dd>
  #                             <dt>Country</dt>
  #                             <dd>", transcript_data$country, "</dd>
  #                             <dt>State/Territory</dt>
  #                             <dd>", transcript_data$state_territory, "</dd>
  #                             <dt>District/County</dt>
  #                             <dd>", transcript_data$district_county, "</dd>
  #                             <dt>Precise Locality</dt>
  #                             <dd>", transcript_data$precise_locality, "</dd>
  #                             <dt>Lat/Lon</dt>
  #                             <dd>", transcript_data$latitude_longitude, "</dd>
  #                             <dt>Elevation</dt>
  #                             <dd>", transcript_data$elevation, "</dd>
  #                             <dt>Other Numbers</dt>
  #                             <dd>", transcript_data$other_numbers, "</dd>
  #                           </dl>",
  #                          "</div></div></div>")
  #     
  #     HTML(block_html)
  #   }
  # })
  
  
  
  #plot----
  output$plot <- renderPlotly({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    
    if (filename != "NULL"){req(FALSE)}
    
    #files_query <- paste0("SELECT d.filename, ROUND(AVG(e.confidence)::numeric, 4) as mean_confidence FROM ocr_documents d LEFT JOIN ocr_entries e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid GROUP BY d.filename ORDER BY mean_confidence DESC")
    files_query <- paste0("SELECT e.confidence FROM ocr_documents d LEFT JOIN ocr_blocks e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid ORDER BY confidence DESC")
    filelist <- dbGetQuery(db, files_query)
    
    #fig <- plot_ly(data = filelist, x = ~mean_confidence, height = "560") %>% 
    fig <- plot_ly(data = filelist, x = ~confidence, height = "560") %>% 
      add_histogram(nbinsx = 40) %>% 
      layout(
        title = "Histogram of text blocks by confidence value",
        xaxis = list(title = "Confidence of OCR"),
        yaxis = list(title = "No. of text blocks")
      )
    })
  
  
  
  #results_h----
  output$results_h <- renderUI({
    
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    if (filename != "NULL"){req(FALSE)}
    
    h2("Matches by reference sample size per field")
  })
  
  #results2_h----
  output$results2_h <- renderUI({
    
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    if (filename != "NULL"){req(FALSE)}
    
    h2("Matches by controlled vocabulary per field")
  })
  
  
  #results----
  output$results <- DT::renderDataTable({
  
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    if (filename != "NULL"){req(FALSE)}
    
    results_table <- data.frame()
    
    vals <- c("0.05", "0.1", "0.2")
    vals2 <- c("five", "ten", "twenty")
    
    fields <- c("collector", "verbatim_locality", "country", "state_territory", "district_county", "precise_locality", "elevation", "verbatim_date")
    
    for (j in 1:3){
      
      for (i in 1:8){
        query <- paste0("
    select 
        '", fields[i], "' as field,
        round((count(coll_t)*1.0 / count(coll_r)*1.0) * 100, 2) || '%' as percent,
        '", vals2[j], "' as cat
    FROM
        (
              SELECT 
                  replace(e.filename, '.jpg', '') as filename,
                  e.", fields[i], " as coll_r,
                  a.", fields[i], " as coll_t
              FROM
                  ocr_transcription_ento e LEFT JOIN
                      ocr_transcription_ento_auto a ON (replace(e.filename, '.jpg', '') = a.filename AND e.", fields[i], " % a.", fields[i], " AND a.reference_size = '", vals[j], "')
              WHERE 
                  e.", fields[i], " IS NOT NULL AND
                  replace(e.filename, '.jpg', '') IN (
                      SELECT 
                          filename
                      FROM 
                          ocr_auto_sample
                      WHERE 
                          reference_size = '", vals[j], "' AND
                          ref_or_test = 'test'
                  )
  ) a;")
              print(query)
              results_table <- rbind(results_table, dbGetQuery(db, query))
        }
      }
    
    res <- data.frame()
    
    for (i in 1:8){
      
      f_data <- results_table %>% filter(field == fields[i])
      
      res <- rbind(res, cbind(
              field = f_data[f_data$cat == "five",]$field,
              five = f_data[f_data$cat == "five",]$percent,
              ten = f_data[f_data$cat == "ten",]$percent,
              twenty = f_data[f_data$cat == "twenty",]$percent,
              thirty = f_data[f_data$cat == "thirty",]$percent,
              forty = f_data[f_data$cat == "forty",]$percent)
      )
      
      
    }
      
    
    
    DT::datatable(
      res,
      escape = FALSE,
      options = list(
        searching = FALSE,
        ordering = TRUE, 
        paging = TRUE
      ),
      rownames = FALSE,
      selection = 'none'
    )
  })
  
  
  
  #results2----
  output$results2 <- DT::renderDataTable({
    
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]]", "", query['filename'])
    if (filename != "NULL"){req(FALSE)}
    
    results_table <- data.frame()
    
    vals <- c("0.05", "0.1", "0.2")
    vals2 <- c("five", "ten", "twenty")
    
    fields <- c("collector", "verbatim_locality", "country", "state_territory", "district_county", "precise_locality", "elevation", "verbatim_date")
    
    for (j in 1:3){
      
      for (i in 1:8){
        query <- paste0("
    select 
        '", fields[i], "' as field,
        round((count(coll_t)*1.0 / count(coll_r)*1.0) * 100, 2) || '%' as percent,
        '", vals2[j], "' as cat
    FROM
        (
              SELECT 
                  replace(e.filename, '.jpg', '') as filename,
                  e.", fields[i], " as coll_r,
                  a.", fields[i], " as coll_t
              FROM
                  ocr_transcription_ento e LEFT JOIN
                      ocr_transcription_ento_auto_geo a ON (replace(e.filename, '.jpg', '') = a.filename AND e.", fields[i], " % a.", fields[i], " AND a.reference_size = '", vals[j], "')
              WHERE 
                  e.", fields[i], " IS NOT NULL AND
                  replace(e.filename, '.jpg', '') IN (
                      SELECT 
                          filename
                      FROM 
                          ocr_auto_sample
                      WHERE 
                          reference_size = '", vals[j], "' AND
                          ref_or_test = 'test'
                  )
  ) a;")
        print(query)
        results_table <- rbind(results_table, dbGetQuery(db, query))
      }
    }
    
    res2 <- data.frame()
    
    for (i in 1:8){
      
      f_data <- results_table %>% filter(field == fields[i])
      
      res2 <- rbind(res2, cbind(
        field = f_data[f_data$cat == "five",]$field,
        five = f_data[f_data$cat == "five",]$percent,
        ten = f_data[f_data$cat == "ten",]$percent,
        twenty = f_data[f_data$cat == "twenty",]$percent,
        thirty = f_data[f_data$cat == "thirty",]$percent,
        forty = f_data[f_data$cat == "forty",]$percent)
      )
      
      
    }
    
    
    
    DT::datatable(
      res2,
      escape = FALSE,
      options = list(
        searching = FALSE,
        ordering = TRUE, 
        paging = TRUE
      ),
      rownames = FALSE,
      selection = 'none'
    )
  })
  

  # footer ----
  output$footer <- renderUI({
    HTML(paste0("<br><div class=\"footer navbar-fixed-bottom\" style=\"background: #FFFFFF;\"><br><p>&nbsp;&nbsp;<a href=\"https://dpo.si.edu\" target = _blank>Digitization Program Office</a>, <a href=\"https://www.si.edu/ocio\" target = _blank>OCIO</a>, <a href=\"https://www.si.edu\" target = _blank>Smithsonian</a> | <a href=\"https://github.com/Smithsonian/DPO_OCR\" target = _blank>OCR Shiny Explorer</a> version ", ui_ver, "</p></div>"))
  })  
}

# Run the application 
shinyApp(ui = ui, server = server)
