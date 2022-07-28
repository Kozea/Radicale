window.addEventListener("DOMContentLoaded", function() {
    function resetSelect(select) {
        for (let option of select.options) {
            option.selected = option.defaultSelected;
        }
    }
    let select = document.querySelector("header .documentBranch select");
    resetSelect(select);
    select.addEventListener("change", function() {
        let option = select.selectedOptions.item(0);
        if (option && !option.defaultSelected) {
            location.assign(option.value);
        }
        resetSelect(select);
    });
});
