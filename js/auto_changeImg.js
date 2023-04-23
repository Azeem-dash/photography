$(function () {
  function displayNextImage() {
    x = x === images.length - 1 ? 0 : x + 1;
    console.log("images[x] ", images[x]);
    document.getElementById("ChangeIMG").src = images[x];
  }

  function displayPreviousImage() {
    x = x <= 0 ? images.length - 1 : x - 1;
    document.getElementById("ChangeIMG").src = images[x];
  }

  setInterval(displayNextImage, 4000);

  var images = [],
    x = -1;
//   images[0] = "../asset/photos/me.jpeg";
  images[0] = "../asset/photos/me2.jpeg";
//   images[2] = "../asset/photos/me3.jpeg";
  images[1] = "../asset/photos/me4.jpeg";
  images[2] = "../asset/photos/me5.jpeg";
  images[3] = "../asset/photos/me6.jpeg";
  images[4] = "../asset/photos/me7.jpeg";
  images[5] = "../asset/photos/me.jpeg";

});
