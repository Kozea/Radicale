window.addEventListener("load", function() {
    let select = document.querySelector("header .documentBranch select");
    while (select.length > 0) {
        select.remove(0);
    }
    for (let branch of documentBranches) {
        select.add(new Option(branch, branch, branch === documentBranch, branch === documentBranch), 0);
    }
    select.addEventListener("change", function() {
        if (select.value !== documentBranch) {
            location.assign(encodeURIComponent(select.value + ".html"));
            select.value = documentBranch;
        }
    });
});
