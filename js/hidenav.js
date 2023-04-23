$(function () {
  var boolean;
  var t;
  document.addEventListener("scroll", function (e) {
//     document.getElementById("navbar").style.display = "block";
    $("#navbar").fadeIn(500);
    clearTimeout(t);
    checkScroll();
  });

  function checkScroll() {
    t = setTimeout(function () {
	$("#navbar").fadeOut(500);
//       document.getElementById("navbar").style.display = "none";
         
    }, 1500); /* You can increase or reduse timer */
  }
});
