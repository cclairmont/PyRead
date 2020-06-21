var get_content = new XMLHttpRequest();
var get_refs = new XMLHttpRequest();
var get_info = new XMLHttpRequest();
var metadata;
var queries;
var references;
var img_sem = 0;

function after_load() {
  var cookies = {};
  document.cookie.split(";").map(function(a) {
    var kv = a.split("=");
    cookies[kv[0]] = kv[1];
  });
  cookie = cookies.session;
  var sessions = {};
  if (cookie != null) {
    cookie.split(",").map(function(a) {
      var kv = a.split(":");
      sessions[kv[0]] = {scroll: kv[1], inactive: kv[2]};
    });
  }
  if (sessions[queries.doi] == null) {
    sessions[queries.doi] = {scroll: 0, inactive: 0};
  }
}

function add_figures() {
  var figures = document.querySelectorAll("figure");
  for (var i = 0; i < figures.length; i++) {
    if (i == metadata.figures.length) {
      break;
    }
    var fname;
    if ("lr" in metadata.figures[i]) {
      fname = metadata.figures[i].lr;
    } else {
      fname = metadata.figures[i].name;
    }
    var params = "doi=" + queries.doi + "&type=file&name=" + fname;
    var caption = document.createElement("div");
    caption.id = "figcap" + i;
    caption.className = "fig-cap";
    caption.innerHTML = metadata.figures[i].title;
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
    detail.innerHTML = metadata.figures[i].caption;
    legend.appendChild(detail);
    figures[i].appendChild(legend);
  }
  make_collapsible();
  add_reflinks();
  add_figlinks();
}

function make_collapsible() {
  var titles = document.querySelectorAll(".section-title,.subsection-title," +
                                         ".fig-cap");
  for (var i = 0; i < titles.length; i++) {
    titles[i].classList.toggle("active");
    titles[i].addEventListener("click", function() {
      this.classList.toggle("active");
      var content = this.nextElementSibling;
      var parent = this.parentElement.parentElement;
      if (content.style.maxHeight != "0px"){
        parent.style.maxHeight = parent.scrollHeight - content.scrollHeight + "px";
        content.style.maxHeight = "0px";
      } else {
        parent.style.maxHeight = parent.scrollHeight + content.scrollHeight + "px";
        content.style.maxHeight = content.scrollHeight + "px";
      }
    });
  }
}

function elemsAreAdjacent(e1, e2) {
  if (e1.parentElement.isSameNode(e2.parentElement)) {
    var p_html = e1.parentElement.innerHTML;
    var c1_html = e1.outerHTML;
    var c2_html = e2.outerHTML;
    var distance = p_html.indexOf(c2_html) - p_html.indexOf(c1_html);
    if (distance == c1_html.length) {
      return true;
    } else {
      return false;
    }
  } else {
    return false;
  }
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
          ref_str = ref_str + ref_list[i - num_consec - 1] + "-" + ref_list[i - 1] + ",";
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

function add_reflinks() {
  var ref_links = document.querySelectorAll("span.ref");
  var consec_elems = [];
  for (var i = 0; i < ref_links.length; i++) {
    var consec = false;
    if (consec_elems.length == 0 ||
        elemsAreAdjacent(ref_links[i-1], ref_links[i])) {
      consec_elems.push(ref_links[i]);
      consec = true;
    }
    if (!consec || i + 1 == ref_links.length) {
      var ref_nums = [];
      for (var j = 0; j < consec_elems.length; j++) {
        ref_nums.push(consec_elems[j].dataset.refnum);
      }
      var ref_str = merge_refs(ref_nums);
      var spans = ref_str.split(",");
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
        } else {
          s.dataset.doi = references[slicers[0] - 1].doi;
          s.dataset.pmid = references[slicers[0] - 1].pmid;
          s.dataset.local = references[slicers[0] - 1].local;
        }
        consec_elems[0].insertAdjacentElement("beforebegin", s);
        if (j == 0) {
          s.insertAdjacentText("beforebegin", " (");
        }
        if (j + 1 < spans.length) {
          s.insertAdjacentText("afterend", ",");
        } else {
          s.insertAdjacentText("afterend", ")");
        }
      }
      for (var j = 0; j < consec_elems.length; j++) {
        consec_elems[j].remove();
      }
    consec_elems = [ref_links[i]];
    }
  }
}

function add_figlinks() {
  var fig_links = document.querySelectorAll("span.figure_ref");
  var consec_elems = [];
  for (var i = 0; i < fig_links.length; i++) {
    var consec = false;
    if (consec_elems.length == 0 ||
        elemsAreAdjacent(fig_links[i-1], fig_links[i])) {
      consec_elems.push(fig_links[i]);
      consec = true;
    }
    if (!consec || i + 1 == fig_links.length) {
      for (var j = 0; j < consec_elems.length; j++) {
        var fignum = consec_elems[j].dataset.fignum;
        var file = fignum.indexOf("-");
        if (file > -1) {
          fignum = fignum.substring(0, file);
        }
        if (fignum[0] == "S") {
          num_index = 2;
        } else {
          num_index = 1;
        }
        var fig_str = fignum.substring(0, num_index) +
                      merge_refs(fignum.substring(num_index).split(","));
        consec_elems[j].innerHTML = fig_str;
        if (j == 0) {
          if (consec_elems.length == 1 && fig_str.indexOf(",") == -1 &&
              fig_str.indexOf("-") == -1) {
            consec_elems[j].insertAdjacentText("beforebegin", " (Figure ");
          } else {
            consec_elems[j].insertAdjacentText("beforebegin", " (Figures ");
          }
        }
        if (j + 1 < consec_elems.length) {
          consec_elems[j].insertAdjacentText("afterend", ",");
        } else {
          consec_elems[j].insertAdjacentText("afterend", ")");
        }
      }
      consec_elems = [fig_links[i]];
    }
  }
}

function parse_args(uri) {
  var arg_start = uri.indexOf("\?");
  var q_string = uri.substring(arg_start+1);
  var result = Object();
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

get_content.onload = function () {
  /*Section order should be: Intro, Results,
    Discussion, Methods, Acknowledgments*/
  var response_data = JSON.parse(get_content.response);
  for (var i = 0; i < response_data.length; i++) {
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
    document.body.appendChild(section);
  }
  var params = "doi=" + queries.doi + "&type=references";
  get_refs.open("POST", "pyreadapi");
  get_refs.send(params);
};

get_refs.onload = function () {
  response_data = JSON.parse(get_refs.response);
  var refs = document.createElement("div");
  refs.id = "refs";
  var refs_title = document.createElement("div");
  refs_title.id = "refs-title";
  refs_title.innerHTML = "References";
  refs_title.className = "section-title";
  refs.appendChild(refs_title);
  var ref_list = document.createElement("ol");
  ref_list.id = "ref-list";
  ref_list.className = "section-content";
  refs.appendChild(ref_list);
  for (var i = 0; i < response_data.length; i++) {
    if (Object.keys(response_data[i]).length == 0) {
      continue;
    }
    var next_ref = document.createElement("li");
    next_ref.id = "ref" + i;
    var ref_string = "";
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
    ref_string = ref_string + " " + response_data[i].title;
    ref_string = ref_string + ". " + response_data[i].journal;
    ref_string = ref_string + " " + response_data[i].year;
    next_ref.innerHTML = ref_string;
    ref_list.appendChild(next_ref);
    references = response_data;
  }
  document.body.appendChild(refs);
  var params = "doi=" + queries.doi + "&type=info";
  get_info.open("POST", "pyreadapi");
  get_info.send(params);
};

get_info.onload = function() {
  metadata = JSON.parse(get_info.response);
  add_figures();
};

queries = parse_args(location.href);
get_content.open("POST", "pyreadapi");
var params = "doi=" + queries.doi + "&type=content";
get_content.send(params);
