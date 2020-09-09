/*jshint esversion: 6 */

//
// Internal Functions
//

function ref_selector(elem) {
  var stuff = elem.querySelectorAll("a.workspace-trigger");
  var refs = [];
  for (var s of stuff) {
    if (s.name.startsWith("bb")) {
      refs.push(s);
    }
  }
  return refs;
}

function ref_matcher(text) {
  var m = text.match(
    /([,;]\s)?([^\(^\s]+(\set\sal\.|\sand\s[^\(^\s]+)?,\s\d\d\d\d)+/);
  if (m != null) {
    return m[0];
  } else {
    return null;
  }
}

function ref_num(ref, text) {
  return ref.name.slice(4);
}

function fig_ref_selector(elem) {
  var stuff = elem.querySelectorAll("a.workspace-trigger");
  var fig_refs = [];
  var is_figref = false;
  for (var s of stuff) {
    if (s.name.startsWith("bfig") || s.name.startsWith("bmmc") ||
        s.name.startsWith("bapp")) {
      if (s.textContent.startsWith("Fig")) {
        is_figref = true;
      } else if (s.textContent.startsWith("Table")) {
        is_figref = false;
      }
      if (is_figref) {
        fig_refs.push(s);
      }
    }
  }
  return fig_refs;
}

function fig_ref_matcher(text) {
  var m = text.match(
    /(Figures?|Figs?.|^)((,|;|,?\sand)?(\s|^)S?\d[A-Z]?(-S?\d?[A-Z]?)?)+/g);
  if (m != null) {
    return m[0];
  } else {
    return null;
  }
}

function fig_ref_num(ref, text) {
  var start = text.indexOf(ref.textContent);
  var num;
  if (start == -1) {
    return "";
  }
  num = text.slice(start);
  console.log(text);
  console.log(num);
  var m =  num.match(/((,|,?\sand)?\sS?\d+[A-Z]?)+/);
  if (m != null) {
    console.log(m[0]);
    m = m[0].replace(/\s/g, "");
    console.log(m);
    m = m.replace(/,?and/g, ",");
    console.log(m);
    var m_list = m.split(",");
    console.log(m_list);
    var prefix;
    if (m_list[0].length > 0) {
      prefix = m_list[0].match(/S?\d+/)[0];
    } else {
      prefix = m_list[1].match(/S?\d+/)[0];
    }
    for (var i = 0; i < m_list.length; i++) {
      if (!m_list[i].startsWith(prefix)) {
        m_list.splice(i, 1);
        i--;
      }
    }
    return m_list.join(",");
  } else {
    return "";
  }
}

function table_ref_selector(elem) {
  var stuff = elem.querySelectorAll("a.workspace-trigger");
  var table_refs = [];
  var is_table = false;
  for (var s of stuff) {
    if (s.name.startsWith("bfig") || s.name.startsWith("bmmc") ||
        s.name.startsWith("bapp")) {
      if (s.textContent.startsWith("Fig")) {
        is_table = false;
      } else if (s.textContent.startsWith("Table")) {
        is_table = true;
      }
      if (is_table) {
        table_refs.push(s);
      }
    }
  }
  return table_refs;
}

function table_ref_matcher(text) {
  var m = text.match(/(Tables?|^)((,|;|\s,?and)?(\s|^)S?\d[A-Z]?(-S?\d?[A-Z]?)?)+/g);
  if (m != null) {
    return m[0];
  } else {
    return null;
  }
}

var handlers = [{selector: ref_selector,
                 matcher: ref_matcher,
                 num: ref_num,
                 class: "ref"},
                {selector: fig_ref_selector,
                 matcher: fig_ref_matcher,
                 num: fig_ref_num,
                 class: "figure-ref"},
                 {selector: table_ref_selector,
                  matcher: table_ref_matcher,
                  num: fig_ref_num,
                  class: "table-ref"}];

//
// PyRead functions
//

function get_identifiers() {
  var doi_elem = document.querySelector("a.doi");
  var link = doi_elem.href;
  console.log(link);
  var slashes = [...link.matchAll(/\//g)];
  var doi_start = slashes[slashes.length - 2].index + 1;
  var doi = link.slice(doi_start);
  var title = document.querySelector("span.title-text").textContent;
  return {"doi": doi, "title": title};
}

function have_access() {
  var pdf_dl_button = document.querySelector("span.pdf-download-label");
  return pdf_dl_button.textContent == "Download PDF";
}

function get_abstract() {
  var abs = document.querySelector("div.abstract.author");
  if (abs == null) {
    abs = document.querySelector("div[id^=aep-abstract-sec]");
  } else {
    abs = abs.querySelector("div");
  }
  return abs;
}

function get_figures() {
  var figures = document.querySelectorAll("figure");
  var result = [];
  for (var i = 0; i < figures.length; i++) {
    var fig_entry = {};
    var fig_links = figures[i].querySelector("ol.links-for-figure");
    fig_links = fig_links.querySelectorAll("a");
    for (var j = 0; j < fig_links.length; j++) {
      if (fig_links[j].textContent.indexOf("high-res") == -1) {
        fig_entry.lr = fig_links[j].href;
      } else {
        fig_entry.hr = fig_links[j].href;
      }
    }
    var captions = figures[i].querySelector("span.captions");
    if (captions) {
      var caption_list = captions.querySelectorAll("p");
      if (caption_list.length > 1) {
        fig_entry.title = caption_list[0].textContent;
        caption_list[0].parentElement.removeChild(caption_list[0]);
      } else {
        var title = caption_list[0].textContent.match(
          /Fig\.\s\d+\.\s[^\.]*\.\s/);
        if (title != null) {
          fig_entry.title = title[0];
          captions.textContent = captions.textContent.slice(title[0].length);
        }
      }
      fig_entry.legend = handle_figs_refs(captions);
    } else {
      fig_entry.title = "Graphical Abstract";
    }
    result.push(fig_entry);
  }
  return result;
}

function get_content() {
  var content = [];
  var elems = document.querySelectorAll("section[id^=sec]");
  if (elems.length == 0) {
    var main = document.querySelector("div#body");
    console.log(main.textContent);
    if (main.textContent != "Loading...") {
      content = [{"title": "Body", "content": handle_figs_refs(main)}];
    }
  }
  for (var i = 0; i < elems.length; i++) {
    if (elems[i].id.indexOf(".") != -1 ||
        elems[i].parentElement.tagName == "SECTION") {
      //Skipping subsections (Which have '.' in their id)
      continue;
    }
    var section = {};
    var title = elems[i].querySelector("h2");
    if (title == null) {
      title = elems[i].querySelector("h3");
    }
    console.log(elems[i]);
    section.title = title.innerHTML;
    elems[i].removeChild(title);
    var subsects = elems[i].querySelectorAll("section");
    if (subsects.length == 0) {
      section.content = handle_figs_refs(elems[i]);
    } else {
      section.content = [];
      for (var j = 0; j < subsects.length; j++) {
        if ([...subsects[j].id.matchAll(/\./g)].length > 1) {
          continue;
        }
        var subsection = {};
        var subtitle = subsects[j].querySelector("h3");
        if (subtitle == null) {
          subtitle = subsects[j].querySelector("h4");
        }
        console.log(subsects[j]);
        subsection.title = subtitle.innerHTML;
        subsects[j].removeChild(subtitle);
        subsection.content = handle_figs_refs(subsects[j]);
        section.content.push(subsection);
      }
    }
    content.push(section);
  }
  return content;
}

function get_references() {
  var bib_section = document.querySelector("section[class^=bibliography]");
  var refs = bib_section.querySelectorAll("dt.label");
  var ref_list = [];
  for (var i = 0; i < refs.length; i++) {
    var refnum = refs[i].querySelector("a").href;
    refnum = parseInt(refnum.slice(refnum.indexOf('#bb') + 5), 10);
    var ref_entry = {};
    ref_entry.label = refs[i].textContent;
    var ref_info = refs[i].nextSibling;
    var auth_list = ref_info.querySelector("div.contribution");
    var journal_year, auth_list_end;
    if (auth_list) {
      auth_list = auth_list.textContent;
      ref_entry.title = ref_info.querySelector("strong");
      if (ref_entry.title != null) {
        ref_entry.title = ref_entry.title.textContent;
        auth_list_end = auth_list.indexOf(ref_entry.title);
        if (auth_list_end != -1) {
          auth_list = auth_list.slice(0, auth_list_end);
        }
      }
      journal_year = ref_info.querySelector("div.host").textContent;
    } else {
      var text = ref_info.textContent;
      auth_list_end = text.indexOf(" (");
      if (auth_list_end != -1) {
        auth_list = text.slice(0, auth_list_end);
      }
      var title_start = text.indexOf("). ") + 3;
      text = text.slice(title_start);
      title_end = text.indexOf(". ");
      ref_entry.title = text.slice(0, title_end);
    }
    if (journal_year != null) {
      var journal_end = journal_year.indexOf(",");
      var year_start = journal_year.slice(journal_end).indexOf('(') +
                       journal_end + 1;
      var year_end = journal_year.slice(year_start).indexOf(')') + year_start;
      ref_entry.journal = journal_year.slice(0, journal_end);
      ref_entry.year = journal_year.slice(year_start, year_end);
    }
    if (auth_list != null) {
      ref_entry.authors = auth_list.split(", ");
    }
    var links = ref_info.querySelectorAll("a");
    for (var j = 0; j < links.length; j++) {
      var doi_start = links[j].href.indexOf("doi.org/");
      if (doi_start != -1) {
        ref_entry.doi = links[j].href.slice(doi_start + 8);
        break;
      }
    }
    ref_list[refnum - 1] = ref_entry;
  }
  return ref_list;
}

function get_files() {
  result = {};
  var pdf_button = document.querySelector("div.PdfDownloadButton");
  var link = pdf_button.querySelector("a");
  if(!link) {
    document.getElementById("pdfLink").click();
    return {};
  } else {
    result.pdf = link.href;
    if (result.pdf != null) {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", result.pdf, false);
      xhr.send();
      var response = xhr.responseText;
      var start = response.indexOf('<a href="') + 9;
      var end = response.slice(start).indexOf('">') + start;
      result.pdf = response.slice(start, end);
    }
    var appendix = document.querySelector("div.Appendices");
    if (appendix != null) {
      var links = appendix.querySelectorAll("span.article-attachment");
      for (var i = 0; i < links.length; i++) {
        if (links[i].nextSibling == null) {
          continue;
        }
        var title = links[i].nextSibling.textContent;
        if (title.indexOf("Supplemental Information") != -1 &&
            !result.hasOwnProperty("extended")) {
          title = "extended";
        }
        link = links[i].querySelector("a");
        result[title] = link.href;
      }
    }
  }
  return result;
}
