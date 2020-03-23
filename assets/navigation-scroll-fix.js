window.addEventListener("load", function() {
    for (let link of document.querySelectorAll("nav a")) {
        link.addEventListener("click", function() {
            let fragmentIndex = link.href.indexOf("#");
            let anchor = null;
            if (fragmentIndex >= 0) {
                let fragment = link.href.substring(fragmentIndex + 1, link.href.length);
                anchor = document.getElementById(fragment);
            }
            if (anchor) {
                document.documentElement.scrollTop += anchor.getBoundingClientRect().y;
            } else {
                document.documentElement.scrollTop = 0;
            }
        });
    }
});
