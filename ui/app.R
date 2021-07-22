
library(DBI)
library(shiny)
library(dplyr)
library(readr)
library(plotly)
library(DT)
library(futile.logger)
library(shinycssloaders)

flog.logger("log", DEBUG, appender=appender.file(paste0("logs/", format(Sys.time(), "%Y-%m-%d_%H%M%S"), '.log')))

# Settings ----
source("settings.R")

app_name <- "Zonal OCR"
app_ver <- "0.2.3"
github_link <- "https://github.com/Smithsonian/DPO_OCR"


flog.info(app_ver, name='log')

#UI----
ui <- fluidPage(
  
  # Application title
  fluidRow(
    column(width = 4,
            uiOutput("selectfile")
    ),
    column(width = 3,
           shinycssloaders::withSpinner(uiOutput("summary"))
    ),
    column(width = 5,
           plotlyOutput("plot", height = 200)
    )
  ),
  hr(),
  tags$style(HTML("
                  #image {
                    height:600px;
                    overflow-y:scroll;
                  }
                  ")),
  tags$style(HTML("
                  #filetext {
                    height:600px;
                    overflow-y:scroll;
                  }
                  ")),
  fluidRow(
    column(width = 4,
           uiOutput("results_h"),
           shinycssloaders::withSpinner(DT::dataTableOutput("resultstable")),
           uiOutput("filetext")
    ),
    column(width = 8, 
           uiOutput("image")
           
    )
  ),
  uiOutput("main"),
  hr(),
  
  #footer ----
  HTML(paste0("<br><br><br><br><div class=\"footer navbar-fixed-bottom\" style = \"background: white;\"><br><p>&nbsp;&nbsp;<a href=\"http://dpo.si.edu\" target = _blank><img src=\"DPO_logo_300.png\"></a> | ", app_name, ", ver. ", app_ver, " | <a href=\"", github_link, "\" target = _blank>Source code</a></p></div>"))
  
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
  
  flog.debug(proj_name, name='log')
  
  #summary----
  output$summary <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['filename'])
    
    if (filename != "NULL"){req(FALSE)} 
    
    summary_query <- paste0("SELECT string_agg(DISTINCT d.ocr_source, ',') AS ocr_source, COUNT(DISTINCT d.filename)::int as no_files FROM ocr_documents d WHERE project_id = '", project_id, "'::uuid")
    summary <- dbGetQuery(db, summary_query)
    
    flog.debug(paste("summary", summary, sep = ":"), name='log')
    
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
    flog.debug(paste("summary_docs", summary_docs, sep = ":"), name='log')
    
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
    flog.debug(paste("blocks", blocks, sep = ":"), name='log')
    
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
    
    if (int_blocks$no_blocks == 0){
      field_html <- ""
    }else{
      field_html <- p(paste0("Number of blocks with field assigned: ", int_blocks$no_blocks, " (", round((int_blocks$no_blocks/blocks$no_blocks) * 100 ,2), "%)"))
    }
    
    tagList(
      h3("Summary"),
      #HTML(paste0("<p>OCR Source: ", summary$ocr_source, br(), "<small>Min confidence allowed: 0.70</small></p>")),
      HTML(paste0("<p><small>OCR Source: ", summary$ocr_source, br(), "Number of files: ", summary$no_files, br(), "Number of files with successful OCR: ", summary_docs$no_docs, " (", round((summary_docs$no_docs/summary$no_files) * 100 ,2), "%)")),
      br(),
      paste0("Number of total blocks of text: ", blocks$no_blocks),
      field_html
      
    )
  })
  
  
  
  
  
  #selectfile----
  output$selectfile <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    filename <- gsub("[^[:alnum:][:space:]][_]", "", query['document_id'])
    
    #if (filename != "NULL"){req(FALSE)}
    
    files_query <- paste0("SELECT d.document_id, d.filename, ROUND(AVG(e.confidence)::numeric, 4) as mean_confidence FROM ocr_documents d LEFT JOIN ocr_entries e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid GROUP BY d.document_id, d.filename ORDER BY d.filename ASC")
    filelist <- dbGetQuery(db, files_query)
    
    files <- filelist$document_id
    
    if (length(files) > 1){
      names(files) <- paste0(filelist$filename, " (", filelist$mean_confidence, ")")
    }
    
    if (filename == "NULL"){
      sel_list <- selectInput("document_id", "Select a file:", choices = NULL)
    }else{
      sel_list <- selectInput("document_id", "Select a file:", filename, choices = NULL)
    }
    
    if (filename == "NULL"){
      updateSelectizeInput(session, 'document_id', choices = files, server = TRUE)
    }else{
      updateSelectizeInput(session, 'document_id', choices = files, selected = filename, server = TRUE)
    }
    
    tagList(
      HTML(paste0("<h2><a href=\"./\">", proj_name, "</a></h2>")),
      sel_list,
      actionButton("submit_filename", "View Image")
    )
  })
  
  
  # submit_filename react ----
  observeEvent(input$submit_filename, {
    
    req(input$document_id)

    output$main <- renderUI({
      HTML(paste0("<script>$(location).attr('href', './?document_id=", input$document_id, "')</script>"))
    })
  })
  
  
  #filetext----
  output$filetext <- renderUI({
    query <- parseQueryString(session$clientData$url_search)
    #Sanitize input
    document_id <- gsub("[^[:alnum:][:space:]][_]", "", query['document_id'])
    
    if (document_id == "NULL"){req(FALSE)}
    
    img_width <- gsub("[^[:digit:]]", "", query['img_width'])
    
    if (img_width == ""){
      img_width <- default_image_width
    }
    
    flog.debug(paste("document_id", document_id, sep = ":"), name='log')
    flog.debug(paste("img_width", img_width, sep = ":"), name='log')
    
    doc_id <- dbGetQuery(db, "SELECT document_id, doc_width, doc_height FROM ocr_documents WHERE project_id = ? AND document_id = ? LIMIT 1", params = c(project_id, document_id))
    
    flog.debug(paste("doc_id", doc_id, sep = ":"), name='log')
    
    if (length(doc_id$document_id) == 0){
      output$main <- renderUI({
        HTML(paste0("<script>$(location).attr('href', './?')</script>"))
      })
      req(FALSE)
    }
    
    img_width_scale <- round(as.numeric(img_width)/as.numeric(doc_id$doc_width), 3)
    
    flog.debug(paste("img_width_scale", img_width_scale, sep = ":"), name='log')
    
    file_query <- paste0("SELECT * FROM ocr_entries WHERE document_id = '", doc_id$document_id, "'::uuid")
    file_data <- dbGetQuery(db, file_query)
    
    flog.debug(paste("file_data", file_data, sep = ":"), name='log')
    
    block_html <- ""
    
    imagemap <- "<map name=\"workmap\" style=\"visibility: hidden; width: 0px;\">"
    
    if (length(file_data$block) > 0){
    
      block_html <- paste0("<p><small><em>Mouseover for word confidence;<br>Mean line confidence in parenthesis</em></small></p>")
      
      for (b in seq(min(file_data$block), max(file_data$block))){
        block_data <- filter(file_data, block == b)
        
        flog.debug(paste("block_data", block_data, sep = ":"), name='log')
        
        if (dim(block_data)[1] > 0){
          
          block_c_q <- paste0("SELECT confidence FROM ocr_blocks WHERE document_id = '", doc_id$document_id, "'::uuid and block = ", b)
          block_conf <- dbGetQuery(db, block_c_q)
          
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
          block_types <- dbGetQuery(db, block_q)
          
          blk_types <- "<em>NA</em>"
          if (dim(block_types)[1] == 1){
            blk_types <- paste0("<em>", block_types$data_type, "</em>")
          }
          
          pre_txt <- paste0("<div class=\"panel\"><div class=\"panel-heading\" style=\"background:", header_color, ";\"><h3 class=\"panel-title\">Block confidence: ", blk_conf, "</small></h3></div><div class=\"panel-body\">")
          
          post_box <- paste0("</div></div></div>")
          line_text <- ""
          
          for (i in seq(min(block_data$word_line), max(block_data$word_line))){
            line_data <- filter(block_data, word_line == i)
            flog.debug(paste("line_data", line_data, sep = ":"), name='log')
            
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
              
              flog.debug(paste("this_word", this_word, sep = ":"), name='log')
              flog.debug(paste("img_width_scale", img_width_scale, sep = ":"), name='log')
              
              #imagemap entries----
              imagemap <- paste0(imagemap, 
                                 "<area shape=\"rect\" coords=\"", 
                                 round(as.numeric(this_word$vertices_x_0) * img_width_scale, 0), 
                                 ",", 
                                 round(as.numeric(this_word$vertices_y_0) * img_width_scale, 0), 
                                 ",", 
                                 round(as.numeric(this_word$vertices_x_2) * img_width_scale, 0), 
                                 ",", 
                                 round(as.numeric(this_word$vertices_y_2) * img_width_scale, 0), 
                                 "\" alt=\"", 
                                 this_word$word_text, 
                                 " (", 
                                 round(this_word$confidence, 2), 
                                 ")\" title=\"", 
                                 this_word$word_text, 
                                 " (", 
                                 round(this_word$confidence, 2), 
                                 ")\" alt=\"", 
                                 this_word$word_text, 
                                 " (", 
                                 round(this_word$confidence, 2), 
                                 ")\" style=\"border-style: dotted;\">\n"
                                )
              
            }
            
            line_text <- paste0(line_text, " (<span style=\"color: ", text_color, "\">", conf, '</span>)<br>')
            
          }
          
          block_html <- paste0(block_html, pre_txt, line_text)
          
          #Interpreted
          block_q <- paste0("SELECT initcap(data_type) as data_type, interpreted_value FROM ocr_interpreted_blocks WHERE document_id = '", doc_id$document_id, "'::uuid and block_id = ", b)
          int_data <- dbGetQuery(db, block_q)
          flog.debug(paste("int_data", int_data, sep = ":"), name='log')
          
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
    document_id <- gsub("[^[:alnum:][:space:]][_]", "", query['document_id'])
    
    if (document_id == "NULL"){req(FALSE)}
    
    img_width <- gsub("[^[:digit:]]", "", query['img_width'])
    
    if (img_width == ""){
      img_width <- default_image_width
    }
    
    filename <- dbGetQuery(db, "SELECT filename, doc_version, doc_section FROM ocr_documents WHERE project_id = ? AND document_id = ? LIMIT 1", params = c(project_id, document_id))
    
    tagList(
      p("Annotated image:"),
      HTML(paste0("<img src=\"", image_annotated_url, "?file=", filename$filename, "&project=", project_id, "&width=", img_width, "&version=", filename$doc_version, "&section=", filename$doc_section, "\" width = \"", img_width, "\" usemap=\"#workmap\">"))#,
    #   br(),
    #   br(),
    #   p("Original image:"),
    #   HTML(paste0("<img src=\"", image_url, "?file=", filename$filename, "&version=", filename$doc_version, "&project=", project_id, "&section=", filename$doc_section, "\" width = \"", img_width, "\">"))
    )
    
  })
  
  

  
  #plot----
  output$plot <- renderPlotly({
    query <- parseQueryString(session$clientData$url_search)
    document_id <- gsub("[^[:alnum:][:space:]][_]", "", query['document_id'])
    
    #if (document_id != "NULL"){req(FALSE)}
    
    files_query <- paste0("SELECT e.confidence FROM ocr_documents d LEFT JOIN ocr_blocks e ON (d.document_id = e.document_id) WHERE project_id = '", project_id, "'::uuid ORDER BY confidence DESC")
    filelist <- dbGetQuery(db, files_query)
    
    fig <- plot_ly(data = filelist, x = ~confidence, height = "200") %>% 
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
    document_id <- gsub("[^[:alnum:][:space:]][_]", "", query['document_id'])
    if (document_id == "NULL"){req(FALSE)}
    
    h3("Detected data by field and row")
  })
  
 
  
  
  
  
  
  #results_filename----
  results_filename <- reactive({
    
    query <- parseQueryString(session$clientData$url_search)
    document_id <- gsub("[^[:alnum:][:space:]][_]", "", query['document_id'])
    if (document_id == "NULL"){req(FALSE)}
    
    document_id
  })
  
  
  
  #datasetCSV ----
  datasetCSV <- reactive({
    
    query <- parseQueryString(session$clientData$url_search)
    document_id <- gsub("[^[:alnum:][:space:]][_]", "", query['document_id'])
    if (document_id == "NULL"){req(FALSE)}
    
    if (project_type == "coordinates"){
      
      data_rows <- dbGetQuery(db, paste0("SELECT DISTINCT z.row_no FROM ocr_zones z, ocr_documents d WHERE d.document_id = '", document_id, "' AND  z.doc_version = d.doc_version AND z.doc_section = d.doc_section AND z.row_no != 999"))
      
      data_cols <- dbGetQuery(db, paste0("SELECT z.field_name, z.field_order FROM ocr_zones z, ocr_documents d WHERE d.document_id = '", document_id, "' AND  z.doc_version = d.doc_version AND z.doc_section = d.doc_section AND z.row_no != 999 GROUP BY z.field_name, z.field_order ORDER BY z.field_order"))
      
      doc_info <- dbGetQuery(db, paste0("SELECT filename, doc_version, doc_section FROM ocr_documents WHERE document_id = '", document_id, "'"))
      
      data <- data.frame(matrix(ncol = 4 + length(data_cols$field_name), data = NA), stringsAsFactors = FALSE)
      
      data_row <- cbind("filename", "doc_version", "doc_section", "row_no")
      for (j in seq(1:length(data_cols$field_name))){
        data_row <- cbind(data_row, data_cols$field_name[j])
      }
      
      data[1,] <- data_row
      data[2:(length(data_rows$row_no) + 1),1] <- doc_info$filename
      data[2:(length(data_rows$row_no) + 1),2] <- doc_info$doc_version
      data[2:(length(data_rows$row_no) + 1),3] <- doc_info$doc_section
      
      
      for (i in seq(1:length(data_rows$row_no))){
        data[i+1, 4] <- data_rows$row_no[i]
      }
      
      for (i in seq(1:length(data_rows$row_no))){
        for (j in seq(1:length(data_cols$field_name))){
          
          data_cell <- dbGetQuery(db, paste0("SELECT d.word_text FROM ocr_zonal_data d, ocr_zones z WHERE d.zone_id = z.zone_id AND d.document_id = '", document_id, "' AND z.row_no = ", data_rows$row_no[i], " AND field_name = '", data_cols$field_name[j], "'"))
          
          if (dim(data_cell)[1] == 1){
            data[i+1, j+4] <- data_cell
          }
        }
      }
      
      names(data) <- data[1,]
      data <- data[2:dim(data)[1],]
      
    }else{
      
      data_rows <- dbGetQuery(db, paste0("SELECT DISTINCT z.row_no FROM ocr_zones z, ocr_documents d WHERE d.document_id = '", document_id, "' AND  z.doc_version = d.doc_version AND z.doc_section = d.doc_section AND z.row_no != 999"))
      
      data_cols <- dbGetQuery(db, paste0("SELECT z.field_name, z.field_order FROM ocr_zones z, ocr_documents d WHERE d.document_id = '", document_id, "' AND  z.doc_version = d.doc_version AND z.doc_section = d.doc_section AND z.row_no != 999 GROUP BY z.field_name, z.field_order ORDER BY z.field_order"))
      
      doc_info <- dbGetQuery(db, paste0("SELECT filename, doc_version, doc_section FROM ocr_documents WHERE document_id = '", document_id, "'"))
      
      data <- data.frame(matrix(ncol = 4 + length(data_cols$field_name), data = NA), stringsAsFactors = FALSE)
      
      data_row <- cbind("filename", "doc_version", "doc_section", "row_no")
      for (j in seq(1:length(data_cols$field_name))){
        data_row <- cbind(data_row, data_cols$field_name[j])
      }
      
      data[1,] <- data_row
      data[2:(length(data_rows$row_no) + 1),1] <- doc_info$filename
      data[2:(length(data_rows$row_no) + 1),2] <- doc_info$doc_version
      data[2:(length(data_rows$row_no) + 1),3] <- doc_info$doc_section
      
      
      for (i in seq(1:length(data_rows$row_no))){
        data[i+1, 4] <- data_rows$row_no[i]
      }
      
      for (i in seq(1:length(data_rows$row_no))){
        for (j in seq(1:length(data_cols$field_name))){
          
          data_cell <- dbGetQuery(db, paste0("SELECT d.word_text FROM ocr_zonal_data d, ocr_zones z WHERE d.zone_id = z.zone_id AND d.document_id = '", document_id, "' AND z.row_no = ", data_rows$row_no[i], " AND field_name = '", data_cols$field_name[j], "'"))
          
          if (dim(data_cell)[1] == 1){
            data[i+1, j+4] <- data_cell
          }
        }
      }
      
      names(data) <- data[1,]
      data <- data[2:dim(data)[1],]
    }
    
    data
    
  })
  
  
  
  #resultstable ----
  output$resultstable <- DT::renderDataTable({
    query <- parseQueryString(session$clientData$url_search)
    document_id <- gsub("[^[:alnum:][:space:]][_]", "", query['document_id'])
    if (document_id == "NULL"){req(FALSE)}
    
    if (project_type != "coordinates"){req(FALSE)}
    
    DT::datatable(
      datasetCSV(),
      extensions = 'Buttons',
      escape = FALSE, 
      options = list(
        columnDefs = list(list(visible = FALSE, targets = table_hiddencols)),
        paging = FALSE,
        searching = FALSE,
        fixedColumns = TRUE,
        autoWidth = FALSE,
        ordering = TRUE,
        dom = 'Bfrtip',
        buttons = list(list(extend = 'csv', filename = document_id, title = NULL),list(extend = 'excel', title = NULL, filename = document_id)),
        pageLength = table_pagelength
      ),
      selection = 'none',
      rownames = FALSE,
      class = "display"
    )
  }, server = FALSE)
  
  
}


# Run the application 
shinyApp(ui = ui, server = server)
