window.onload = function() {
  var isFirefox = "undefined" != typeof InstallTrigger;
  var isSafari = 0 < Object.prototype.toString.call(window.HTMLElement).
                 indexOf("Constructor") ||
                 "[object SafariRemoteNotification]" ===
                 (!window.safari || safari.pushNotification).toString();
  var isIE = !!document.documentMode;
  var isEdge = !isIE && !!window.StyleMedia;
  var isChrome = !!window.chrome;
  var isChromiumEdge = !!navigator && !!navigator.userAgent.match(/edg/i);
  var isMobile= !!window.chrome &&
    /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile|CriOS/i.
    test(navigator.userAgent);
  var msg = document.querySelectorAll(".pyread-msg");
  msg[0].textContent = "PyRead was unable to access the full text content for";
  msg[1].textContent = "If you have acccess through your institutional or " +
                       "personal subscription, PyRead can load this " +
                       "article after you log in";
  if (isFirefox) {
    msg[2].textContent = "If you have not done so already, drag the button " +
                         "below to your Bookmarks toolbar.  ";
    msg[3].textContent = "If you don't see your Bookmarks toolbar select \"" +
                         "View > Toolbars > Bookmarks Toolbar\"";
  } else if (isSafari) {
    msg[2].textContent = "If you have not done so already, drag the button " +
                         "below to your Favorites bar.  ";
    msg[3].textContent = "If you don't see your Favorites bar select \"" +
                         "View > Show Favorites Bar\"";
  } else if (isIE) {
    msg[2].textContent = "If you have not done so already, right click the " +
                         "button below and click \"Add to Favorites\"";
    msg[3].textContent = "You may be prompted with a security alert. " +
                         "It is safe to continue.";
  } else if (isChrome) {
    msg[2].textContent = "If you have not done so already, drag the button " +
                         "below to your Bookmarks bar.  ";
    msg[3].textContent = "If you don't see your Bookmarks bar click the " +
                         "three dots (⋮) menu and select \"Bookmarks > Show " +
                         "Bookmarks bar\"";
  } else if (isChromiumEdge) {
    msg[2].textContent = "If you have not done so already, drag the button " +
                         "below to your Bookmarks bar.  ";
    msg[3].textContent = "If you don't see your Bookmarks bar click the " +
                         "three dots (⋮) menu and select \"Favorites > Show " +
                         "Favorites bar > Always\"";
  }
  msg[4].textContent = "When you are ready, please click the link below to " +
                       "be redirected to the webpage for the article you " +
                       "have requested.  Once you have logged in using your " +
                       "instutional or personal credentials, click your " +
                       "PyRead button to add the article to your library";

  var button = document.querySelector('.pyread-btn');
  button.innerHTML = "<a href='javascript:void(function(){location.href=%22" +
                     "http://localhost:8080/pyreadproxy?location=%22+" +
                     "location.href+%22&pyreadcookies=%22+document.cookie})" +
                     "();'>PyRead</a>";
};
