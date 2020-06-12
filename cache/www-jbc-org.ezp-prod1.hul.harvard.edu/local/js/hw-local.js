$(document).ready(function(){
	updateFormInput("#search-keyword", "#header-qs-input-keyword", '#7a7a7a', '');
	updateFormInput("#search-author", "#header-qs-input-author", '#7a7a7a', '');
	updateFormInput("#search-year", "#header-qs-input-year", '#7a7a7a', '');
	updateFormInput("#search-vol", "#header-qs-input-vol", '#7a7a7a', '');
	updateFormInput("#search-page", "#header-qs-input-page", '#7a7a7a', '');

  // $('#col-2 #article-cb-main .cb-contents .cb-views ol li.primary').last().next().css( "margin-top", "10px" );

  // Author's Choice
  $('#content-block ul li .open-access-note, #content-block ol li .open-access-note, #content-block .cit .open-access-note').each(function(){
    var oaNote = $(this).text().toLowerCase();
    if (oaNote == "author's choice") {
        $(this).css("display","none");
        $(this).parent().parent().parent().prepend('<div class="authors-choice">' + oaNote +  '</div>');
        $(this).parent().parent().parent().css("padding-bottom","0");
    }
  })

  var coverRightH = $('#pageid-home .new-at-jbc .home-cover-right').height();
  if (coverRightH > 200 ) {
	console.log('height: ' + coverRightH);
	$('#pageid-home .new-at-jbc .cover-img-wrap').css("height",coverRightH);
  }

  // content top
  $('#pageid-content #content-block').each(function(){
    var crossMark = $(this).find('.crossmark-logo');
    if (crossMark.length) {
	crossMark.css("padding-top","20px");
    } else {
	$(this).find('.article').css("padding-top","20px");
    }

    $(this).children('div').last().css("padding-bottom","45px");
  })

  // adjust qs position in pdf frame
  var requestUrl = window.location.pathname;
  if (document.querySelector('#pageid-login') == null && requestUrl.indexOf('full.pdf+html') != -1) {
        $('#header div#header-qs-jbc.header-qs').css("top","145px");
  }

    // decoding html entities in institution name
    $('.subscr-ref').each(function(a,b){$(b).html($(b).text())})

});

