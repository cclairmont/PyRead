    // updates all PDF links on the page to link them to the PDF only view and sets them to open in a new window
    $(function()
    {
      $("a[rel='full-text.pdf'],a[rel='view-full-text-pdf-with-supplemental-data'],a[rel='view-full-text.pdf']").each( function( index, element )                                                                                                                                                     
      {
        $(element).attr("href", $(element).attr("href").replace(".pdf+html", ".pdf"));
        $(element).attr("target", "_blank");
      });
    });