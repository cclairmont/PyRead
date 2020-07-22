/*jshint esversion: 6 */

var get_content = new XMLHttpRequest();
var get_refs = new XMLHttpRequest();
var get_fileinfo = new XMLHttpRequest();
var fileinfo; //result of info api call
var queries;
var current_article = -1;
var inactive = [];
var sessions = [];
var references;
var updater;
var img_sem = 0;
var active_interval = setInterval(function() {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/pyreadstatus');
  xhr.send();
}, 1000);

/*****************************************************************************/
/*                              Helper Functions                             */
/*****************************************************************************/

function decode(code, type) {
  var num = 0;
  for (var i = 0; i < code.length; i++) {
    if (code[i] <= "9") {
      num += (code[i].charCodeAt(0) - 48) << i*6;
    } else if (code[i] == "-") {
      num += 62;
    } else if (code[i] <= "Z") {
      num += (code[i].charCodeAt(0) - 29) << i*6;
    } else if (code[i] == "_") {
      num += 63;
    } else {
      num += (code[i].charCodeAt(0) - 87) << i*6;
    }
  }
  if (type == "int") {
    return num;
  } else {
    var result = [];
    pos = 0;
    while (num > 0) {
      bit = num & (1 << pos) >> pos;
      num = num >> 1;
      if (bit) {
        result.push(true);
      } else {
        result.push(false);
      }
    }
    return result;
  }
}

function encode(num_array) {
  result = "";
  if (typeof num_array == "object") {
    if (num_array.length == 0) {
      return "0";
    }
  } else if(typeof num_array == "number") {
    if (num_array == 0) {
      return "0";
    } else if (num_array > ~(1 << 31)) {
      return "";
    } else {
      var pos = 0;
      var new_array = [];
      while (num_array > 0) {
        var bit = num_array & (1 << pos) >> pos;
        num_array = num_array >> 1;
        if (bit) {
          new_array.push(true);
        } else {
          new_array.push(false);
        }
      }
      num_array = new_array;
    }
  }
  while (num_array.length > 0) {
    var slice = num_array.slice(0,6);
    num_array = num_array.slice(6);
    var num = 0;
    for (var i = 0; i < 6; i++) {
      if (slice[i]) {
        num += 1 << i;
      }
    }
    if (num < 36) {
      result += num.toString(36);
    } else if (num < 62) {
      result += String.fromCharCode(29 + num);
    } else if (num == 62) {
      result += '-';
    } else {
      result += '_';
    }
  }
  return result;
}

function update_session() {
  if (sessions.length > 0 && current_article != -1) {
    sessions[current_article].inactive = inactive;
    sessions[current_article].scroll = document.documentElement.scrollTop;
    sessions[current_article].height = document.documentElement.scrollHeight;
  }
}

function save_session() {
  if (sessions.length > 0 && current_article != -1) {
    update_session();
    var s_strings = [current_article];
    for (var i = 0; i < sessions.length; i++) {
      var s_array = [];
      s_array.push(sessions[i].doi);
      s_array.push(encode(sessions[i].inactive));
      s_array.push(encode(sessions[i].scroll));
      s_array.push(encode(sessions[i].height));
      s_strings.push(s_array.join(":"));
    }
    document.cookie = "session=" + s_strings.join(",") + "; samesite=strict";
  } else {
    document.cookie = "session=; samesite=strict";
  }
}

function elemsAreAdjacent(e1, e2) {
  return (e1.nextSibling != null && e1.nextSibling.isSameNode(e2)) ||
         (e1.previousSibling != null && e1.previousSibling.isSameNode(e2));
}

function merge_refs(ref_list) {
  var ref_str = "";
  var num_consec = 0;
  var char = false;
  for (var i = 0; i < ref_list.length; i++) {
    var curr = ref_list[i];
    if (isNaN(parseInt(ref_list[i]))) {
      char = true;
      curr = curr.charCodeAt(0);
    }
    if (i == 0) {
      continue;
    } else {
      var prev = ref_list[i - 1];
      if (char) {
        prev = prev.charCodeAt(0);
      }
      if (curr - prev == 1) {
        num_consec++;
      } else {
        if (num_consec == 0) {
          ref_str = ref_str + ref_list[i - 1] + ",";
        } else if (num_consec == 1) {
          ref_str = ref_str + ref_list[i - 2] + "," + ref_list[i - 1] + ",";
        } else {
          ref_str = ref_str + ref_list[i - num_consec - 1] + "-" +
                    ref_list[i - 1] + ",";
        }
      num_consec = 0;
      }
    }
  }
  if (num_consec == 0) {
    ref_str = ref_str + ref_list[i - 1];
  } else if (num_consec == 1) {
    ref_str = ref_str + ref_list[i - 2] + "," + ref_list[i - 1];
  } else {
    ref_str = ref_str + ref_list[i - num_consec - 1] + "-" + ref_list[i - 1];
  }
  return ref_str;
}

function parse_args(uri) {
  var arg_start = uri.indexOf("\?");
  var q_string = uri.substring(arg_start+1);
  var result = {};
  while (true) {
   var q_sep = q_string.indexOf("=");
   var q_end = q_string.substring(q_sep).indexOf("&") + q_sep;
   if (q_end - q_sep == -1) {
     q_end = q_string.length;
   }
   if (q_sep == -1) {
     break;
   }
   var kw = q_string.substring(0, q_sep);
   var val = q_string.substring(q_sep+1, q_end);
   result[kw] = val;
   q_string = q_string.substring(q_end+1);
  }
  return result;
}

function switch_session(idx) {
  save_session();
  if (idx != current_article) {
    var sidebar = document.getElementsByClassName("sidenav-linkcon");
    if (sidebar[current_article] != null) {
      sidebar[current_article].classList.toggle("active");
    }
    load_page(idx);
  }
}

function close_session(idx) {
  save_session();
  sessions.splice(idx, 1);
  if (idx < current_article) {
    current_article--;
  }
  var sidebar = document.getElementsByClassName("sidenav-linkcon");
  sidebar[idx].remove();
  if (idx == current_article) {
    load_page();
  }
}

function new_sidenav() {
  var sidenav = document.getElementsByClassName("sidenav")[0];
  var link_container = document.createElement("div");
  var i = sidenav.childElementCount;
  link_container.className = "sidenav-linkcon";
  link_container.id = "sn-linkcon" + i;
  var link_x = document.createElement("div");
  link_x.className = "sidenav-x";
  link_x.id = "sn-x" + i;
  link_x.innerHTML = "&times;";
  link_container.appendChild(link_x);
  var link = document.createElement("div");
  link.className = "sidenav-link";
  link.id = "sn-link" + i;
  link_container.appendChild(link);
  sidenav.appendChild(link_container);
  function get_pos(elem) {
    var s_elems = sidenav.childNodes;
    for (var i = 0; i < s_elems.length; i++) {
      if (s_elems[i].isSameNode(elem.parentElement)) {
        return i;
      }
    }
  }
  link.onclick = function() {
    i = get_pos(this);
    switch_session(i);
  };
  link_x.onclick = function() {
    i = get_pos(this);
    close_session(i);
  };
  return link;
}

function new_session(doi, title = null, inactive = [], scroll = 0,
                     height = 1) {
  var newest_session = sessions.length;
  for (var i = 0; i < sessions.length; i++) {
    if (doi == sessions[i].doi) {
      newest_session = i;
      break;
    }
  }
  if (title == null) {
    title = doi;
  }
  if (newest_session == sessions.length) {
    sessions.push({doi: doi, inactive: inactive, scroll: scroll,
                   height: height, title: title});
    var link = new_sidenav();
    link.title = title;
    link.innerHTML = title;
    var xhr = new XMLHttpRequest();
    xhr.onload = function() {
      var response = JSON.parse(xhr.response);
      if (response.title != null) {
        sessions[newest_session].title = response.title;
        link.innerHTML = response.title;
        link.title = response.title;
      }
      console.log(response);
      if (!response.local && !response.loading) {
        load_scraper(doi);
      }
    };
    xhr.open('POST', 'pyreadapi');
    params = JSON.stringify({"doi": doi, "type": "info"});
    xhr.send(params);
  }
  var sidenav = document.getElementsByClassName("sidenav")[0];
  var sidebar = sidenav.childNodes[newest_session];
  sidebar.classList.add('highlight');
  sidenav.classList.add('active');
  setTimeout(function() {
    sidebar.classList.remove('highlight');
    sidenav.classList.remove('active');
  }, 500);
}

function load_scraper(doi) {
  resolver = new XMLHttpRequest();
  status_updater = new XMLHttpRequest();
  status_updater.open('GET', '/pyreadstatus?loading=true&doi=' + doi);
  status_updater.send();
  resolver.onload = function() {
    console.log(resolver.status);
    if (resolver.status == 200) {
      var target_url = JSON.parse(resolver.response).url;
      var netloc = new URL(window.location).origin;
      var path = netloc + "/pyreadproxy?location=" + target_url;
      save_session();
      window.open('pyreadhome');
      window.location.replace(path, '_blank');
    } else {
      status_updater.open('GET', '/pyreadstatus?loading=false&doi=' + doi);
      status_updater.send();
    }
  };
  resolver.open('GET', '/pyreadresolve?doi=' + doi);
  resolver.send();
}

/*****************************************************************************/
/*                           Sequential Functions                            */
/*****************************************************************************/

window.onload = function() {
  queries = parse_args(location.href);
  var reload = false;
  if(Object.keys(queries).length > 0) {
    reload = true;
  }
  init_page();
  load_page();
  if (reload) {
    save_session();
    window.location.replace("/pyreadhome");
  }
};

function init_page() {
  var cookies = {};
  document.cookie.split(";").map(function(a) {
    var kv = a.split("=");
    cookies[kv[0]] = kv[1];
  });
  var cookie = cookies[" session"];
  if (cookie != null && cookie != "") {
    cookie.split(",").map(function(a) {
      if (a.indexOf(":") == -1) {
        current_article = parseInt(a, 10);
      } else {
        var kv = a.split(":");
        new_session(kv[0], null, decode(kv[1]), decode(kv[2], "int"),
                    decode(kv[3], "int"));
      }
    });
  }
  if (queries.doi == null && current_article != -1) {
    queries.doi = sessions[current_article].doi;
  }
  var found_session = false;
  for (var i = 0; i < sessions.length; i++) {
    if (sessions[i].doi == queries.doi) {
      current_article = i;
      inactive = sessions[i].inactive;
      found_session = true;
    }
  }
  if (!found_session && queries.doi != null && queries.doi != "") {
    current_article = sessions.length;
    new_session(queries.doi);
  }
}

function load_page(idx = -1) {
  clearInterval(updater);
  if (idx != -1) {
    current_article = idx;
  }
  if (current_article >= sessions.length) {
    current_article = sessions.length - 1;
  }
  var article = document.getElementsByClassName("article")[0];
  article.innerHTML = "";
  var sidebar = document.getElementsByClassName("sidenav-linkcon");
  if (current_article != -1 && sessions[current_article].doi != null) {
    sidebar[current_article].classList.add("active");
    get_content.open("POST", "pyreadapi");
    var params = JSON.stringify({"doi": sessions[current_article].doi,
                                 "type": "content"});
    get_content.send(params);
  } else {
    save_session();
  }
}

get_content.onload = function () {
  /*Section order should be: Intro, Results,
    Discussion, Methods, Acknowledgments*/
  var article = document.getElementsByClassName("article")[0];
  var response_data = JSON.parse(get_content.response);
  for (var i = 0; i < response_data.length; i++) {
    if (response_data[i].content == null) {
      continue;
    }
    section = document.createElement("div");
    section.id = "sec" + i;
    title = document.createElement("div");
    title.id = "title" + i;
    title.className = "section-title";
    title.innerHTML = response_data[i].title;
    content = document.createElement("div");
    content.id = "content" + i;
    content.className = "section-content";
    section.appendChild(title);
    section.appendChild(content);
    if (typeof(response_data[i].content) == 'string') {
      content.innerHTML = response_data[i].content;
    } else {
      for (var j = 0; j < response_data[i].content.length; j++) {
        subsection = document.createElement("div");
        subsection.id = "subsec" + i + "." + j;
        subtitle = document.createElement("div");
        subtitle.id = "subtitle" + i + "." + j;
        subtitle.className = "subsection-title";
        subtitle.innerHTML = response_data[i].content[j].title;
        subcontent = document.createElement("div");
        subcontent.id = "subcontent" + i + "." + j;
        subcontent.className = "subsection-content";
        subcontent.innerHTML = response_data[i].content[j].content;
        subsection.appendChild(subtitle);
        subsection.appendChild(subcontent);
        content.appendChild(subsection);
      }
    }
    article.appendChild(section);
  }
  var params = JSON.stringify({"doi": sessions[current_article].doi, "type": "references"});
  get_refs.open("POST", "pyreadapi");
  get_refs.send(params);
};

get_refs.onload = function () {
  response_data = JSON.parse(get_refs.response);
  var article = document.getElementsByClassName("article")[0];
  var refs = document.createElement("div");
  refs.id = "refs";
  var refs_title = document.createElement("div");
  refs_title.id = "title-r";
  refs_title.innerHTML = "References";
  refs_title.className = "section-title";
  refs.appendChild(refs_title);
  var ref_list = document.createElement("ol");
  ref_list.id = "ref-list";
  ref_list.className = "section-content";
  refs.appendChild(ref_list);
  for (var i = 0; i < response_data.length; i++) {
    if (response_data[i] == null ||
        Object.keys(response_data[i]).length == 0) {
      response_data[i] = {title: null, doi: null, local: null, authors: null,
                          year: null, journal: null};
    }
    var next_ref = document.createElement("li");
    next_ref.id = "ref" + i;
    var ref_string = "";
    if (response_data[i].authors != null) {
      for (var j = 0; j < response_data[i].authors.length; j++) {
        if (j > 0 && j == response_data[i].authors.length - 1 &&
            response_data[i].authors[j].indexOf("et al.") == -1) {
          ref_string = ref_string + " and ";
        } else if (j > 0) {
          ref_string = ref_string + ", ";
        }
        ref_string = ref_string + response_data[i].authors[j];
      }
      if (ref_string[-1] != "." && ref_string[-1] != ' ') {
        ref_string = ref_string + ".";
      }
    }
    ref_string = ref_string + " " + response_data[i].title;
    ref_string = ref_string + ". " + response_data[i].journal;
    ref_string = ref_string + " " + response_data[i].year;
    next_ref.innerHTML = ref_string;
    ref_list.appendChild(next_ref);
    references = response_data;
  }
  article.appendChild(refs);
  var params = JSON.stringify({"doi": sessions[current_article].doi, "type": "fileinfo"});
  get_fileinfo.open("POST", "pyreadapi");
  get_fileinfo.send(params);
};

get_fileinfo.onload = function() {
  fileinfo = JSON.parse(get_fileinfo.response);
  console.log(fileinfo);
  add_figures();
};

function add_figures() {
  var figures = document.querySelectorAll("figure");
  if (figures.length == 0) {
    after_load();
  }
  for (var i = 0; i < figures.length; i++) {
    if (i == fileinfo.figures.length) {
      break;
    }
    var fname;
    if ("lr" in fileinfo.figures[i]) {
      fname = fileinfo.figures[i].lr;
    } else {
      fname = fileinfo.figures[i].name;
    }
    var params = "doi=" + sessions[current_article].doi + "&type=file" +  "&name=" + fname;
    var caption = document.createElement("div");
    caption.id = "figcap" + i;
    caption.className = "fig-cap";
    caption.innerHTML = fileinfo.figures[i].title;
    figures[i].appendChild(caption);
    var legend = document.createElement("div");
    legend.id = "figleg" + 1;
    legend.className = "fig-leg";
    var img = new Image();
    img_sem++;
    img.src = "/pyreadapi?" + params;
    img.className = "fig-img";
    img.onload = function() {
      img_sem--;
      if (img_sem == 0) {
        after_load();
      }
    };
    legend.appendChild(img);
    var detail = document.createElement("div");
    detail.id = "figdet" + i;
    detail.className = "fig-details";
    detail.innerHTML = fileinfo.figures[i].caption;
    legend.appendChild(detail);
    figures[i].appendChild(legend);
  }
  add_reflinks();
  add_figlinks();
}

function add_reflinks() {
  var ref_links = document.querySelectorAll("span.ref");
  var consec_elems = [];
  for (var i = 0; i <= ref_links.length; i++) {
    var consec = false;
    if (i < ref_links.length &&
        (consec_elems.length == 0 ||
         (ref_links[i-1].nextElementSibling != null &&
          (ref_links[i-1].nextSibling.isSameNode(ref_links[i]) ||
           (ref_links[i-1].nextElementSibling.isSameNode(ref_links[i]) &&
            ref_links[i-1].nextSibling.textContent.trim() == ""))))) {
      consec_elems.push(ref_links[i]);
      consec = true;
    }
    if (!consec || i == ref_links.length) {
      var ref_nums = [];
      for (var j = 0; j < consec_elems.length; j++) {
        ref_nums.push(consec_elems[j].dataset.refnum);
      }
      var ref_str = merge_refs(ref_nums);
      var spans = ref_str.split(",");
      var search = true;
      var prev_elem = consec_elems[0].previousSibling;
      var inside_parens = false;
      while (search && prev_elem != null) {
        for(var k = prev_elem.textContent.length - 1; k >= 0; k--) {
          if (prev_elem.textContent[k] == '(') {
            inside_parens = true;
            search = false;
            break;
          } else if (prev_elem.textContent[k] == ')') {
            search = false;
            break;
          }
        }
        prev_elem = prev_elem.previousSibling;
      }
      var closing_paren = false;
      if (inside_parens) {
        search = true;
        var next_elem = consec_elems[consec_elems.length - 1].nextSibling;
        while (search && next_elem != null) {
          for(var k = 0; k < next_elem.textContent.length; k++) {
            if (next_elem.textContent[k] == ')') {
              closing_paren = true;
              search = false;
              break;
            } else if (next_elem.textContent[k] == '(') {
              search = false;
              break;
            }
          }
          next_elem = next_elem.nextSibling;
        }
      }
      for (var j = 0; j < spans.length; j++) {
        var s = document.createElement("span");
        s.className = "ref";
        s.dataset.refnum = spans[j];
        s.innerHTML = spans[j];
        var slicers = spans[j].split("-");
        if (slicers.length == 2) {
          s.dataset.doi = references.slice(
            slicers[0] - 1, slicers[1]).map(a => a.doi).join(",");
          s.dataset.pmid = references.slice(
            slicers[0] - 1, slicers[1]).map(a => a.pmid).join(",");
          s.dataset.local = references.slice(
            slicers[0] - 1, slicers[1]).map(a => a.local).join(",");
        } else if (references[slicers[0] - 1] != null){
          s.dataset.doi = references[slicers[0] - 1].doi;
          s.dataset.pmid = references[slicers[0] - 1].pmid;
          s.dataset.local = references[slicers[0] - 1].local;
        }
        consec_elems[0].insertAdjacentElement("beforebegin", s);
        if (j == 0 && !inside_parens) {
          s.insertAdjacentText("beforebegin", " (");
        }
        if (j + 1 < spans.length) {
          s.insertAdjacentText("afterend", ",");
        } else if (!inside_parens || !closing_paren){
          s.insertAdjacentText("afterend", ")");
        }
        var reftip = document.createElement("span");
        reftip.className = "ref-tip";
        var num_refs = 1;
        if (slicers.length == 2) {
          num_refs = slicers[1] - slicers[0] + 1;
        }
        s.onmouseover = function() {
          this.childNodes[1].style.transform = "";
          var box = this.childNodes[1].getClientRects()[0];
          var body = document.body.getClientRects()[0];
          if (box.right > body.right) {
            this.childNodes[1].style.transform = "translateX(" +
                                                 (body.right - box.right) +
                                                 "px)";
          } else if (box.left < body.left) {
            this.childNodes[1].style.transform = "translateX(" +
                                                 (body.left - box.left) +
                                                 "px)";
          }
        };
        for (var k = 0; k < num_refs; k++) {
          var reftipcontainer = document.createElement("span");
          reftipcontainer.className = "ref-tip-con";
          (function(slicers, k) {
            reftipcontainer.onclick = function() {
              var ref = references[slicers[0] - 1 + k];
              new_session(ref.doi, ref.title);
            };
          })(slicers, k);
          var reftiplabel = document.createElement("span");
          reftiplabel.className = "ref-tip-label";
          if (references[slicers[0] - 1 + k] != null) {
            var authors = references[slicers[0] - 1 + k].authors;
            var first_auth = null;
            if (authors != null && authors[0] != null) {
              first_auth = authors[0].slice(authors[0].lastIndexOf(' '));
            }
            var year = references[slicers[0] - 1 + k].date;
            if (year != null) {
              year = year.slice(0,4);
            }
            if (authors != null && authors.length == 1) {
              reftiplabel.innerHTML = first_auth + ' ' + year;
            } else {
              reftiplabel.innerHTML = first_auth + ' et al. ' + year;
            }
          }
          var reftiptitle = document.createElement("span");
          reftiptitle.className = "ref-tip-title";
          if (references[slicers[0] - 1 + k] != null) {
            reftiptitle.innerHTML = references[slicers[0] - 1 + k].title;
          }
          reftipcontainer.appendChild(reftiplabel);
          reftipcontainer.appendChild(reftiptitle);
          reftip.appendChild(reftipcontainer);
        }
        s.appendChild(reftip);
      }
      for (var j = 0; j < consec_elems.length; j++) {
        consec_elems[j].remove();
      }
    if (i < ref_links.length) {
      consec_elems = [ref_links[i]];
    }
    }
  }
}

function add_figlinks() {
  fig_types = [["Figure ", "Figures ", "span.figure-ref"],
               ["Table ", "Tables ", "span.table-ref"],
               ["", "", "span.other-ref"]];
  for (var ft of fig_types) {
    var fig_links = document.querySelectorAll(ft[2]);
    var consec_elems = [];
    for (var i = 0; i <= fig_links.length; i++) {
      var consec = false;
      if (i < fig_links.length && (consec_elems.length == 0 ||
                                   elemsAreAdjacent(fig_links[i-1],
                                                    fig_links[i]))) {
        consec_elems.push(fig_links[i]);
        consec = true;
      }
      if (!consec || i == fig_links.length) {
        var search = true;
        var prev_elem = consec_elems[0].previousSibling;
        var inside_parens = false;
        while (search && prev_elem != null) {
          for(var k = prev_elem.textContent.length - 1; k >= 0; k--) {
            if (prev_elem.textContent[k] == '(') {
              inside_parens = true;
              search = false;
              break;
            } else if (prev_elem.textContent[k] == ')') {
              search = false;
              break;
            }
          }
          prev_elem = prev_elem.previousSibling;
        }
        var closing_paren = false;
        if (inside_parens) {
          search = true;
          var next_elem = consec_elems[consec_elems.length - 1].nextSibling;
          while (search && next_elem != null) {
            for(var k = 0; k < next_elem.textContent.length; k++) {
              if (next_elem.textContent[k] == ')') {
                closing_paren = true;
                search = false;
                break;
              } else if (next_elem.textContent[k] == '(') {
                search = false;
                break;
              }
            }
            next_elem = next_elem.nextSibling;
          }
        }
        for (var j = 0; j < consec_elems.length; j++) {
          var fignum = consec_elems[j].dataset.refnum;
          if (fignum[0] == "S") {
            num_index = 2;
          } else {
            num_index = 1;
          }
          var fig_str = fignum.substring(0, num_index) +
                        merge_refs(fignum.substring(num_index).split(","));
          fig_str = fig_str.split(",").join(", ");
          consec_elems[j].innerHTML = fig_str;
          if (j == 0) {
            if (consec_elems.length == 1 && fig_str.indexOf(",") == -1 &&
                fig_str.indexOf("-") == -1) {
              if(!inside_parens) {
                consec_elems[j].insertAdjacentText("beforebegin", " (" +
                                                   ft[0]);
              } else {
                consec_elems[j].insertAdjacentText("beforebegin", " " + ft[0]);
              }
            } else {
              if (!inside_parens) {
                consec_elems[j].insertAdjacentText("beforebegin", " (" +
                                                   ft[1]);
              } else {
                consec_elems[j].insertAdjacentText("beforebegin", " " + ft[1]);
              }
            }
          }
          if (j + 1 < consec_elems.length) {
            consec_elems[j].insertAdjacentText("afterend", ", ");
          } else {
            if (!inside_parens || !closing_paren) {
              consec_elems[j].insertAdjacentText("afterend", ")");
            }
          }
        }
        if (i < fig_links.length) {
          consec_elems = [fig_links[i]];
        }
      }
    }
  }
}

function after_load() {
  make_collapsible();
  setTimeout(function() {
    var ratio = document.documentElement.scrollHeight /
                sessions[current_article].height;
    document.documentElement.scrollTop = sessions[current_article].scroll *
                                         ratio;
    updater = setInterval(save_session, 100);
  }, 500);
}

function make_collapsible() {
  var titles = document.querySelectorAll(".section-title,.subsection-title," +
                                         ".fig-cap");
  titles = Array.from(titles);
  //The Id of the collapsible titles need to be in alphabetical order, with the
  //innermost titles first.
  titles.sort(function(a,b) {return a.id > b.id;});
  for (var i = 0; i < titles.length; i++) {
    titles[i].classList.toggle("active");
    titles[i].nextElementSibling.classList.toggle("active");
    (function(i) {
      titles[i].addEventListener("click", function() {
        this.classList.toggle("active");
        var content = this.nextElementSibling;
        var parent = this.parentElement.parentElement;
        content.classList.toggle("active");
        if (content.style.maxHeight != "0px"){
          parent.style.maxHeight = parent.scrollHeight - content.scrollHeight + "px";
          content.style.maxHeight = "0px";
        } else {
          parent.style.maxHeight = parent.scrollHeight + content.scrollHeight + "px";
          content.style.maxHeight = content.scrollHeight + "px";
        }
        inactive[i] = !inactive[i];
      });
    })(i);
    if (inactive[i]) {
      inactive[i] = !inactive[i];
      titles[i].click();
    }
  }
}
