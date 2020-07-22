/*jshint esversion: 6 */

function handle_figs_refs(elem) {
  if (elem.length != null) {
    return elem.map(handle_figs_refs);
  }
  var class_names = handlers.map(a => a.class);

  for (var h of handlers) {
    var refs = h.selector(elem);
    for (var i = 0; i < refs.length; i++) {
      var new_ref = document.createElement("span");
      new_ref.className = h.class;
      var nodes = [refs[i]];
      var text = refs[i].textContent;
      var m, pm;
      var matched = false;
      while(true) {
        if (text == "") {
          matched = true;
          break;
        }
        text = text.replace("–", "-");
        text = text.replace("&nbsp;", " ");
        m = h.matcher(text);
        if (m != null) {
          if (!matched) {
            matched = true;
          } else if (m.length == pm.length) {
            break;
          }
          pm = m;
        }
        var prev = nodes[0].previousSibling;
        var next = nodes[nodes.length - 1].nextSibling;
        if (prev != null && (i == 0 || !prev.isSameNode(refs[i - 1]))) {
          nodes.unshift(prev);
          text = prev.textContent + text;
        } else {
          prev = null;
        }
        if (next != null && (i == refs.length - 1 ||
                             !next.isSameNode(refs[i + 1]))) {
          nodes.push(next);
          text = text + next.textContent;
        } else {
          next = null;
        }
        console.log(prev, next);
        if (prev == null && next == null) {
          break;
        }
      }
      if (matched) {
        if (m == null) {
          new_ref.dataset.refnum = h.num(refs[i], "");
          refs[i].replaceWith(new_ref);
          continue;
        }
        console.log(text);
        console.log(m);
        var start = text.indexOf(m);
        console.log(nodes);
        for (var j = 0; j < nodes.length; j++) {
          console.log("start", start);
          if (start < nodes[j].textContent.length) {
            var end = start + m.length;
            for (var k = j; k < nodes.length; k++) {
              console.log("end", end);
              if (end <= nodes[k].textContent.length) {
                if (k > j) {
                  console.log("j", nodes[j].textContent);
                  console.log("k", nodes[k].textContent);
                  nodes[k].textContent = nodes[k].textContent.slice(end);
                  nodes[j].textContent = nodes[j].textContent.slice(0, start);
                  for (var n = j + 1; n < k; n++) {
                    console.log("n", nodes[n].textContent);
                    nodes[n].textContent = "";
                  }
                } else {
                  console.log(start, end);
                  nodes[k].textContent = nodes[k].textContent.slice(0, start) +
                                         nodes[k].textContent.slice(end);
                }
                break;
              }
              end -= nodes[k].textContent.length;
            }
            break;
          }
          start -= nodes[j].textContent.length;
        }
        new_ref.dataset.refnum = h.num(refs[i], m);
        refs[i].replaceWith(new_ref);
      }
    }
  }
  return elem;
}

function clean_elem(elem) {
  if (elem == null) {
    return null;
  }
  var result;
  if (elem.nodeType == Node.TEXT_NODE) {
    return elem.textContent;
  }
  var nodes;
  if (elem.nodeType == null) {
    nodes = Array.from(elem);
    if (nodes.length == 1) {
      nodes = [];
    }
  } else {
    nodes = Array.from(elem.childNodes);
  }
  if (elem.tagName == "A" || elem.tagName == "DIV" ||
      elem.tagName == "SECTION" ||
      ((elem.tagName == "SPAN" || elem.textContent == "") &&
       (elem.className != "ref" && elem.className != "figure-ref" &&
        elem.className != "table-ref" && elem.className != "other-ref"))) {
    result = nodes.map(clean_elem).join("");
  } else if (elem.tagName == "FIGURE") {
    result = "<figure></figure>";
  } else {
    if (elem.attributes != null) {
      num_attributes = 0;
      while(elem.attributes.length > num_attributes) {
        if (elem.attributes[0].name != "class" ||
            (elem.attributes[0].value != "ref" &&
             elem.attributes[0].value != "figure-ref" &&
             elem.attributes[0].value != "table-ref" &&
             elem.attributes[0].value != "other-ref")) {
          elem.removeAttribute(elem.attributes[0].name);
        } else {
          num_attributes++;
        }
      }
    }
    elem.innerHTML =  nodes.map(clean_elem).join("");
    if (elem.outerHTML == null) {
      result = elem.innerHTML;
    } else {
      result = elem.outerHTML;
    }
  }
  result = result.replace(/\((<span[^>]*>[^\)^\(]*<\/span>)\)/g, "$1");
  result = result.replace(/<\/span>[\s]*<span/g, "</span><span");
  return result;
}

window.onload = scrape;

var id_xhr = new XMLHttpRequest();
var abstract, figures, main_text, references, files, id;

var results = {"abs": new XMLHttpRequest(), "fig": new XMLHttpRequest(),
               "main": new XMLHttpRequest(), "ref": new XMLHttpRequest(),
               "file": new XMLHttpRequest()};

var MAX_RETRY = 20;

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
  var count = 0;
  var response = JSON.parse(id_xhr.response);
  if (!have_access()) {
    window.location.replace("/pyreadredirect?doi=" + id.doi);
  }
  var interval = setInterval(function() {
    count++;
    abstract = get_abstract();
    if (abstract || count > MAX_RETRY) {
      clearInterval(interval);
      abstract = clean_elem(abstract);
      results.abs.open("POST", "/pyreadscrapi");
      results.abs.send(JSON.stringify({"doi": id.doi, "abstract": abstract}));
      pyr_figures();
    }
  }, 500);
}

function pyr_figures() {
  var count = 0;
  var interval = setInterval(function() {
    count++;
    figures = get_figures();
    if (count > MAX_RETRY ||
        (figures.length > 0 && (figures.length > 1 ||
                                figures[0].title != "Graphical Abstract"))) {
      clearInterval(interval);
      for (var i = 0; i < figures.length; i++) {
        if (figures[i].legend) {
          figures[i].legend = clean_elem(figures[i].legend);
        }
      }
      results.fig.open("POST", "/pyreadscrapi");
      results.fig.send(JSON.stringify({"doi": id.doi, "figures": figures}));
      pyr_content();
    }
  }, 500);
}

function pyr_content() {
  var count = 0;
  var interval = setInterval(function() {
    count++;
    main_text = get_content();
    if (main_text.length > 1 || count > MAX_RETRY) {
      clearInterval(interval);
      for (var i = 0; i < main_text.length; i++) {
        if (main_text[i].content.length && main_text[i].content[0].title) {
          for (var j = 0; j < main_text[i].content.length; j++) {
            main_text[i].content[j].content =
              clean_elem(main_text[i].content[j].content);
          }
        } else {
          main_text[i].content = clean_elem(main_text[i].content);
        }
      }
      results.main.open("POST", "/pyreadscrapi");
      results.main.send(JSON.stringify({"doi": id.doi, "main": main_text}));
      pyr_references();
    }
  }, 500);
}

function pyr_references() {
  var count = 0;
  var interval = setInterval(function() {
    count++;
    references = get_references();
    if (references.length > 0 || count > MAX_RETRY) {
      clearInterval(interval);
      results.ref.open("POST", "/pyreadscrapi");
      results.ref.send(JSON.stringify({"doi": id.doi,
                                       "references": references}));
      pyr_files();
    }
  }, 500);
}

function pyr_files() {
  var count = 0;
  var interval = setInterval(function() {
    count++;
    files = get_files();
    if (Object.keys(files).length > 0 || count > MAX_RETRY) {
      clearInterval(interval);
      results.file.open("POST", "/pyreadscrapi");
      results.file.send(JSON.stringify({"doi": id.doi, "files": files}));
      collect_results();
    }
  }, 500);
}

function collect_results() {
  var interval = setInterval(function() {
    var success = true;
    for (var x in results) {
      console.log(x);
      success = success && results[x].readyState == 4;
      if (!success) {
        break;
      }
    }
    if (success) {
      clearInterval(interval);
      status_updater = new XMLHttpRequest();
      status_updater.onload = function() {
        //window.location.replace('/pyreadhome?doi=' + id.doi);
      };
      status_updater.open('GET', '/pyreadstatus?loading=false&doi=' + id.doi);
      status_updater.send();
    }
  }, 500);
}
