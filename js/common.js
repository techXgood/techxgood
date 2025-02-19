function include(file, selector) {
    fetch(file).then(response => response.text()).then(data => {
            document.querySelector(selector).innerHTML = document.querySelector(selector).innerHTML.concat("\n", data);
        })
};