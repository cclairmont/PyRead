/*jshint esversion: 6 */

//
// Internal Functions
//

function ref_selector(elem) {
  return elem.querySelectorAll("a.xref-bibr");
}

function ref_matcher(text) {
  var m = text.match(/(\d+[,–]?)/);
  if (m != null) {
    return m[0];
  } else {
    return null;
  }
}

function ref_num(ref) {
  return ref.dataset.open.split(" ").map(function(x) {
    return x.slice(1);
  }).join(",");
}

function fig_ref_selector(elem) {
  main_figs = elem.querySelectorAll("a.xref-fig");
  supp_figs = [...elem.querySelectorAll("span.supplementary-material")].filter(
    function(x) {
      return /Figure/.test(x);
    });
  return supp_figs.concat(...main_figs);
}

function fig_ref_matcher(text) {
  var m = text.match(/((Supplementary )?Figures? |, | and )(\d+)?[A-Z]/);
  if (m != null) {
    return m[0];
  } else {
    return null;
  }
}

function fig_ref_num(ref) {
  if (ref.tagName == "A") {
    return ref.dataset.open.split(" ").map(function(x) {
      return x.slice(1);
    }).join(",");
  } else if (ref.tagName == "SPAN") {
    return ref.childNodes[0].attributes['path-from-xml'].textContent;
  }
}

var handlers = [{selector: ref_selector,
                 matcher: ref_matcher,
                 num: ref_num,
                 class: "ref"},
                {selector: fig_ref_selector,
                 matcher: fig_ref_matcher,
                 num: fig_ref_num,
                 class: "figure-ref"}];

//
// PyRead functions
//

function get_identifiers() {
  var doi = document.querySelector("div.ww-citation-primary").textContent.match(/doi.org\/(.*)/)[1];
  var title = document.querySelector("meta[property='og.title']").content;
  return {"doi": doi, "title": title};
}

function have_access() {
  return true;
}

function get_abstract() {
  var abs = document.querySelector("section.abstract");
  return abs;
}

function get_figures() {
  var figures = document.querySelectorAll("div.fig-section");
  var result = [];
  for (var i = 0; i < figures.length; i++) {
    var fig_entry = {};
    fig_entry.lr = figures[i].querySelector("img").src;
    fig_entry.hr = figures[i].querySelector("a.fig-view-orig").href;
    fig_entry.legend = figures[i].querySelector("div.fig-caption");
    fig_entry.title = figures[i].querySelector("div.fig-label").textContent;
    result.push(fig_entry);
  }
  return result;
}

function get_content() {
  var content = [];
  var section_titles = document.querySelectorAll("h2.section-title");
  for (var i = 0; i < section_titles.length; i++) {
    var section = {};
    section.title = section_titles[i].innerHTML;
    section.title = title.innerHTML;
    section.content = [];
    current_elem = section_titles[i].nextElementSibling;
    while(current_elem != null &&
          (i == section_titles.length - 1 ||
           !current_elem.isSameNode(section_titles[i+1]))) {
      if (current_elem.className == "chapter-para") {
        section.content.push(current_elem);
      } else if (current_elem.className == "section-title") {
        var subsection = {};
        subsection.title = current_elem.innerHTML;
        subsection.content = [];
        current_elem = current_elem.nextElementSibling;
        while(current_elem != null &&
              (i == section_titles.length - 1 ||
               (!current_elem.isSameNode(section_titles[i+1]) &&
                current_elem.tagName != "H3"))) {
          if (current_elem.className == "chapter-para" ||
              current_elem.className == "section-title") {
            subsection.content.push(current_elem);
          }
        }
        section.content.push(subsection);
        continue;
      }
      current_elem = current_elem.nextElementSibling;
    }
    content.push(section);
  }
  return content;
}

function get_references() {
  var refs = document.querySelectorAll("div.ref-content");
  var ref_list = [];
  for (var i = 0; i < refs.length; i++) {
    var refnum = parseInt(refs[i].id.slice(10), 10);
    var ref_entry = {};
    var surnames = refs[i].querySelectorAll(".surname");
    var given_names = refs[i].querySelectorAll(".given-names");
    ref_entry.authors = [];
    for (var j = 0; j < surnames.length; j++) {
      ref_entry.authors.push(surnames[i].textContent + ", " +
                             given_names[i].textContent);
    }
    ref_entry.title = document.querySelector(".article-title").textContent;
    ref_entry.journal = document.querySelector(".source").textContent;
    ref_entry.year = document.querySelector(".year").textContent;
    var link;
    var crossref = document.querySelector(".crossref-doi");
    if (crossref != null) {
      link = crossref.querySelector("a").href;
      ref_entry.doi = link.match(/doi.org\/(.*)/)[1];
    }
    var pubmed = document.querySelector(".pub-id");
    if (pub_id != null) {
      link = pubmed.querySelector("a").href;
      ref_entry.pmid = link.match(/pubmed\/(.*)/)[1];
    }
  }
  return ref_list;
}

function get_files() {
  result = {};
  result.pdf = document.querySelector("a.article-pdfLink").href;
  var supplements = document.querySelectorAll("div.dataSuppLink");
  for (var i = 0; i < supplements.length; i++) {
    var link = supplements[i].querySelector("a").href;
    result[supplements[i].textContent] = link;
  }
  return result;
}
