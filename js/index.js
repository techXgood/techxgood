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
        console.error('Cannot load categories:', error);
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
        console.error('Cannot load stats', error);
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


async function loadStats() {
    try {
        // Assicurati che il percorso sia corretto (es. data/projects.json)
        const response = await fetch('data/projects.json');
        const projects = await response.json();

        // 1. Calcolo Totale Progetti
        const totalProjects = projects.length;
        animateValue("totalProjects", 0, totalProjects, 1500);

        // 2. Calcolo Totale Stelle
        const totalStars = projects.reduce((acc, curr) => acc + (curr.stars || 0), 0);
        animateValue("totalStars", 0, totalStars, 1500);

        // 3. Logica per Linguaggi (Top 10)
        const langCounts = {};
        projects.forEach(p => {
            if (p.language) {
                langCounts[p.language] = (langCounts[p.language] || 0) + 1;
            }
        });

        const sortedLangs = Object.entries(langCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10);

        renderPieChart(sortedLangs);

        // 4. Logica per Keywords (Top 20)
        const keywordCounts = {};
        projects.forEach(p => {
            if (p.keywords && Array.isArray(p.keywords)) {
                p.keywords.forEach(k => {
                    // Normalizza keyword (lowercase)
                    const key = k.toLowerCase();
                    keywordCounts[key] = (keywordCounts[key] || 0) + 1;
                });
            }
        });

        const sortedKeywords = Object.entries(keywordCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 20);

        renderWordCloud(sortedKeywords);

    } catch (error) {
        console.error('Cannot load stats:', error);
    }
}

// Funzione per animare i numeri
function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    if(!obj) return;
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start).toLocaleString();
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

function renderPieChart(dataArray) {
    const ctx = document.getElementById('languagesChart');
    if(!ctx) return;

    new Chart(ctx, {
        type: 'doughnut', // o 'pie'
        data: {
            labels: dataArray.map(i => i[0]),
            datasets: [{
                data: dataArray.map(i => i[1]),
                backgroundColor: [
                    '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51', '#264653',
                    '#8ab17d', '#b5e48c', '#52b788', '#40916c', '#1b4332'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
}

function renderWordCloud(dataArray) {
    const canvas = document.getElementById('keywordsCloud');
    if(!canvas) return;

    // Il canvas deve avere dimensioni fisiche impostate
    canvas.width = canvas.parentElement.offsetWidth;
    canvas.height = canvas.parentElement.offsetHeight;

    // Fattore di scala per rendere le parole visibili
    // Trova il conteggio massimo per normalizzare
    const maxCount = dataArray[0][1];

    // Formatta per wordcloud2: [[word, size], ...]
    const list = dataArray.map(([word, count]) => {
        // Scala la dimensione: min 12px, max 60px
        const size = 15 + ((count / maxCount) * 50);
        return [word, size];
    });

    WordCloud(canvas, {
        list: list,
        gridSize: 8,
        weightFactor: 1,
        fontFamily: 'Arial, sans-serif',
        color: 'random-dark',
        rotateRatio: 0.5,
        rotationSteps: 2,
        backgroundColor: '#ffffff',
        drawOutOfBound: false
    });
}


/* Call functions at the end of loading */
//loadPartners();
loadCategories();
//toggleMenu();
loadStats();
