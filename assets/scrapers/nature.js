/*jshint esversion: 6 */

//
// Internal Functions
//

function ref_selector(elem) {
  return elem.querySelectorAll("a[id^=ref-link]");
}

function ref_matcher(text) {
  var m = text.match(/(\d+,?)/);
  if (m != null) {
    return m[0];
  } else {
    return null;
  }
}

function ref_num(ref) {
  return ref.href.match(/#[^\d]*(\d*)$/)[1];
}

function fig_ref_selector(elem) {
  return elem.querySelectorAll("a[data-track-action='figure anchor']");
}

function fig_ref_matcher(text) {
  var m = text.match(/((, )?(Extended Data )?Fig\. \d([a-z][,\-])*[a-z])+/);
  if (m != null) {
    return m[0];
  } else {
    return null;
  }
}

function fig_ref_num(ref) {
  console.log(ref);
  var num = ref.textContent.match(/^\d+/)[0];
  var link_num = ref.href.match(/\d+$/)[0];
  console.log(num);
    console.log(link_num);
  if (num == link_num) {
    return ref.textContent.toUpperCase();
  } else {
    return "S" + ref.textContent.toUpperCase();
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
  var doi = document.querySelector("meta[name=DOI]").content;
  var title = document.querySelector("meta[name='dc.title']").content;
  return {"doi": doi, "title": title};
}

function have_access() {
  return document.querySelector("#access-options") == null;
}

function get_abstract() {
  var abs = document.querySelector("div[id^=Abs][id$=content]");
  return abs;
}

function get_figures() {
  var figures = document.querySelector("div.c-article-body").querySelectorAll("figure");
  var result = [];
  for (var i = 0; i < figures.length; i++) {
    var fig_entry = {};
    var fig_link = new URL("https:" + figures[i].querySelector("source").srcset);
    fig_link.search = "";
    fig_entry.lr = fig_link.href;
    fig_link.pathname = fig_link.pathname.replace(/^\/[^\/]*/, '/full');
    fig_entry.hr = fig_link.href;
    var captions = figures[i].querySelector("p");
    fig_entry.legend = handle_figs_refs(captions);
    fig_entry.title = figures[i].querySelector("figcaption").textContent;
    result.push(fig_entry);
  }
  var elems = document.querySelectorAll("section[aria-labelledby^=Sec]");
  for (var i = 0; i < elems.length; i++) {
    var title = elems[i].querySelector("h2");
    if (title != null && title.textContent == "Extended data") {
      var ext_figs = elems[i].querySelectorAll("[id^=Fig]");
      for (var j = 0; j < ext_figs.length; j++) {
        var fig_entry = {};
        fig_entry.title = ext_figs[j].querySelector("h3").textContent;
        fig_entry.hr = "https:" +
                       ext_figs[j].querySelector("a").dataset.suppInfoImage;
        fig_entry.legend = handle_figs_refs(ext_figs[j].querySelector("div"));
        result.push(fig_entry);
      }
    }
  }
  return result;
}

function get_content() {
  var content = [];
  var elems = document.querySelectorAll("section[aria-labelledby^=Sec]");
  for (var i = 0; i < elems.length; i++) {
    var section = {};
    var title = elems[i].querySelector("h2");
    if (title == null || title.textContent == "Extended data" ||
        title.textContent == 'Supplementary information' ||
        title.textContent == "Source data") {
      continue;
    }
    section.title = title.innerHTML;
    var subtitles = elems[i].querySelectorAll("h3");
    var subelem;
    var p_list = [];
    if (subtitles.length == 0) {
      subelem = title.nextSibling.childNodes[0];
      while(subelem != null) {
        p_list.push(subelem);
        subelem = subelem.nextSibling;
      }
      section.content = handle_figs_refs(p_list);
    } else {
      section.content = [];
      for (var j = 0; j < subtitles.length; j++) {
        var subsection = {};
        subsection.title = subtitles[j].innerHTML;
        subelem = subtitles[j].nextSibling;
        p_list = [];
        while(subelem != null) {
          if (subelem.tagName == "H3") {
            break;
          } else {
            p_list.push(subelem);
          }
            subelem = subelem.nextSibling;
        }
        subsection.content = handle_figs_refs(p_list);
        section.content.push(subsection);
      }
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
