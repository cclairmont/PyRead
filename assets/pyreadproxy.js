var pyread_counter = 0;
r = new XMLHttpRequest;
s = new XMLHttpRequest;

r.onload = function() {
    console.log("r")
    var response_data = JSON.parse(r.response)
    if (response_data.doi == 'none') {
        scrape();
    } else {
        window.location.replace('pyreadhome?doi=' + response_data.doi)
    }
}

s.onload = function() {
    console.log(s.response)
    var response_data = JSON.parse(s.response);
    if (Object.entries(response_data).length > 0) {
        console.log(s.response);
        var elem = document.createElement(response_data.elem_type);
        elem.innerHTML = response_data.content;
        document.body.appendChild(elem);
    }
    get_info();
}

function scrape() {
    pyread_counter++;
    r.open('POST', 'pyreadscrape');
    r.send(document.documentElement.outerHTML);
}

function get_info() {
   s.open('GET', 'pyreadinfo');
   s.send();
}

scrape();
get_info();
