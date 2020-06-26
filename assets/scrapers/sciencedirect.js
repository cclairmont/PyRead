function get_identifiers() {
  var doi_elem = document.querySelector("a.doi");
  var link = doi_elem.href;
  var doi_start = link.indexOf("doi.org/") + 8;
  var doi = link.slice(doi_start);
  var title = document.querySelector("span.title-text").textContent;
  return {"doi": doi, "title": title};
}
