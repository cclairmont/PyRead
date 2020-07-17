//
// Internal Functions
//

function handle_figs_refs(elem) {
  var refs = elem.querySelectorAll("a.workspace-trigger");
  for (var i = 0; i < refs.length; i++) {
    var new_ref, refnum, is_figref;
    if (refs[i].name.startsWith("bbib") || refs[i].name.startsWith("bfig") ||
        refs[i].name.startsWith("bapp")) {
      is_figref = refs[i].name.startsWith("bfig") ||
                  refs[i].name.startsWith("bapp");
      refnum = refs[i].name.slice(4);
      new_ref = document.createElement("span");
      if (is_figref) {
        new_ref.className = "figure-ref";
      } else {
        new_ref.className = "ref";
        new_ref.dataset.refnum = refnum;
      }
      refs[i].replaceWith(new_ref);
    } else {
      continue;
    }
    var prev = new_ref.previousSibling;
    var next = new_ref.nextSibling;
    if (is_figref) {
      refnum = "";
      var fig_ref = refs[i].textContent;
      var ref_end = -1;
      var del_len = 0;
      while (next != null && next.tagName != 'A') {
        fig_ref = fig_ref + next.textContent;
        ref_end = fig_ref.search(/[\[\(\)\]\.]/);
        if (ref_end != -1) {
          fig_ref = fig_ref.slice(0, ref_end + 1);
          break;
        }
        del_len = del_len + next.textContent.length;
        next.textContent = "";
        next = next.nextSibling;
      }
      console.log(fig_ref);
      fig_ref = fig_ref.replace(/&nbsp;/g, ' ');
      var matcher = fig_ref.matchAll(
        /(^|\s)(S?\d[A-Z]?)([,;\s\.\)\]]|–S?\d?[A-Z]?|$)/g);
      var matches = [];
      for (m of matcher) {
        console.log(m);
        if (m[3].startsWith("–")) {
          matches.push(m[2] + m[3]);
        } else {
          matches.push(m[2]);
        }
      }
      console.log(matches);
      if (matches.length > 0) {
        ref_end = fig_ref.lastIndexOf(matches[matches.length - 1]) +
                  matches[matches.length - 1].length -
                  refs[i].textContent.length - del_len;
        next.textContent = next.textContent.slice(ref_end);
        new_ref.dataset.refnum = matches.join(",");
      }
    }

    if (next && (next.textContent.startsWith(";") ||
                 next.textContent.startsWith(","))) {
      next.textContent = next.textContent.slice(1);
    }
  }
  return elem;
}


//
// PyRead functions
//

function get_identifiers() {
  var doi_elem = document.querySelector("a.doi");
  var link = doi_elem.href;
  console.log(link);
  var slashes = [...link.matchAll(/\//g)]
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
  var abs = document.querySelector("div[id^=abssec]");
  if (abs == null) {
    abs = document.querySelector("div[id^=aep-abstract-sec]")
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
      fig_entry.title = caption_list[0].textContent;
      caption_list[0].parentElement.removeChild(caption_list[0]);
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
  for (var i = 0; i < elems.length; i++) {
    if (elems[i].id.indexOf(".") != -1) {
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
  var bib_section = document.querySelector("section.bibliography");
  var refs = bib_section.querySelectorAll("dt.label");
  var ref_list = [];
  for (var i = 0; i < refs.length; i++) {
    var refnum = refs[i].querySelector("a").href;
    refnum = parseInt(refnum.slice(refnum.indexOf('#bbib') + 5), 10);
    var ref_entry = {};
    ref_entry.label = refs[i].textContent;
    var ref_info = refs[i].nextSibling;
    var auth_list = ref_info.querySelector("div.contribution");
    var journal_year;
    if (auth_list) {
      ref_entry.title = ref_info.querySelector("strong").textContent;
      auth_list = auth_list.textContent.slice(
        0, auth_list.textContent.indexOf(ref_entry.title));
      journal_year = ref_info.querySelector("div.host").textContent;
    } else {
      var text = ref_info.textContent;
      var auth_list_end = text.indexOf(" (");
      auth_list = text.slice(0, auth_list_end);
      var title_start = text.indexOf("). ") + 3;
      text = text.slice(title_start);
      title_end = text.indexOf(". ");
      ref_entry.title = text.slice(0, title_end);
    }
    var journal_end = journal_year.indexOf(",");
    var year_start = journal_year.slice(journal_end).indexOf('(') +
                     journal_end + 1;
    var year_end = journal_year.slice(year_start).indexOf(')') + year_start;
    ref_entry.journal = journal_year.slice(0, journal_end);
    ref_entry.year = journal_year.slice(year_start, year_end);
    ref_entry.authors = auth_list.split(", ");
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
  return result;
}
