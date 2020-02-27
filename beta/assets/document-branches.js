window.addEventListener("load", function() {
    let select = document.querySelector("header select.documentBranch");
    while (select.firstChild) {
        select.removeChild(select.firstChild);
    }
    for (let branch of documentBranches) {
        let option = document.createElement("option");
        option.textContent = branch;
        if (branch === documentBranch) {
            option.setAttribute("selected", "");
        }
        select.prepend(option);
    }
    select.addEventListener("change", function() {
        if (select.value !== documentBranch) {
            location.assign(select.value + ".html");
            select.value = documentBranch;
        }
    });
});
