// Data files, downloaded once and shared by the search box, the categories and the stats
const projectsPromise = fetch('data/projects.json').then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
});
const categoriesPromise = fetch('conf/categories.json')
    .then(response => response.json())
    .then(data => data.cat);

// projects already downloaded (used by "Surprise me" without waiting)
let loadedProjects = null;

function explorerUrl(params) {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value));
    const text = query.toString();
    return text ? `explorer.html?${text}` : 'explorer.html';
}

/* ------------------ */
/* --- Categories --- */
/* ------------------ */

// Category chips under the search box and category cards: built with the DOM, without innerHTML
async function loadCategories() {
    try {
        const categories = await categoriesPromise;
        const chips = document.getElementById('heroChips');
        const cardGrid = document.getElementById('categories-grid');
        chips.textContent = '';
        cardGrid.textContent = '';

        categories.forEach((item, index) => {
            const chip = document.createElement('a');
            chip.className = 'chip';
            chip.href = explorerUrl({ cat: item.id });
            chip.dataset.category = item.id;
            chip.style.setProperty('--i', index);
            const icon = document.createElement('img');
            icon.src = `imgs/explorer/category/${encodeURIComponent(item.id)}.png`;
            icon.alt = '';
            chip.append(icon, item.name);
            chips.appendChild(chip);

            const card = document.createElement('a');
            card.className = 'category-card reveal';
            card.href = explorerUrl({ cat: item.id });
            card.style.setProperty('--reveal-delay', index % 3);
            const image = document.createElement('img');
            image.src = item.preview_img;
            image.alt = '';
            image.loading = 'lazy';
            const count = document.createElement('span');
            count.className = 'category-count';
            count.dataset.category = item.id;
            count.hidden = true;
            const body = document.createElement('div');
            body.className = 'category-body';
            const title = document.createElement('h3');
            title.textContent = item.name;
            const description = document.createElement('p');
            description.textContent = item.description;
            const cta = document.createElement('span');
            cta.className = 'category-cta';
            cta.textContent = 'Explore →';
            body.append(title, description, cta);
            card.append(image, count, body);
            cardGrid.appendChild(card);
        });
        observeReveal(cardGrid.querySelectorAll('.reveal'));

        // a chip keeps the words already typed in the search box
        chips.addEventListener('click', (event) => {
            const chip = event.target.closest('.chip');
            const query = document.getElementById('searchInput').value.trim();
            if (chip && query) {
                event.preventDefault();
                window.location.href = explorerUrl({ q: query, cat: chip.dataset.category });
            }
        });

        // number of projects of each category, on the cards
        const projects = await projectsPromise;
        const counts = {};
        projects.forEach(p => { counts[p.category] = (counts[p.category] || 0) + 1; });
        cardGrid.querySelectorAll('.category-count').forEach(badge => {
            const count = counts[badge.dataset.category] || 0;
            badge.textContent = `${count.toLocaleString('en')} projects`;
            badge.hidden = false;
        });
    } catch (error) {
        console.error('Cannot load categories:', error);
    }
}

/* ---------------------------- */
/* --- Search box: suggestions --- */
/* ---------------------------- */

function buildSearchIndex(projects) {
    // keywords ranked by number of projects using them
    const keywordCounts = new Map();
    projects.forEach(p => {
        const keywords = Array.isArray(p.keywords) ? p.keywords : [];
        new Set(keywords.map(k => String(k).toLowerCase())).forEach(k => {
            keywordCounts.set(k, (keywordCounts.get(k) || 0) + 1);
        });
    });
    const keywords = [...keywordCounts.entries()]
        .filter(([keyword, count]) => count >= 2 && keyword.length >= 2)
        .sort((a, b) => b[1] - a[1]);

    const items = projects
        .map(p => {
            const title = String(p.title || '');
            return { title, name: title.toLowerCase().split('/').pop(), lower: title.toLowerCase(), repo: safeUrl(p.repo), stars: p.stars || 0 };
        })
        .filter(p => p.title && p.repo)
        .sort((a, b) => b.stars - a.stars);

    return { keywords, items };
}

// first matches that start with the query, then the ones containing it
function topMatches(list, startsWith, contains, limit) {
    const result = list.filter(startsWith).slice(0, limit);
    if (result.length < limit) {
        list.filter(item => !startsWith(item) && contains(item))
            .slice(0, limit - result.length)
            .forEach(item => result.push(item));
    }
    return result;
}

function getSuggestions(searchIndex, rawQuery) {
    const query = rawQuery.trim().toLowerCase();
    if (!query) return [];
    const suggestions = [{ type: 'search', text: rawQuery.trim() }];
    topMatches(searchIndex.keywords, ([k]) => k.startsWith(query), ([k]) => k.includes(query), 4)
        .forEach(([keyword, count]) => suggestions.push({ type: 'keyword', text: keyword, meta: `${count} projects` }));
    topMatches(searchIndex.items, p => p.name.startsWith(query), p => p.lower.includes(query), 4)
        .forEach(p => suggestions.push({ type: 'project', text: p.title, url: p.repo, meta: `★ ${compactNumber.format(p.stars)}` }));
    return suggestions;
}

// text with the query highlighted, as DOM nodes (project titles come from third-party repositories)
function highlightText(text, query) {
    const fragment = document.createDocumentFragment();
    const start = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
    if (start < 0) {
        fragment.append(text);
        return fragment;
    }
    const mark = document.createElement('mark');
    mark.textContent = text.slice(start, start + query.length);
    fragment.append(text.slice(0, start), mark, text.slice(start + query.length));
    return fragment;
}

function initSuggestions() {
    const form = document.getElementById('searchForm');
    const input = document.getElementById('searchInput');
    const list = document.getElementById('suggestions');
    let searchIndex = null;
    let suggestions = [];
    let active = -1;

    projectsPromise.then(projects => { searchIndex = buildSearchIndex(projects); }).catch(() => {});

    const close = () => {
        list.hidden = true;
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
        active = -1;
    };

    const setActive = (index) => {
        const options = list.querySelectorAll('.suggestion');
        options.forEach(option => option.setAttribute('aria-selected', 'false'));
        active = index;
        if (index >= 0 && options[index]) {
            options[index].setAttribute('aria-selected', 'true');
            options[index].scrollIntoView({ block: 'nearest' });
            input.setAttribute('aria-activedescendant', options[index].id);
        } else {
            input.removeAttribute('aria-activedescendant');
        }
    };

    const choose = (suggestion) => {
        if (suggestion.type === 'project') {
            window.open(suggestion.url, '_blank', 'noopener');
            close();
            return;
        }
        window.location.href = explorerUrl({ q: suggestion.text });
    };

    const render = () => {
        suggestions = searchIndex ? getSuggestions(searchIndex, input.value) : [];
        list.textContent = '';
        if (suggestions.length === 0) {
            close();
            return;
        }
        const query = input.value.trim();
        let lastType = null;
        suggestions.forEach((suggestion, index) => {
            if (suggestion.type !== lastType && suggestion.type !== 'search') {
                const group = document.createElement('li');
                group.className = 'suggestion-group';
                group.setAttribute('role', 'presentation');
                group.textContent = suggestion.type === 'keyword' ? 'Keywords' : 'Projects ↗';
                list.appendChild(group);
            }
            lastType = suggestion.type;

            const option = document.createElement('li');
            option.className = 'suggestion';
            option.id = `suggestion-${index}`;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', 'false');
            option.dataset.index = index;

            const icon = document.createElement('span');
            icon.className = 'suggestion-icon';
            icon.setAttribute('aria-hidden', 'true');
            icon.textContent = { search: '🔎', keyword: '#', project: '📦' }[suggestion.type];

            const text = document.createElement('span');
            text.className = 'suggestion-text';
            if (suggestion.type === 'search') {
                text.append('Search for “', highlightText(suggestion.text, ''), '”');
            } else {
                text.append(highlightText(suggestion.text, query));
            }
            option.append(icon, text);

            if (suggestion.meta) {
                const meta = document.createElement('span');
                meta.className = 'suggestion-meta';
                meta.textContent = suggestion.meta;
                option.append(meta);
            }
            list.appendChild(option);
        });
        list.hidden = false;
        input.setAttribute('aria-expanded', 'true');
        active = -1;
    };

    input.addEventListener('input', render);
    input.addEventListener('focus', () => { if (input.value.trim()) render(); });
    input.addEventListener('blur', close);

    input.addEventListener('keydown', (event) => {
        if (list.hidden) return;
        const count = list.querySelectorAll('.suggestion').length;
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActive((active + 1) % count);
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActive(active <= 0 ? count - 1 : active - 1);
        } else if (event.key === 'Enter' && active >= 0) {
            event.preventDefault();
            choose(suggestions[active]);
        } else if (event.key === 'Escape') {
            close();
        }
    });

    // mousedown would move the focus out of the input (and close the list) before the click
    list.addEventListener('mousedown', (event) => event.preventDefault());
    list.addEventListener('click', (event) => {
        const option = event.target.closest('.suggestion');
        if (option) choose(suggestions[Number(option.dataset.index)]);
    });

    // an empty search opens the full explorer
    form.addEventListener('submit', (event) => {
        if (!input.value.trim()) {
            event.preventDefault();
            window.location.href = explorerUrl({});
        }
    });
}

// Placeholder that "types" some example searches
function initPlaceholderTyping() {
    const input = document.getElementById('searchInput');
    const examples = ['climate', 'open data', 'healthcare', 'renewable energy', 'accessibility',
                      'disaster response', 'education', 'agriculture', 'air quality', 'python'];
    if (prefersReducedMotion) return;

    let example = 0;
    let length = 0;
    let deleting = false;
    const step = () => {
        // stop "typing" while the user is using the search box
        if (document.activeElement === input || input.value) {
            input.placeholder = 'Search projects, keywords, languages…';
            setTimeout(step, 1000);
            return;
        }
        const word = examples[example];
        length += deleting ? -1 : 1;
        input.placeholder = `Search “${word.slice(0, length)}”`;
        let delay = deleting ? 40 : 90;
        if (!deleting && length === word.length) {
            deleting = true;
            delay = 1600;
        } else if (deleting && length === 0) {
            deleting = false;
            example = (example + 1) % examples.length;
            delay = 300;
        }
        setTimeout(step, delay);
    };
    step();
}

// "I'm feeling lucky": opens a random well-known project
function initSurpriseButton() {
    const button = document.getElementById('luckyButton');
    button.addEventListener('click', async () => {
        const projects = loadedProjects || await projectsPromise.catch(() => []);
        const candidates = projects.filter(p => (p.stars || 0) >= 100 && safeUrl(p.repo));
        const pool = candidates.length ? candidates : projects.filter(p => safeUrl(p.repo));
        if (!pool.length) return;
        const project = pool[Math.floor(Math.random() * pool.length)];
        button.classList.remove('is-rolling');
        void button.offsetWidth; // restart the animation
        button.classList.add('is-rolling');
        window.open(safeUrl(project.repo), '_blank', 'noopener');
    });
}

/* ------------- */
/* --- Stats --- */
/* ------------- */

async function loadStats() {
    try {
        // --- 1. Caricamento dati Progetti (JSON locale) ---
        const projects = await projectsPromise;
        loadedProjects = projects;

        // Calcolo Totale Progetti e Totale Stelle
        const totalProjects = projects.length;
        const totalStars = projects.reduce((acc, curr) => acc + (curr.stars || 0), 0);
        document.getElementById('heroCount').textContent = totalProjects.toLocaleString('en');

        // the counters start when the stats are on the screen
        onVisible(document.querySelector('.stats-counters'), () => {
            animateValue("totalProjects", 0, totalProjects, 1500);
            animateValue("totalStars", 0, totalStars, 1800);
        });

        // Generazione Grafici (Linguaggi e Keywords), when visible: the charts animate while appearing
        onVisible(document.querySelector('.stats-charts-container'), () => generateCharts(projects));

        // --- 2. Caricamento Data Ultimo Commit (API GitHub) ---
        const githubResponse = await fetch('https://api.github.com/repos/techXgood/techxgood/commits?path=data/projects.json&page=1&per_page=1');

        if (githubResponse.ok) {
            const commits = await githubResponse.json();
            if (commits.length > 0) {
                // Prendi la data dell'ultimo commit
                const dateString = commits[0].commit.committer.date;
                const dateObj = new Date(dateString);

                // Formatta la data
                const options = { minute: 'numeric', hour: 'numeric', day: 'numeric', month: 'short', year: 'numeric' };
                const formattedDate = dateObj.toLocaleDateString('en-GB', options);

                document.getElementById("lastUpdate").innerText = formattedDate;
            }
        } else {
            console.warn("Cannot retrieve data from GitHub");
        }

    } catch (error) {
        console.error('Cannot load stats:', error);
    }
}

// Funzione di supporto per generare i grafici (spostata qui per pulizia)
function generateCharts(projects) {
    // Logica Linguaggi
    const langCounts = {};
    projects.forEach(p => {
        if (p.language) langCounts[p.language] = (langCounts[p.language] || 0) + 1;
    });
    const sortedLangs = Object.entries(langCounts).sort((a, b) => b[1] - a[1]).slice(0, 10);
    renderPieChart(sortedLangs);

    // Logica Keywords
    const keywordCounts = {};
    projects.forEach(p => {
        if (p.keywords && Array.isArray(p.keywords)) {
            p.keywords.forEach(k => {
                const key = String(k).toLowerCase();
                keywordCounts[key] = (keywordCounts[key] || 0) + 1;
            });
        }
    });
    const sortedKeywords = Object.entries(keywordCounts).sort((a, b) => b[1] - a[1]).slice(0, 20);
    renderWordCloud(sortedKeywords);
}


// Funzione per animare i numeri (rallenta alla fine)
function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    if(!obj) return;
    if (prefersReducedMotion) {
        obj.textContent = end.toLocaleString('en');
        return;
    }
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        obj.textContent = Math.floor(eased * (end - start) + start).toLocaleString('en');
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

// shades of the palette greens, plus yellow and anthracite
const CHART_COLORS = ['#388E3C', '#4CAF50', '#66BB6A', '#81C784', '#A5D6A7',
                      '#FEFF9F', '#4c524d', '#7d837e', '#2E7032', '#C8E6C9'];

function renderPieChart(dataArray) {
    const ctx = document.getElementById('languagesChart');
    if(!ctx || typeof Chart === 'undefined') return;

    Chart.defaults.font.family = '"Oxanium", system-ui, sans-serif';
    Chart.defaults.color = '#4c524d';

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: dataArray.map(i => i[0]),
            datasets: [{
                data: dataArray.map(i => i[1]),
                backgroundColor: CHART_COLORS,
                borderColor: '#f4f4f4',
                borderWidth: 3,
                hoverOffset: 14
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '55%',
            animation: { animateRotate: true, animateScale: true, duration: 1200 },
            plugins: {
                legend: { position: 'bottom', labels: { usePointStyle: true, padding: 14, font: { weight: 600 } } }
            }
        }
    });
}

function renderWordCloud(dataArray) {
    const canvas = document.getElementById('keywordsCloud');
    if(!canvas || dataArray.length === 0 || typeof WordCloud === 'undefined') return;

    // Il canvas deve avere dimensioni fisiche impostate
    canvas.width = canvas.parentElement.offsetWidth;
    canvas.height = canvas.parentElement.offsetHeight;

    // Trova il conteggio massimo per normalizzare
    const maxCount = dataArray[0][1];
    // smaller words on narrow screens, so they all fit
    const scale = Math.min(1, canvas.width / 500);

    // Formatta per wordcloud2: [[word, size], ...] (min 15px, max 65px)
    const list = dataArray.map(([word, count]) => [word, (15 + ((count / maxCount) * 50)) * scale]);
    const colors = ['#388E3C', '#2E7032', '#4c524d', '#4CAF50'];

    WordCloud(canvas, {
        list: list,
        gridSize: Math.round(8 * scale) || 4,
        weightFactor: 1,
        fontFamily: '"Oxanium", system-ui, sans-serif',
        fontWeight: 700,
        color: () => colors[Math.floor(Math.random() * colors.length)],
        rotateRatio: 0.3,
        rotationSteps: 2,
        backgroundColor: getComputedStyle(canvas.closest('.chart-box')).backgroundColor,
        drawOutOfBound: false,
        shrinkToFit: true
    });
}

/* ---------------- */
/* --- Partners --- */
/* ---------------- */

// Function to load data from JSON file
async function loadPartners() {
    const partnersSection = document.getElementById('partners');
    try {
        const response = await fetch('data/partners.json');
        const data = await response.json();
        if (!Array.isArray(data) || data.length === 0) return;
        const cardGrid = document.getElementById('partners-grid');
        cardGrid.textContent = ''; // Clean the contents before adding new cards
        data.forEach(item => {
            const card = document.createElement('div');
            card.className = 'partner-item';
            const link = document.createElement('a');
            link.href = safeUrl(item.website) || '#';
            const image = document.createElement('img');
            image.src = item.preview_img;
            image.alt = item.name;
            link.appendChild(image);
            const name = document.createElement('p');
            name.className = 'partner-name';
            name.textContent = item.name;
            card.append(link, name);
            cardGrid.appendChild(card);
        });
        partnersSection.hidden = false;
    } catch (error) {
        console.error('Cannot load partners', error);
    }
}


/* Call functions at the end of loading */
//loadPartners();
loadCategories();
initSuggestions();
initPlaceholderTyping();
initSurpriseButton();
loadStats();
