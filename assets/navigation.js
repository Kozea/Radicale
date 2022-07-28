window.addEventListener("DOMContentLoaded", function() {
    function findActiveSection(sections) {
        let result = sections[0];
        for (let [section, link] of sections) {
            if (section.getBoundingClientRect().y > 10) {
                break;
            }
            result = [section, link];
        }
        return result;
    }

    let nav = document.querySelector("nav");
    let sections = [[document.querySelector("main"), null]];
    for (let section of document.querySelectorAll("section")) {
        let id = section.getAttribute("id");
        let link = nav.querySelector("a[href=\\#" + id.replace(/\//g, "\\/") + "]");
        if (link) {
            link = link.parentElement;
            link.classList.remove("active");
            sections.push([section, link]);
        }
    }
    let oldLink = null;
    function updateLink() {
        let [section, link] = findActiveSection(sections);
        while (oldLink) {
            if (oldLink.tagName === "LI") {
                oldLink.classList.remove("active");
                if (!oldLink.classList.contains("level4")) {
                    break;
                }
            }
            oldLink = oldLink.parentElement;
        }
        oldLink = link;
        while (link) {
            if (link.tagName === "LI") {
                link.classList.add("active");
                if (!link.classList.contains("level4")) {
                    break;
                }
            }
            link = link.parentElement;
        }
        if (link) {
            let topLink = link.getBoundingClientRect().y;
            let topNav = nav.getBoundingClientRect().y;
            nav.scrollTop += topLink - topNav - 10;
        } else {
            nav.scrollTop = 0;
        }
    }
    function resizeNav() {
        let height = window.innerHeight - nav.getBoundingClientRect().y;
        nav.style.maxHeight = height > 0 ? height + "px" : "none";
    }
    function updateNav() {
        resizeNav();
        updateLink();
    }
    document.addEventListener("scroll", updateNav);
    window.addEventListener("resize", updateNav);
    updateNav();
});
