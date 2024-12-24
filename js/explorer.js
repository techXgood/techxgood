const order_by_options = [
        {
            "id": "descending_stars",
            "name": "descending stars",
            "description": "order by stars (descending order)",
            "func": (b, a) => a.stars - b.stars
        },
       {
            "id": "ascending_stars",
            "name": "ascending stars",
            "description": "order by stars (ascending order)",
            "func": (a, b) => a.stars - b.stars
       }
];

async function loadFilterCat() {
    const response = await fetch('conf/categories.json');
    var data = await response.json();
    data = data.cat;
    console.log(data);

    const filter_cat = document.getElementById('filter_cat');
    filter_cat.innerHTML = ''; // Clean the contents before adding new cards

    const cat = document.createElement('option');
    cat.value = "All";
    cat.innerHTML = "All";
    filter_cat.appendChild(cat);
    data.forEach(item => {
        const cat = document.createElement('option');
        cat.value = item.id;
        cat.innerHTML = item.name;
        //cat = `<option value="${item.id}">${item.name}</option>`;
        filter_cat.appendChild(cat);
    });
}

async function loadOrderBy() {
    const order_selection = document.getElementById('orderBy');
    order_selection.innerHTML = ''; // Clean the contents before adding new cards

    var order_by = document.createElement('option');
    order_by.value = "None";
    order_by.innerHTML = "All";
    order_selection.appendChild(order_by);
    order_by_options.forEach(item => {
        order_by = document.createElement('option');
        order_by.value = item.id;
        order_by.innerHTML = item.name;
        //cat = `<option value="${item.id}">${item.name}</option>`;
        order_selection.appendChild(order_by);
    });
}

function apply_filter(item, cat = null) {
    const searchTerm = searchInput.value.toLowerCase();
    var filterCatValue = "";
    if (cat !== null) {
        filterCatValue = cat.toLowerCase();
    } else {
        filterCatValue = filter_cat.value.toLowerCase();
    }
    console.log(filterCatValue);

    try {
        term_is_in_title = item.title.toLowerCase().includes(searchTerm);
    } catch (e) {
        term_is_in_title = false;
    }
    const titleMatches = searchTerm === "" || term_is_in_title || item.keywords.includes(searchTerm);
    const categoryMatches = filterCatValue === "all" || item.category.toLowerCase() === filterCatValue;
    //const tagsMatches = filter2Value === "" || item.tags.includes(filter2Value);
    console.log(item, titleMatches, categoryMatches)
    return titleMatches && categoryMatches; //&& tagsMatches;
}

// Function to load data from JSON file
async function loadCards(cat = null) {
    try {
        const response = await fetch('data/projects.json'); // Replace 'data.json' with the correct path
        const data = await response.json();

        const cardGrid = document.getElementById('cardGrid');
        cardGrid.innerHTML = ''; // Clean the contents before adding new cards

        var filtered_data = data.filter(item => apply_filter(item, cat));

        const order_by = orderBy.value.toLowerCase();
        console.log(order_by);
        console.log(order_by_options);
        const sortConf = order_by_options.find(config => config.id === order_by);
        if (sortConf) {
            filtered_data.sort(sortConf.func);
        }

        filtered_data.forEach(item => {
            var website_link_tag = '';
            if ("website" in item && item["website"] !== "") {
                website_link_tag = `
                <br><a href="${item.website}"><img src="imgs/explorer/homepage-icon.png" alt="homepage icons" class="card_homepage_icon"> homepage</a>
                `;
                console.log(website_link_tag);
            }
            var desc = "";
            if ("description" in item) {
                if (item.description === null) {
                    desc = "";
                } else if (item["description"].length > 200) {
                    desc = item.description.slice(0, 200) + '...';
                } else {
                    desc = item.description;
                }
            } else {
                desc = "";
            }
            var poc = "";
            if ("poc" in item && item["poc"] == true) {
                poc = `<p class="card_stats_info">
                           <img src="imgs/explorer/poc-icon.png" alt="poc icon" class="card_stats_icons">
                           PoC
                        </p>`;
            }
            var lang = "";
            // <p style="color: #fee003; margin-right: 5px;">&lt;/&gt;</p>
            if ("language" in item && item["language"] !== "") {
                lang = `<p class="card_stats_info">
                            <img src="imgs/explorer/code-icon.png" alt="code icon" class="card_stats_icons">
                            ${item.language}
                        </p>`;
            }
            var stars = "";
            if ("stars" in item && item["stars"] !== "") {
                stars = `<p class="card_stats_info">
                            <img src="imgs/explorer/star-icon.png" alt="star icon" class="card_stats_icons">
                            ${item.stars}
                        </p>`;
            }
            const card = document.createElement('div');
            card.className = 'card';

            // generic
            var repo_logo = "homepage-icon.png";
            var repo_logo_class = "card_github_logo";
            if (item.repo.includes("github.com")) {
                repo_logo = "github-logo.png";
                repo_logo_class = "card_github_logo";
            } else if (item.repo.includes("gitlab.com")) {
                repo_logo = "gitlab-logo.png";
                repo_logo_class = "card_gitlab_logo";
            }
            console.log(repo_logo);
            console.log(repo_logo_class);
            card.innerHTML = `
                <div>
                    <div class="card-overview">
                        <h3 class="oxanium-title-img">${item.title}</h3>
                        <p>${desc}</p>
                    </div>
                    <hr>
                    <div class="card-links">
                        <a href="${item.repo}">
                            <img src="imgs/explorer/${repo_logo}" class="${repo_logo_class}">
                            code
                        </a>
                        ${website_link_tag}
                    </div>
                    <hr>
                    <div class="card_category">
                        <div class="category_item">
                            <img class="card-category-img" src="imgs/explorer/category/${item.category}.png">
                            <p>${item.category}</p>
                        </div>
                    </div>
                    <hr>
                    <div class="card_stats">
                        ${lang}
                        ${stars}
                        ${poc}
                    </div>
                </div>
            `;
        cardGrid.appendChild(card);
        });
    } catch (error) {
        console.error('Error while loading data:', error);
    }
}


/* call functions */
loadFilterCat();
loadOrderBy();

const urlParams = new URL(document.URL).searchParams;
const cat = urlParams.get("cat");
console.log(cat)
window.onload = loadCards(cat);