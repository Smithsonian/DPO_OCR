
library(DBI)
library(shiny)
library(dplyr)
library(readr)
library(plotly)
library(DT)


# Settings ----
source("settings.R")
ui_ver <- "0.2.1"


#UI----
ui <- fluidPage(
  
  # Application title
  #titlePanel("OCR test"),
  uiOutput("selectfile"),
  hr(),
  tags$style(HTML("
                  #filetext {
                    height:600px;
                    overflow-y:scroll
                  }
                  ")),
  fluidRow(
    column(width = 2,
           uiOutput("summary"),
           uiOutput("filetext")
           #,
           #plotlyOutput("plot")
    ),
    column(width = 10,
           #uiOutput("results_h"),
           
           #DT::dataTableOutput("results"),
           # uiOutput("results2_h"),
           # DT::dataTableOutput("results2"),
           uiOutput("image"),
           plotlyOutput("plot")
    )#,
   # column(width = 4,
   #        #uiOutput("ocr_transcript", style = "font-size: 80%;")
   #        DT::dataTableOutput("ocr_transcript")
   # )
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
    #For Ubuntu odbc driver
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
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
    
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
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
    
    #if (filename != "NULL"){req(FALSE)}
    
    files_query <- paste0("SELECT d.filename, ROUND(AVG(e.confidence)::numeric, 4) as mean_confidence FROM ocr_documents d LEFT JOIN ocr_entries e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid GROUP BY d.filename ORDER BY mean_confidence DESC NULLS LAST")
    filelist <- dbGetQuery(db, files_query)
    
    files <- stringr::str_replace(filelist$filename, '.jpg', '')
    
    if (length(files) > 1){
      names(files) <- paste0(filelist$filename, " (", filelist$mean_confidence, ")")
    }
    
    if (filename == "NULL"){
      #sel_list <- selectInput("filename", "Select a file:", files)
      sel_list <- selectInput("filename", "Select a file:", choices = NULL)
    }else{
      #sel_list <- selectInput("filename", "Select a file:", files, filename)
      sel_list <- selectInput("filename", "Select a file:", filename, choices = NULL)
    }
    
    if (filename == "NULL"){
      updateSelectizeInput(session, 'filename', choices = files, server = TRUE)
    }else{
      updateSelectizeInput(session, 'filename', choices = files, selected = filename, server = TRUE)
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
    #Sanitize input
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
    
    if (filename == "NULL"){req(FALSE)}
    
    #doc_query <- paste0("SELECT document_id FROM ocr_documents WHERE project_id = '", project_id, "'::uuid AND filename = '", filename, ".jpg' LIMIT 1")
    #print(doc_query)
    doc_id <- dbGetQuery(db, "SELECT document_id FROM ocr_documents WHERE project_id = ? AND filename = ? LIMIT 1", params = c(project_id, paste0(filename, '.jpg')))
    #doc_id <- dbGetQuery(db, doc_query)[1]

    if (length(doc_id$document_id) == 0){
      output$main <- renderUI({
        HTML(paste0("<script>$(location).attr('href', './?')</script>"))
      })
      req(FALSE)
    }
    
    file_query <- paste0("SELECT * FROM ocr_entries WHERE document_id = '", doc_id$document_id, "'::uuid")
    print(file_query)
    file_data <- dbGetQuery(db, file_query)
    
    block_html <- ""
    
    imagemap <- "<map name=\"workmap\">"
    
    if (length(file_data$block) > 0){
    
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
        print("block_q")
        block_types <- dbGetQuery(db, block_q)
        blk_types <- "<em>NA</em>"
        if (dim(block_types)[1] == 1){
          blk_types <- paste0("<em>", block_types$data_type, "</em>")
        }
        
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
            print("this_word")
            print(this_word)
            #imagemap entries----
            imagemap <- paste0(imagemap, "<area shape=\"rect\" coords=\"", this_word$vertices_x_0, ",", this_word$vertices_y_0, ",", this_word$vertices_x_2, ",", this_word$vertices_y_2, "\" alt=\"", this_word$word_text, " (", round(this_word$confidence, 2), ")\" title=\"", this_word$word_text, " (", round(this_word$confidence, 2), ")\" alt=\"", this_word$word_text, " (", round(this_word$confidence, 2), ")\" style=\"border-style: dotted;\">\n")
            
          }
          
          line_text <- paste0(line_text, " (<span style=\"color: ", text_color, "\">", conf, '</span>)<br>')
          
        }
        
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
    
    }else{
      block_html <- paste0(block_html, "<p><em>No text was identified.</em></p>")
    }
    
    
    imagemap <- paste0(imagemap, "</map>")
    
    tagList(
      HTML(imagemap),
      HTML(block_html)
    )
    
  })
  
  
  #image----
  output$image <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
    
    if (filename == "NULL"){req(FALSE)}
    
    tagList(
      HTML(paste0("<img src=\"", image_annotated_url, "?file=", filename, "&project=", project_id, "\" usemap=\"#workmap\">")),
      br(),
      br(),
      p("Original image:"),
      HTML(paste0("<img src=\"", image_url, "?file=", filename, "&project=", project_id, "\" width = \"", image_width, "\">"))
    )
    
  })
  
  

  
  #plot----
  output$plot <- renderPlotly({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
    
    if (filename != "NULL"){req(FALSE)}
    
    files_query <- paste0("SELECT e.confidence FROM ocr_documents d LEFT JOIN ocr_blocks e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid ORDER BY confidence DESC")
    filelist <- dbGetQuery(db, files_query)
    
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
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
    if (filename != "NULL"){req(FALSE)}
    
    h2("Matches by reference sample size per field")
  })
  
  #results2_h----
  output$results2_h <- renderUI({
    
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
    if (filename != "NULL"){req(FALSE)}
    
    h2("Matches by controlled vocabulary per field")
  })
  
  
  #results----
  output$results <- DT::renderDataTable({
  
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
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
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
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
