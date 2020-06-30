function clean_elem(elem) {
  if (elem.nodeType == Node.TEXT_NODE) {
    return elem.textContent;
  }
  var nodes = Array.from(elem.childNodes);
  if (elem.tagName == "SPAN" || elem.tagName == "A" || elem.tagName == "DIV" ||
      elem.tagName == "SECTION" &&
      elem.className != "ref" && elem.className != "figure-ref") {
      return nodes.map(clean_elem).join("");
  } else if (elem.tagName == "FIGURE") {
    return "";
  } else {
    while(elem.attributes.length > 0) {
      if (elem.attributes[0].name != "class" ||
          (elem.attributes[0].value != "ref" &&
           elem.attributes[0].value != "figure-ref")) {
        elem.removeAttribute(elem.attributes[0].name);
      }
    }
    elem.innerHTML =  nodes.map(clean_elem).join("");
    return elem.outerHTML;
  }
}

var script;
if (document.title.endsWith("ScienceDirect")) {
  script = 'sciencedirect.js';
}
if (script != null) {
  s = document.createElement("script");
  s.type = "text/javascript";
  s.src = "/pyreadasset?file=scrapers/" + script;
  s.onload = scrape;
  document.head.appendChild(s);
}

var id_xhr = new XMLHttpRequest();
var abstract, figures, main_text, references, files;

function scrape() {

  /* get_identifiers should return a JSON with the following information  */
  /* {'doi': ..., 'pmid': ..., 'title': ...}.  If possible, the function  */
  /* should return all three identifiers.  If this is not possible, the   */
  /* backend will try to fetch the other identifiers from Pubmed and/or   */
  /* Crossref.  Doi is the preferred identifer, followed by pmid.  Giving */
  /* the title alone should be a last resort.                             */

  id_xhr.onload = pyr_abstract;
  var id = get_identifiers();
  id_xhr.open("POST", "/pyreadscrapi");
  id_xhr.send(JSON.stringify(id));
}

function pyr_abstract() {
  var response = JSON.parse(id_xhr.response);
  if (!have_access()) {
    window.location.replace("/pyreadredirect");
  }
  var interval = setInterval(function() {
    abstract = get_abstract();
    if (abstract) {
      clearInterval(interval);
      abstract = clean_elem(abstract);
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
      pyr_references();
    }
  }, 500);
}

function pyr_references() {
  var interval = setInterval(function() {
    references = get_references();
    if (references.length > 0 ) {
      clearInterval(interval);
      pyr_files();
    }
  }, 500);
}

function pyr_files() {
  var interval = setInterval(function() {
    files = get_files();
    if (Object.keys(files).length > 0 ) {
      clearInterval(interval);
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
