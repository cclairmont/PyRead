var xhr = new XMLHttpRequest();

window.onload = function() {
  var script;
  if (document.title.endsWith("ScienceDirect")) {
    script = 'sciencedirect.js';
  }
  if (script != null) {
    s = document.createElement("script");
    s.type = "text/javascript";
    s.src = "/pyreadasset?file=scrapers/" + script;
    s.onload = scrape;
    document.head.appendChild(s);
  }

};

function scrape() {

  /* get_identifiers should return a JSON with the following information  */
  /* {'doi': ..., 'pmid': ..., 'title': ...}.  If possible, the function  */
  /* should return all three identifiers.  If this is not possible, the   */
  /* backend will try to fetch the other identifiers from Pubmed and/or   */
  /* Crossref.  doi is the preferred identifer, followed by pmid.  Giving */
  /* the title alone should be alast resort.                              */

  var id = get_identifiers();
  xhr.onload = function() {
    var res = JSON.parse(xhr.response)
  };
  xhr.open("POST", "/pyreadscrapi");
  xhr.send(JSON.stringify(id));
}
