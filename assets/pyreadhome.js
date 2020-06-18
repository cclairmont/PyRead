var get_content = new XMLHttpRequest();
var get_refs = new XMLHttpRequest();

function after_load() {
  make_collapsible();
  add_reflinks();
}

function make_collapsible() {
  var titles = document.querySelectorAll(".section-title,.subsection-title");
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
      console.log(content);
      console.log(parent);
    });
  }
}

function merge_refs(ref_list) {
  var ref_str = "";
  var num_consec = 0;
  for (var i = 0; i < ref_list.length; i++) {
    if (i == 0) {
      continue;
    } else {
      if (ref_list[i] - ref_list[i - 1] == 1) {
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
  var new_span;
  var adjacent = true;
  for (var i = 0; i < ref_links.length; i++) {
    if (consec_elems.length == 0) {
      consec_elems.push(ref_links[i])
    } else {
      if (ref_links[i - 1].parentElement.isSameNode(ref_links[i].
                                                    parentElement)) {
        var p_html = ref_links[i].parentElement.innerHTML;
        var pr_html = ref_links[i - 1].outerHTML;
        var cr_html = ref_links[i].outerHTML;
        var distance = p_html.indexOf(cr_html) - p_html.indexOf(pr_html)
        if (distance == pr_html.length) {
          consec_elems.push(ref_links[i]);
          adjacent = true;
        } else {
          adjacent = false;
        }
      } else {
        adjacent = false;
      }
      if (!adjacent) {
        var ref_nums = [];
        for (var j = 0; j < consec_elems.length; j++) {
          ref_nums.push(consec_elems[j].dataset.refnum);
        }
        var ref_str = merge_refs(ref_nums);
        console.log(ref_str);
        var spans = ref_str.split(",");
        for (var j = 0; j < spans.length; j++) {
          var s = document.createElement("span");
          s.className = "ref";
          s.dataset.refnum = spans[j];
          s.innerHTML = spans[j]
          consec_elems[0].insertAdjacentElement("beforebegin", s)
          if (j == 0) {
            s.insertAdjacentText("beforebegin", " (");
          }
          if (j + 1 < spans.length) {
            s.insertAdjacentText("afterend", ", ");
          } else {
            s.insertAdjacentText("afterend", ")");
          }
        }
        for (var j = 0; j < consec_elems.length; j++) {
          consec_elems[j].remove();
        }
        consec_elems = [];
      }
    }
  }
}

function parse_args(uri) {
  var arg_start = uri.indexOf("\?");
  var q_string = uri.substring(arg_start+1);
  var result = Object();
  while (true) {
   console.log(q_string);
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
   q_string = q_string.substring(q_end+1)
  }
  return result
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
}

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
    var next_ref = document.createElement("li");
    next_ref.id = "ref" + i;
    var ref_string = "";
    console.log(response_data[i].authors)
    for (var j = 0; j < response_data[i].authors.length; j++) {
      if (j > 0 && j == response_data[i].authors.length - 1 &&
          response_data[i].authors[j].indexOf("et al.") == -1) {
        ref_string = ref_string + " and ";
      } else if (j > 0) {
        ref_string = ref_string + ", "
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
  }
  document.body.appendChild(refs)
  after_load();
}

var queries = parse_args(location.href);
get_content.open('POST', 'pyreadapi')
var params = "doi=" + queries.doi + "&type=content"
get_content.send(params)
params = "doi=" + queries.doi + "&type=references"
get_refs.open('POST', 'pyreadapi')
get_refs.send(params)
