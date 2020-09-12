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
  var refs = document.querySelectorAll("meta[name=citation_reference]");
  var ref_list = [];
  for (var i = 0; i < refs.length; i++) {
    var refnum, ref_entry = {};
    for (var entry of refs[i].content.matchAll(/([^=]*)=([^;]*)(; |$)/g)) {
      if (entry[1] == "citation_journal_title") {
        ref_entry.journal = entry[2];
      } else if (entry[1] == "citation_title") {
        ref_entry.title = entry[2];
      } else if (entry[1] == "citation_author") {
        ref_entry.authors = entry[2].split(", ");
      } else if (entry[1] == "citation_publication_date") {
        ref_entry.year = entry[2];
      } else if (entry[1] == "citation_doi") {
        ref_entry.doi = entry[2];
      } else if (entry[1] == "citation_id") {
        refnum = parseInt(entry[2].match(/[^\d]*(\d*)$/)[1], 10);
      }
    }
    ref_list[refnum - 1] = ref_entry;
  }
  var citations = document.querySelectorAll("li[itemprop=citation]");
  for (var j = 0; j < citations.length; j++) {
    if (ref_list[j] == null) {
      ref_list[j] = {};
    }
    var cit_text = citations[j].querySelector("p");
    console.log(cit_text);
    var cit_match = cit_text.textContent.match(/((?:[^,^\.]+,(?:\s[A-Z]\.)+(?:,|\s&)\s)*[^,^\.]+,(?:\s[A-Z]\.)+\s(?:et\sal\.\s)?)?([^\.]+)[^\(]+\((\d\d\d\d)/);
    if (ref_list[j].journal == null) {
      ref_list[j].journal = cit_text.querySelector("i").textContent;
    }
    if (ref_list[j].title == null) {
      ref_list[j].title = cit_match[2];
    }
    if (ref_list[j].authors == null) {
      if (cit_match[1] != null) {
      ref_list[j].authors = cit_match[1].match(/([^&^,^\.^\s][^&^,^\.]+,(?:\s[A-Z]\.)|et\sal\.)/g);
      }
    }
    if (ref_list[j].year == null) {
      ref_list[j].year = cit_match[3];
    }
    var cit_links = citations[j].querySelectorAll("a");
    for (var k = 0; k < cit_links.length; k++) {
      if (cit_links[k].textContent == "Article" && ref_list[j].doi == null) {
        ref_list[j].doi = decodeURIComponent(new URL(cit_links[k].href).pathname);
      } else if (cit_links[k].textContent == "Pubmed" && ref_list[j].pmid == null) {
        ref_list[j].pmid = cit_links[k].href.match(/\d+$/)[0];
      }
    }
  }
  return ref_list;
}

function get_files() {
  result = {};
  result.pdf = document.querySelector("a.c-pdf-download__link").href;
  var supplements = document.querySelectorAll(
    "div[data-test=supplementary-info]");
  for (var i = 0; i < supplements.length; i++) {
    if(supplements[i].parentElement.previousSibling.textContent ==
       "Extended data") {
         continue;
    }
    var files = supplements[i].querySelectorAll("h3");
    for (var j = 0; j < files.length; j++) {
      result[files[j].textContent] = files[j].querySelector("a").href;
    }
  }
  return result;
}
