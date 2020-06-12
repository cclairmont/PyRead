gSiteOptions.suppressDockedSearchNav = false;
gSiteOptions.suppressFloatingAbsOnThumbnails = 1;

$(document).ready(function() {
	$(".article .teaser").prepend('<h2>Capsule</h2>');
});

$(window).load(function() {
	//add class to col-3 if there's a spanned box
	if ($('#col-2 div.col-span').length) {
	$('#col-2,#col-3').addClass("spanned");
	//add placeholder div to col-3, set height same as spanning div
	$('#col-3.spanned').prepend('<div class="col-span-holder"></div>');
	var boxheight = $($("#col-2 >  div.col-span")[0]).height();
	$('#col-3 div.col-span-holder').css("height",boxheight);
	};

//For Visual Abstract
        $('li.has-thumbnail, div.has-thumbnail').each ( function() {
            var thumbnail = $(this).find('img.cit-thumbnail');
            var thumbnailUrl = thumbnail.attr('src');
// Visual Overview image is the first in figs
 var abstractGraphic = thumbnailUrl.substring(0, thumbnailUrl.indexOf('/embed/')) + "/F1.medium.gif";
            var absUrl = $(this).find('ul.cit-views a[rel=abstract]').attr("href");

            thumbnail.wrap("<a href='" + absUrl + "' />");

            thumbnail.mouseover(function() {
                var popupTop = thumbnail.offset().top;
                var popupLeft = thumbnail.offset().left + thumbnail.width() + 1;

                $("body").append('<div class="visualOverviewPopup" style="position:absolute;text-align:left;z-index:999;top:'+popupTop+'px;left:'+popupLeft+'px;"><img src="'+abstractGraphic+  '"/></div>');

            }).mouseout(function(){
                $('div.visualOverviewPopup').remove();
            });

 })
        $('div.flag-option').find('#mtgabs-option').click(function() {
        $(":radio[id='mtgabs-option']").attr('checked', false);
        $(this).attr('checked', true);
        });



});
