$(function () {
  function displayNextImage() {
    x = x === images.length - 1 ? 0 : x + 1;
    console.log("images[x] ", images[x]);
    document.getElementById("home").style = `background-image: url(${images[x]})`
    
  }

  function displayPreviousImage() {
    x = x <= 0 ? images.length - 1 : x - 1;
    document.getElementById("home").style = `background-image: url(${images[x]})`
  }

  setInterval(displayNextImage, 4000);

  var images = [],
    x = -1;
  //   images[0] = "../asset/photos/me.jpeg";
  images[0] = "../asset/photos/102.jpg";
  //   images[2] = "../asset/photos/me3.jpeg";
  images[1] = "../asset/photos/88.jpg";
  images[2] = "../asset/photos/95.jpg";
  images[3] = "../asset/photos/86.jpg";
  images[4] = "../asset/photos/100.jpg";
  images[5] = "../asset/photos/92.jpg";
});
