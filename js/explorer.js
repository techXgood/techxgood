// Utility function to clear and populate a dropdown
function populateDropdown(elementId, options, defaultOption = { value: "None", label: "All" }) {
    const dropdown = document.getElementById(elementId);
    dropdown.innerHTML = ""; // Clear existing options

    const defaultOptionElement = document.createElement('option');
    defaultOptionElement.value = defaultOption.value;
    defaultOptionElement.textContent = defaultOption.label;
    dropdown.appendChild(defaultOptionElement);

    options.forEach(option => {
        const optionElement = document.createElement('option');
        optionElement.value = option.id || option.value;
        optionElement.textContent = option.name || option.label;
        dropdown.appendChild(optionElement);
    });
}

// Load categories from a JSON file and populate the filter dropdown
async function loadFilterCategories() {
    try {
        const response = await fetch('conf/categories.json');
        const { cat } = await response.json();
        populateDropdown('filter_cat', cat.map(c => ({ id: c.id, name: c.name })));
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

// Load order-by options from the configuration file
async function loadOrderByConfig() {
    try {
        const response = await fetch('conf/order_by_options.json');
        const data = await response.json();

        // Parse and convert function strings to actual functions
        orderByOptions = data.map(option => ({
            ...option,
            func: new Function('a', 'b', `return ${option.func};`) // Safely convert string to function
        }));

        // Populate the dropdown once the options are loaded
        populateDropdown('orderBy', orderByOptions);
    } catch (error) {
        console.error('Error loading order-by configuration:', error);
    }
}

// Apply filtering logic based on title, keywords, and category
function applyFilter(item, categoryFilter = null) {
    const searchTerms = searchInput.value.toLowerCase();
    const selectedCategory = categoryFilter?.toLowerCase() || filter_cat.value.toLowerCase();

    const titleMatches = searchTerms === "" ||
                         item.title?.toLowerCase()?.split()?.some(word => searchTerms.toLowerCase().split(" ")?.includes(word)) ||
                         item.keywords?.some(word => searchTerms.toLowerCase().split(" ")?.includes(word));
    const categoryMatches = selectedCategory === "all" || item.category.toLowerCase() === selectedCategory;

    return titleMatches && categoryMatches;
}

function createCard(item) {
    const template = document.getElementById('card-template');
    const card = template.content.cloneNode(true);

    // Determine repository type
    const repoType = item.repo.includes("github.com") ? "github" :
                     item.repo.includes("gitlab.com") ? "gitlab" : "homepage";

    // Populate card details
    const description = item.description?.length > 200
                        ? `${item.description.slice(0, 200)}...`
                        : item.description || "";

    card.querySelector('.oxanium-title-img').textContent = item.title || 'Untitled';
    card.querySelector('.card-description').textContent = description;

    const repoLink = card.querySelector('.repo-link');
    repoLink.href = item.repo;
    repoLink.querySelector('.repo-logo').src = `imgs/explorer/${repoType}-logo.png`;
    repoLink.querySelector('.repo-logo').className = `card_${repoType}_logo`;

    if (item.website) {
        card.querySelector('.website-link').innerHTML = `
            <br><a href="${item.website}">
                <img src="imgs/explorer/homepage-icon.png" alt="homepage icon" class="card_homepage_icon">
                homepage
            </a>`;
    }

    const categoryImg = card.querySelector('.card-category-img');
    categoryImg.src = `imgs/explorer/category/${item.category}.png`;
    card.querySelector('.card-category-name').textContent = item.category;

    const statsContainer = card.querySelector('.card_stats');
    if (item.language) {
        statsContainer.querySelector('.language').innerHTML = `
            <img src="imgs/explorer/code-icon.png" class="card_stats_icons">
            ${item.language}`;
    }
    if (item.stars) {
        statsContainer.querySelector('.stars').innerHTML = `
            <img src="imgs/explorer/star-icon.png" class="card_stats_icons">
            ${item.stars}`;
    }
    if (item.poc) {
        statsContainer.querySelector('.poc').innerHTML = `
            <img src="imgs/explorer/poc-icon.png" class="card_stats_icons">
            PoC`;
    }

    return card;
}

async function loadTemplate() {
    const response = await fetch('card.html');
    const templateHTML = await response.text();
    document.body.insertAdjacentHTML('beforeend', templateHTML);
}

// Load and display cards based on filter and sort options
async function loadCards(categoryFilter = null) {
    try {
        const response = await fetch('data/projects.json');
        const data = await response.json();

        const filteredData = data.filter(item => applyFilter(item, categoryFilter));

        const order_by = orderBy.value.toLowerCase();
        const sortConfig = orderByOptions.find(option => option.id === order_by);
        if (sortConfig) {
            console.log(sortConfig.func);
            filteredData.sort(sortConfig.func());
        }

        const cardGrid = document.getElementById('cardGrid');
        cardGrid.innerHTML = ""; // Clear existing cards
        filteredData.forEach(item => cardGrid.appendChild(createCard(item)));
    } catch (error) {
        console.error('Error loading cards:', error);
    }
}

/* Initialize functions */
window.onload = async () => {
    await loadTemplate(); // Load templates
    await loadFilterCategories();
    await loadOrderByConfig();

    const urlParams = new URL(document.URL).searchParams;
    const category = urlParams.get("cat");
    await loadCards(category);
};
