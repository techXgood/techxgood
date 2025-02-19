function include(file, selector, where = "bottom") {
    fetch(file).then(response => response.text()).then(data => {
            let inner_html = document.querySelector(selector).innerHTML
            if (where == "bottom") {
                document.querySelector(selector).innerHTML = inner_html.concat("\n", data);
            } else if (where == "top") {
                document.querySelector(selector).innerHTML = data.concat("\n", inner_html);
            } else {
                throw "Unknown value for 'where' parameter";
            }
        })
};