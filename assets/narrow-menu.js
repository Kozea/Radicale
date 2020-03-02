window.addEventListener("load", function() {
    document.querySelector("button[data-name=nav-open]").addEventListener("click", function() {
        document.documentElement.classList.add("nav-opened");
    });
    document.querySelector("button[data-name=nav-close]").addEventListener("click", function() {
        document.documentElement.classList.remove("nav-opened");
    });
    for (let link of document.querySelectorAll("nav a")) {
        link.addEventListener("click", function() {
            if (link.parentElement.classList.contains("active") || link.parentElement.classList.contains("level4")) {
                document.documentElement.classList.remove("nav-opened");
            }
        });
    }
});
