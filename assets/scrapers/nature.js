/*jshint esversion: 6 */

//
// Internal Functions
//

function handle_figs_refs(elem) {
  // var refs = elem.querySelectorAll("a.workspace-trigger");
  // var fig_type = "other-ref";
  // for (var i = 0; i < refs.length; i++) {
  //   console.log(refs[i]);
  //   var new_ref, refnum, is_figref;
  //   if (refs[i].name.startsWith("bb") || refs[i].name.startsWith("bfig") ||
  //       refs[i].name.startsWith("bapp") || refs[i].name.startsWith("bmmc")) {
  //     is_figref = refs[i].name.startsWith("bfig") ||
  //                 refs[i].name.startsWith("bapp") ||
  //                 refs[i].name.startsWith("bmmc");
  //     refnum = refs[i].name.slice(4);
  //     new_ref = document.createElement("span");
  //     if (is_figref) {
  //       if (refs[i].textContent.startsWith('Fig')) {
  //         fig_type = "figure-ref";
  //       } else if (refs[i].textContent.startsWith('Table')) {
  //         fig_type = "table-ref";
  //       }
  //       new_ref.className = fig_type;
  //     } else {
  //       new_ref.className = "ref";
  //       new_ref.dataset.refnum = refnum;
  //     }
  //     refs[i].replaceWith(new_ref);
  //   } else {
  //     continue;
  //   }
  //   var prev = new_ref.previousSibling;
  //   var next = new_ref.nextSibling;
  //   if (is_figref) {
  //     refnum = "";
  //     var fig_ref = refs[i].textContent;
  //     var orig_ref = fig_ref;
  //     var ref_end = -1;
  //     var del_len = 0;
  //     var searched_nodes = [refs[i]];
  //     while (next != null && next.tagName != 'A') {
  //       searched_nodes.push(next);
  //       fig_ref = fig_ref + next.textContent;
  //       fig_ref = fig_ref.replace(/&nbsp;/g, ' ');
  //       fig_ref = fig_ref.replace(/–/g, '-');
  //       ref_end = fig_ref.match(/(Figures?|Tables?|Figs?.|^)((,|;|\sand)?(\s|^)S?\d[A-Z]?(-S?\d?[A-Z]?)?)+/g);
  //       if (ref_end != null) {
  //         console.log(ref_end[0]);
  //         ref_end = fig_ref.indexOf(ref_end[0]) + ref_end[0].length;
  //         fig_ref = fig_ref.slice(0, ref_end + 1);
  //         break;
  //       }
  //       next = next.nextSibling;
  //     }
  //     console.log(fig_ref);
  //     var matcher = fig_ref.matchAll(
  //       /(^|\s)(S?\d[A-Z]?)(-S?\d?[A-Z]?|$)?/g);
  //     var matches = [];
  //     for (var m of matcher) {
  //       console.log(m);
  //       if (m[3] != null && m[3].startsWith("-")) {
  //         matches.push(m[2] + m[3]);
  //       } else {
  //         matches.push(m[2]);
  //       }
  //     }
  //     console.log(matches);
  //     if (matches.length > 0) {
  //       ref_end = fig_ref.lastIndexOf(matches[matches.length - 1]) +
  //                 matches[matches.length - 1].length;
  //       for (var sn of searched_nodes) {
  //         console.log(ref_end);
  //         console.log(sn.textContent);
  //         if (ref_end >= sn.textContent.length) {
  //           ref_end -= sn.textContent.length;
  //           sn.textContent = "";
  //         } else {
  //           sn.textContent = sn.textContent.slice(ref_end);
  //           break;
  //         }
  //       }
  //       new_ref.dataset.refnum = matches.join(",");
  //     } else {
  //       new_ref.dataset.refnum = orig_ref;
  //     }
  //     console.log(new_ref);
  //   }
  //
  //   if (next && (next.textContent.startsWith(";") ||
  //                next.textContent.startsWith(","))) {
  //     next.textContent = next.textContent.slice(1);
  //   }
  // }
  return elem;
}


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
        fig_entry.hr = ext_figs[j].querySelector("a").dataset.suppInfoImage;
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
