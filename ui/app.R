
library(DBI)
library(shiny)
library(dplyr)
library(readr)
library(plotly)

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
           uiOutput("filetext")
    ),
    column(width = 9,
           uiOutput("image"),
           plotlyOutput("plot")
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
      h2(proj_name),
      sel_list,
      actionButton("submit_filename", "Submit")
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
        
        blk_conf <- round(mean(as.numeric(block_data$confidence)), 4)
        
        if (blk_conf > 0.9){
          header_color <- "success"
        }else if (blk_conf <= 0.9 && blk_conf > 0.8){
          header_color <- "warning"
        }else{
          header_color <- "danger"
        }
        
        block_q <- paste0("SELECT block_id, string_agg(data_type, ',') as data_type FROM ocr_interpreted_blocks WHERE document_id = '", doc_id$document_id, "'::uuid and block_id = ", b, " GROUP BY block_id")
        print(block_q)
        block_types <- dbGetQuery(db, block_q)
        blk_types <- "<em>NA</em>"
        if (dim(block_types)[1] == 1){
          blk_types <- paste0("<em>", block_types$data_type, "</em>")
        }
        
        pre_txt <- paste0("<div class=\"panel panel-", header_color, "\"><div class=\"panel-heading\"><h3 class=\"panel-title\">Block type: [", blk_types, "] <small>(mean confidence: ", blk_conf, ")</small></h3></div><div class=\"panel-body\">")
        
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
        
        #Interpreted
        block_q <- paste0("SELECT initcap(data_type) as data_type, interpreted_value FROM ocr_interpreted_blocks WHERE document_id = '", doc_id$document_id, "'::uuid and block_id = ", b)
        print(block_q)
        int_data <- dbGetQuery(db, block_q)
        block_info <- "Interpreted data: NA"
        if (dim(int_data)[1] > 0){
          block_info <- "Interpreted data:<ul>"
          for (n in seq(1, dim(int_data)[1])){
            block_info <- paste0(block_info, "<li>", int_data$data_type[n], ":", int_data$interpreted_value[n], "</li>")
          }
          block_info <- paste0(block_info, "</ul>")
        }
        
        block_html <- paste0(block_html, pre_txt, line_text, "<br><em>", block_info, "</em>", post_box)
      }
    }
  
    HTML(block_html)
  })
  
  
  output$image <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- query['filename']
    
    if (filename == "NULL"){req(FALSE)}
    
    #img <- readJPEG("www/images/bee2.jpg")
    
    HTML(paste0("<img src=\"images/", filename, ".jpg\">"))
  })
  
  
  
  
  #plot----
  output$plot <- renderPlotly({
    query <- parseQueryString(session$clientData$url_search)
    filename <- query['filename']
    
    if (filename != "NULL"){req(FALSE)}
    
    files_query <- paste0("SELECT d.filename, ROUND(AVG(e.confidence)::numeric, 4) as mean_confidence FROM ocr_documents d LEFT JOIN ocr_entries e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid GROUP BY d.filename ORDER BY mean_confidence DESC")
    filelist <- dbGetQuery(db, files_query)
    
    fig <- plot_ly(data = filelist, x = ~mean_confidence, height = "560") %>% 
      add_histogram(nbinsx = 40) %>% 
      layout(
        title = "Distribution of average confidence in each image",
        xaxis = list(title = "Average Confidence"),
        yaxis = list(title = "No. of images")
      )
    })
}

# Run the application 
shinyApp(ui = ui, server = server)
