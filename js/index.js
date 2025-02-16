// Function to load data from JSON file
async function loadCategories() {
    try {
        const response = await fetch('conf/categories.json'); // Replace 'data.json' with the correct path
        const data = await response.json();
        console.log(data);
        const cardGrid = document.getElementById('categories-grid');
        cardGrid.innerHTML = ''; // Clean the contents before adding new cards
        var cat = data.cat;
        console.log(cat);
        cat.forEach(item => {
            console.log(item);
            const card = document.createElement('div');
            card.className = 'category-item';
            card.innerHTML = `
                <a href="explorer.html?cat=${item.id}">
                    <img src="${item.preview_img}" alt="${item.name}">
                    <strong>${item.name.toUpperCase()}</strong>
                    <div class="banner-content">
                        ${item.description}
                    </div>
                </a>
            `;
            cardGrid.appendChild(card);
            });
    } catch (error) {
        console.error('Errore durante il caricamento dei dati:', error);
    }
}

// Function to load data from JSON file
async function loadPartners() {
    try {
        const response = await fetch('data/partners.json'); // Replace 'data.json' with the correct path
        const data = await response.json();
        console.log(data);
        if (Object.keys(data).length === 0) {
            var partners_section = document.getElementById('partners');
            partners_section.style.display = "none";
        } else {
            const cardGrid = document.getElementById('partners-grid');
            cardGrid.innerHTML = ''; // Clean the contents before adding new cards
            data.forEach(item => {
                console.log(item);
                const card = document.createElement('div');
                card.className = 'partner-item';
                card.innerHTML = `
                    <a href="${item.website}">
                        <img src="${item.preview_img}" alt="${item.name}">
                    </a>
                    <p class="partner-name">${item.name}</p>
                `;
                cardGrid.appendChild(card);
                });
        }
    } catch (error) {
        console.error('Errore durante il caricamento dei dati:', error);
        var partners_section = document.getElementById('partners');
        partners_section.style.display = "none";
    }
}

function toggleMenu() {
    const hamburger = document.querySelector('.hamburger');
    const navbarLinks = document.querySelector('.navbar-links');
    hamburger.classList.toggle('active');
    navbarLinks.classList.toggle('active');
}


/* Call functions */
loadPartners();
loadCategories();
toggleMenu();
