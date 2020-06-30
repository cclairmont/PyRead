var pyread_counter = 0;
var scraper = new XMLHttpRequest();
var injector = new XMLHttpRequest();
var message = new XMLHttpRequest();
var pr_status = [];
var pr_screen;
var pr_image = new Image();

scraper.onload = function() {
    var response_data = JSON.parse(scraper.response);
    if (response_data.doi == 'none') {
        scrape();
    } else {
        window.location.replace('pyreadhome?doi=' + response_data.doi);
    }
};

injector.onload = function() {
    var response_data = JSON.parse(injector.response);
    if (Object.entries(response_data).length > 0) {
        var elem = document.createElement(response_data.elem_type);
        elem.innerHTML = response_data.content;
        document.body.appendChild(elem);
    }
    get_inject();
};

message.onload = function() {
  var response_data = JSON.parse(message.response);
  for (var i = 0; i < response_data.length; i++) {
    if (i >= pr_status.length) {
      var status_container = document.createElement("div");
      status_container.className = "pyreadstatuscontainer";
      status_container.id = "pyrc" + i;
      var status_indicator = document.createElement("div");
      status_indicator.id = "pyrs" + i;
      status_container.appendChild(status_indicator);
      var msg_container = document.createElement("div");
      msg_container.className = "pyreadmsgcontainer";
      msg_container.id = "pyrmc" + i;
      status_container.appendChild(msg_container);
      var msg = document.createElement("div");
      msg.id = "pyrm" + i;
      msg.className = "pyreadmsg";
      msg.innerHTML = response_data[i].caption;
      msg_container.appendChild(msg);
      pr_screen.appendChild(status_container);
      var num_submsg = 0;
    } else {
      var status_indicator = document.querySelector("#pyrs" + i);
      var msg_container = document.querySelector("#pyrmc" + i);
      var num_submsg = pr_status[i].messages.length;
    }
    if (response_data[i].status == "not started") {
      status_indicator.className = "pyreadnotstarted";
    } else if (response_data[i].status == "working") {
      status_indicator.className = "pyreadloader";
    } else if (response_data[i].status == "success") {
      status_indicator.className = "pyreadloaded";
    } else if (response_data[i].status == "fail") {
      status_indicator.className = "pyreadfail";
    }
    for (var j = num_submsg; j < response_data[i].messages.length; j++) {
      submsg = document.createElement("div");
      submsg.className = "pyreadsubmsg";
      submsg.innerHTML = response_data[i].messages[j];
      msg_container.appendChild(submsg);
    }
  }
  pr_status[i] = response_data[i];
  get_msg();
};

function scrape() {
    pyread_counter++;
    scraper.open('POST', 'pyreadscrape');
    scraper.send(document.documentElement.outerHTML);
}

function get_inject() {
   injector.open('GET', 'pyreadinfo');
   injector.send();
}

function get_msg() {
  message.open('GET', 'pyreadstatus');
  message.send();
}

pr_image.onload  = function () {
  scrape();
  get_inject();
  get_msg();
};

window.onload = function() {
  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "/pyreadasset=pyreadproxy.css";
  document.head.appendChild(css);
  pr_screen = document.createElement("div");
  pr_screen.className = "pyreadscreen";
  document.body.appendChild(pr_screen);
  pr_image.src = 'pyreadasset=icons/android-chrome-512x512.png';
};
