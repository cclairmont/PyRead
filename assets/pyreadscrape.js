function clean_elem(elem) {
  var result;
  if (elem.nodeType == Node.TEXT_NODE) {
    return elem.textContent;
  }
  var nodes = Array.from(elem.childNodes);
  if (elem.tagName == "A" || elem.tagName == "DIV" ||
      elem.tagName == "SECTION" ||
      (elem.tagName == "SPAN" && elem.className != "ref" &&
       elem.className != "figure-ref")) {
    result = nodes.map(clean_elem).join("");
  } else if (elem.tagName == "FIGURE") {
    result = "<figure></figure>";
  } else {
    num_attributes = 0;
    while(elem.attributes.length > num_attributes) {
      if (elem.attributes[0].name != "class" ||
          (elem.attributes[0].value != "ref" &&
           elem.attributes[0].value != "figure-ref")) {
        elem.removeAttribute(elem.attributes[0].name);
      } else {
        num_attributes++;
      }
    }
    elem.innerHTML =  nodes.map(clean_elem).join("");
    result = elem.outerHTML;
  }
  result = result.replace(/\((<span[^>]*>[^\)^\(]*<\/span>)\)/g, "$1");
  return result;
}

window.onload = scrape;

var id_xhr = new XMLHttpRequest();
var abs_xhr = new XMLHttpRequest();
var fig_xhr = new XMLHttpRequest();
var main_xhr = new XMLHttpRequest();
var ref_xhr = new XMLHttpRequest();
var file_xhr = new XMLHttpRequest();
var abstract, figures, main_text, references, files, id;

function scrape() {

  /* get_identifiers should return a JSON with the following information  */
  /* {'doi': ..., 'pmid': ..., 'title': ...}.  If possible, the function  */
  /* should return all three identifiers.  If this is not possible, the   */
  /* backend will try to fetch the other identifiers from Pubmed and/or   */
  /* Crossref.  Doi is the preferred identifer, followed by pmid.  Giving */
  /* the title alone should be a last resort.                             */

  id_xhr.onload = pyr_abstract;
  id = get_identifiers();
  id_xhr.open("POST", "/pyreadscrapi");
  id_xhr.send(JSON.stringify({"doi": id.doi, "info": true}));
}

function pyr_abstract() {
  var response = JSON.parse(id_xhr.response);
  if (!have_access()) {
    window.location.replace("/pyreadredirect?doi=" + id.doi);
  }
  var interval = setInterval(function() {
    abstract = get_abstract();
    if (abstract) {
      clearInterval(interval);
      abstract = clean_elem(abstract);
      abs_xhr.open("POST", "/pyreadscrapi");
      abs_xhr.send(JSON.stringify({"doi": id.doi, "abstract": abstract}));
      pyr_figures();
    }
  }, 500);
}

function pyr_figures() {
  var interval = setInterval(function() {
    figures = get_figures();
    if (figures.length > 0 && (figures.length > 1 ||
                               figures[0].title != "Graphical Abstract")) {
      clearInterval(interval);
      for (var i = 0; i < figures.length; i++) {
        if (figures[i].legend) {
          figures[i].legend = clean_elem(figures[i].legend);
        }
      }
      fig_xhr.open("POST", "/pyreadscrapi");
      fig_xhr.send(JSON.stringify({"doi": id.doi, "figures": figures}));
      pyr_content();
    }
  }, 500);
}

function pyr_content() {
  var interval = setInterval(function() {
    main_text = get_content();
    if (main_text.length > 0 ) {
      clearInterval(interval);
      for (var i = 0; i < main_text.length; i++) {
        if (main_text[i].content.length) {
          for (var j = 0; j < main_text[i].content.length; j++) {
            main_text[i].content[j].content =
              clean_elem(main_text[i].content[j].content);
          }
        } else {
          main_text[i].content = clean_elem(main_text[i].content);
        }
      }
      main_xhr.open("POST", "/pyreadscrapi");
      main_xhr.send(JSON.stringify({"doi": id.doi, "main": main_text}));
      pyr_references();
    }
  }, 500);
}

function pyr_references() {
  var interval = setInterval(function() {
    references = get_references();
    if (references.length > 0 ) {
      clearInterval(interval);
      ref_xhr.open("POST", "/pyreadscrapi");
      ref_xhr.send(JSON.stringify({"doi": id.doi, "references": references}));
      pyr_files();
    }
  }, 500);
}

function pyr_files() {
  var interval = setInterval(function() {
    files = get_files();
    if (Object.keys(files).length > 0 ) {
      clearInterval(interval);
      file_xhr.open("POST", "/pyreadscrapi");
      file_xhr.send(JSON.stringify({"doi": id.doi, "files": files}));
      show_results();
    }
  }, 500);
}

function show_results() {
  console.log(abstract);
  console.log(figures);
  console.log(main_text);
  console.log(references);
  console.log(files);
}
