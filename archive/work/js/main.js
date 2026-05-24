///// Portfolio Stuff
$(document).ready(function(){

    ///// prettyPhoto
    callprettyPhoto();

    function callprettyPhoto() {
        ///// Work around for PrettyPhoto HTML Validation
        $('a.portfolio-zoom[data-rel]').each(function() {
            $(this).attr('rel', $(this).data('rel'));
        });

        ///// Call prettyPhoto
        $("a[rel^='prettyPhoto']").prettyPhoto({deeplinking: false, social_tools: false, show_title: false });
    }

    ///// Quicksand
    var $filterType = $('#filterOptions li.active a').attr('class');
    var $holder = $('ul.holder');
    var $data = $holder.clone();

    $('#filterOptions li a').click(function(e) {
        
        $('#filterOptions li').removeClass('active');
        
        var $filterType = $(this).attr('class');
        $(this).parent().addClass('active');
        
        if ($filterType == 'all') {
            var $filteredData = $data.find('li');
        } 
        else {
            var $filteredData = $data.find('li[data-type~=' + $filterType + ']');
        }
        
        ///// Call quicksand
        $holder.quicksand($filteredData, {
            duration: 800,
            easing: 'easeInOutQuad'
            },
            function() {
                callprettyPhoto();
        });
        return false;
    });
});

///// Tweet Footer
$(document).ready(function(){
jQuery(function($){
        $("#tweet").tweet({
          count: 2,
          username: "wegraphics",
          template: "{text} » {retweet_action}"
        });
      }).bind("loaded", function(){
        $(this).find("a.tweet_action").click(function(ev) {
          window.open(this.href, "Retweet",
                      'menubar=0,resizable=0,width=550,height=420,top=200,left=400');
          ev.preventDefault();
        });
      });
});