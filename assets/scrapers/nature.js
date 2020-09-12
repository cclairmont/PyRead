/*jshint esversion: 6 */

//
// Internal Functions
//

// The ref_selector function shoulf return a Node List containing all
// references.  This list will be iterated through and each element will be
// subjected to the ref_matcher and ref_selector functions defined below.
// Usually a simple elem.querySelectorAll will suffice, but you can implement
// more complex logic if needed.

function ref_selector(elem) {
  return elem.querySelectorAll("a[id^=ref-link]");
}

// The ref matcher function should return a string corresponding to the full
// text of a reference given a string. If there are multiple references in
// a given string it should return only the first. The point of this function
// is to tell the reference handler what text should be removed and replaced
// by our custom reference format.  Therefore: commas, spaces etc. should also
// be included in the returned string.  If not match is found, this function
// should return null.
//
// The reference handler will continue to iterate through a given string
// removing the returned substring and passing it back to ref_matcher until it
// returns null.
//
// For example: Nature references are a simple comma separated list like so:
// 1,2,3,4.  Given the input string "1,2,3,4" this function could return "1,".
// On the next iteration, the function will be passed "2,3,4", it could then
// return "2,".  This continues until the function is passed "" at which point
// it will return null.  Note that the function could also return "1" for the
// first iteration and then ",2" ",3" ",4" and null for the subsequent
// iterations.
//
// The ref handler initially looks at the text inside of the ref element given
// by ref_selector.  If no match is found it appends the text from the previous
// and next nodes and checks again.  This process will continue until
// ref_matcher returns a match or there are no more nodes in the given block or
// another reference is reached on either side.
//
// If a match is returned by ref_matcher.  The ref handler will iterate at
// least one more time to determine if a longer match can be found.  Therefore,
// this can be considered a "greedy" matcher in that it will look for the
// longest possible match.  It ref_matcher returns the same match twice in a
// iteration with terminate.
//
// A more complex example: Sciencedirect figure references look like this:
// (Figure <a>1A</a>, <a>1B</a> and <a>1C</a>).  Let's say that ref selector
// gives us all of the <a></a> elements.  Our node list will look like:
// [<a>1A</a>, <a>1B</a>, <a>1C</a>].  The text we want to match (and replace)
// is "Figure 1A, ", "1B and", "1C", respectively, although the choice of
// where to put the commas, whitespace and "and" is flexible.
//
// In most cases a regex is the simplest approach to these functions.  The
// following regex is used in my implementation of the SD scraper:
//
// /(Figures?|Figs?.|^)((,|;|,?\sand)?(\s|^)S?\d[A-Z]?(-S?\d?[A-Z]?)?)+/g
//
// In the first iteration for the first node, this will return a match
// immediately, which will be "1A", but on the the next iteration, ref_matcher
// will be fed the text "(Figure 1A, " which will produce a longer match:
// "Figure 1A".  Iteration will then terminate as there is no previous node
// and the next node is in the reference list.  The original ref node will then
// be replaced with our place holder (<span class='foo'></span>) and
// adjacent matched text will be deleted.  So our whole reference block now
// looks like: (<span class='foo'></span><a>1B</a> and <a>1C</a>).  So for our
// next node, the longest string we will be given to match is: ", 1B and " and
// our regex will match ", 1B".  For the last node, we'll get the string:
// " and 1C", which will be fully matched.  So the final product in the html
// will be:
//(<span class='foo'></span><span class='foo'></span><span class='foo'></span>)
// We don't need to worry about the parens.  Any parens with no text content
// between then will be removed by the clean_html function.

function ref_matcher(text) {
  var m = text.match(/(\d+,?)/);
  if (m != null) {
    return m[0];
  } else {
    return null;
  }
}

// ref_num is fed the original node from the node list and optionally the
// string returned by ref_matcher for that node.  In this case we just use
// a regex on the href attribute of the element.  In other cases we may need to
// factor in the matched string as well.  It should return the number
// corresponsing to the item the given reference is referring to.

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

// handlers defines the classes of reference we are looking for and their
// respective handler functions.  selector, matcher and num correspond to the
// functions described above.  Class will determine the class attribute of the
// placeholder <span> elements that we create to replace the references.

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
