
library(DBI)
library(shiny)
library(dplyr)
library(readr)
library(plotly)
#library(tm)
#library(wordcloud)
#library(memoise)

# Settings ----
source("settings.R")


#UI
ui <- fluidPage(
  
  # Application title
  #titlePanel("OCR test"),
  uiOutput("selectfile"),
  hr(),
  fluidRow(
    column(width = 3,
           uiOutput("summary"),
           uiOutput("filetext", style = "height: 600px; overflow-y: scroll;")
    ),
    column(width = 6,
           uiOutput("image"),
           plotlyOutput("plot")
    ),
    column(width = 3,
           uiOutput("transcript")
           )
  ),
  uiOutput("main")
)

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
    filename <- query['filename']
    
    if (filename != "NULL"){req(FALSE)} 
    
    summary_query <- paste0("SELECT string_agg(DISTINCT d.ocr_source, ',') AS ocr_source, COUNT(DISTINCT d.filename) as no_files, count(e.*) as no_entries, count(distinct i.document_id) as interpreted_docs, count(i.*) as interpreted_blocks FROM ocr_documents d LEFT JOIN ocr_entries e ON (d.document_id = e.document_id) LEFT JOIN ocr_interpreted_blocks i ON (d.document_id = i.document_id) WHERE project_id = '", project_id, "'::uuid")
    summary <- dbGetQuery(db, summary_query)
    
    summary_query <- paste0("select count(*) as interpreted_blocks FROM (
                    SELECT i.document_id, i.block_id FROM ocr_documents d 
                      LEFT JOIN ocr_interpreted_blocks i ON (d.document_id = i.document_id) 
                      WHERE d.project_id = '", project_id, "'::uuid
                      GROUP BY i.document_id, i.block_id) a")
    interpreted <- dbGetQuery(db, summary_query)
    
    tagList(
      h3("Summary"),
      p(paste0("OCR Source: ", summary$ocr_source)),
      p(paste0("Number of files: ", summary$no_files)),
      p(paste0("Number of files with fields assigned: ", summary$interpreted_docs, " (", round((summary$interpreted_docs/summary$no_files) * 100 ,2), "%)")),
      hr(),
      p(paste0("Number of total blocks of text: ", summary$no_entries)),
      p(paste0("Number of blocks with field assigned: ", interpreted$interpreted_blocks, " (", round((interpreted$interpreted_blocks/summary$no_entries) * 100 ,2), "%)"))
      
    )
  })
  
  
  #selectfile----
  output$selectfile <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- query['filename']
    
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
    filename <- query['filename']
    
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
        pre_txt <- paste0("<div class=\"panel\"><div class=\"panel-heading\" style=\"background:", header_color, ";\"><h3 class=\"panel-title\">Block type: [", blk_types, "] <small>(block confidence: ", blk_conf, ")</small></h3></div><div class=\"panel-body\">")
        
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
    filename <- query['filename']
    
    if (filename == "NULL"){req(FALSE)}
    
    #img <- readJPEG("www/images/bee2.jpg")
    
    HTML(paste0("<img src=\"images/", filename, ".jpg\">"))
  })
  
  
  #transcript----
  output$transcript <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- query['filename']
    
    if (filename == "NULL"){req(FALSE)}
    
    transcript_query <- paste0("SELECT * FROM ocr_transcription_ento WHERE filename = '", filename, ".jpg'")
    print(transcript_query)
    transcript_data <- dbGetQuery(db, transcript_query)
    
    if (dim(transcript_data)[1] == 1){
      block_html <- paste0("<div class=\"panel panel-info\"><div class=\"panel-heading\"><h3 class=\"panel-title\">Data from Transcription</h3></div><div class=\"panel-body\">",
                           "<dl>
                              <dt>Collector</dt>
                              <dd>", transcript_data$collector, "</dd>
                              <dt>Date</dt>
                              <dd>", transcript_data$verbatim_date, "</dd>
                              <dt>Locality</dt>
                              <dd>", transcript_data$verbatim_locality, "</dd>
                              <dt>Country</dt>
                              <dd>", transcript_data$country, "</dd>
                              <dt>State/Territory</dt>
                              <dd>", transcript_data$state_territory, "</dd>
                              <dt>District/County</dt>
                              <dd>", transcript_data$district_county, "</dd>
                              <dt>Precice Locality</dt>
                              <dd>", transcript_data$precice_locality, "</dd>
                              <dt>Lat/Lon</dt>
                              <dd>", transcript_data$latitude_longitude, "</dd>
                              <dt>Elevation</dt>
                              <dd>", transcript_data$Elevation, "</dd>
                              <dt>Other Numbers</dt>
                              <dd>", transcript_data$other_numbers, "</dd>
                              <dt>Label Notes</dt>
                              <dd>", transcript_data$label_notes, "</dd>
                            </dl>",
                           "</div></div></div>")
      
      HTML(block_html)
    }
  })
  
  
  
  #plot----
  output$plot <- renderPlotly({
    query <- parseQueryString(session$clientData$url_search)
    filename <- query['filename']
    
    if (filename != "NULL"){req(FALSE)}
    
    #files_query <- paste0("SELECT d.filename, ROUND(AVG(e.confidence)::numeric, 4) as mean_confidence FROM ocr_documents d LEFT JOIN ocr_entries e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid GROUP BY d.filename ORDER BY mean_confidence DESC")
    files_query <- paste0("SELECT e.confidence FROM ocr_documents d LEFT JOIN ocr_entries e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid ORDER BY confidence DESC")
    filelist <- dbGetQuery(db, files_query)
    
    #fig <- plot_ly(data = filelist, x = ~mean_confidence, height = "560") %>% 
    fig <- plot_ly(data = filelist, x = ~confidence, height = "560") %>% 
      add_histogram(nbinsx = 40) %>% 
      layout(
        title = "Distribution of confidence of the OCR by text block",
        xaxis = list(title = "Confidence of OCR"),
        yaxis = list(title = "No. of text blocks")
      )
    })
  
  
  
}

# Run the application 
shinyApp(ui = ui, server = server)
