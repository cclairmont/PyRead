var pyread_counter = 0;
r = new XMLHttpRequest;

r.onload = function() {
    console.log(r.response);
    var response_data = JSON.parse(r.response)
    if (response_data.doi == 'none') {
        scrape();
    } else {
        window.location.replace('pyreadhome?doi=' + response_data.doi)
    }
}

function scrape() {
    pyread_counter++;
    r.open('POST', '?pyreadscrape');
    r.send('url=' + window.location + '&data=' + document.documentElement.outerHTML);
}

scrape();