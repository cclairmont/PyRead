$(document).ready(function(){
	var headHeight=$('#pageid-pap-index #content-block #pap-header').height();
	if (headHeight) {
		var col2adjHeight=headHeight+10;
		$("#proxied-contents.proxied-column-display #col-2").css("margin-top", (col2adjHeight * -1));
	}
	/* 	Temp hack to correct "withdrawn" relationship type link text in col-2.
		Should be removed after long term solution is implemented. */
	var doi = $('meta[name="citation_doi"]').attr('content');
	if (doi && doi == '10.1074/jbc.C112.403048') {
		$('.cb-section .correction-links a[href="/content/288/33/24163"] span').text('This article has been withdrawn');
	}
	if (doi && doi == '10.1074/jbc.A113.403048') {
		$('.cb-section .retraction-for-article .retraction-for-text').text('Withdrawal of');
	}
});

