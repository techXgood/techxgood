// Order-by options loaded from conf/order_by_options.json
let orderByOptions = [];
// Categories loaded from conf/categories.json
let categories = [];
// Projects with the lowercase fields used by the search (computed once)
let projects = [];
// Projects matching the current search, in the order they are shown
let results = [];
// Number of results already turned into cards (they are added while scrolling)
let rendered = 0;
let popularKeywords = [];

const PAGE_SIZE = 48;
const MAX_SEARCH_WORDS = 10;
const state = { query: '', category: 'None' };

// Build a sort function from a config entry like { field: "stars", order: "desc" }
function makeComparator({ field, order }) {
    const direction = order === "asc" ? 1 : -1;
    // missing values (e.g. stars = null) count as 0, otherwise the sort result is undefined
    return (a, b) => direction * ((a[field] ?? 0) - (b[field] ?? 0));
}

// Add "<icon> text" to a stats element without using innerHTML
function setStat(element, iconSrc, text, title = '') {
    const icon = document.createElement('img');
    icon.src = iconSrc;
    icon.alt = '';
    icon.className = 'card_stats_icons';
    element.append(icon, text);
    element.title = title;
    element.hidden = false;
}

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

// Load order-by options from the configuration file
async function loadOrderByConfig() {
    try {
        const response = await fetch('conf/order_by_options.json');
        const data = await response.json();

        // Build the sort functions from field/order (no code evaluated from the config file)
        orderByOptions = data.map(option => ({
            ...option,
            func: makeComparator(option)
        }));
    } catch (error) {
        console.error('Error loading order-by configuration:', error);
    }
    // without a search, "best match" keeps the order of the db
    populateDropdown('orderBy', orderByOptions, { value: "None", label: "Best match" });
}

// Load categories from a JSON file and create the filter chips
async function loadFilterCategories() {
    try {
        const response = await fetch('conf/categories.json');
        ({ cat: categories } = await response.json());
    } catch (error) {
        console.error('Error loading categories:', error);
    }
    const chips = document.getElementById('categoryChips');
    chips.textContent = '';
    [{ id: 'None', name: 'All' }, ...categories].forEach(category => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'chip';
        chip.dataset.category = category.id;
        chip.setAttribute('aria-pressed', 'false');
        if (category.id === 'None') {
            chip.append('✨ ');
        } else {
            const icon = document.createElement('img');
            icon.src = `imgs/explorer/category/${encodeURIComponent(category.id)}.png`;
            icon.alt = '';
            chip.append(icon);
        }
        const count = document.createElement('span');
        count.className = 'chip-count';
        chip.append(category.name, count);
        chips.appendChild(chip);
    });
}

async function loadProjects() {
    const response = await fetch('data/projects.json');
    const data = await response.json();
    projects = data.map(prepareProject);

    // keywords used by many projects, suggested when a search finds nothing
    const counts = new Map();
    projects.forEach(p => p.keywordList.forEach(k => counts.set(k, (counts.get(k) || 0) + 1)));
    popularKeywords = [...counts.entries()]
        .filter(([keyword]) => keyword.length >= 3)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8)
        .map(([keyword]) => keyword);
}

// Lowercase copies of the searched fields, computed once instead of at every key press
function prepareProject(item) {
    const title = String(item.title || '').toLowerCase();
    const keywordList = [...new Set((Array.isArray(item.keywords) ? item.keywords : []).map(k => String(k).toLowerCase()))];
    return {
        item,
        title,
        // titles are like "owner/repo-name": split them into single words
        name: title.split('/').pop(),
        titleWords: title.split(/[\s\/_.-]+/).filter(Boolean),
        keywords: new Set(keywordList),
        keywordList,
        language: String(item.language || '').toLowerCase(),
        description: String(item.description || '').toLowerCase(),
        category: String(item.category || '').toLowerCase(),
    };
}

function getSearchWords(query) {
    return query.toLowerCase().split(/[\s,]+/).filter(Boolean).slice(0, MAX_SEARCH_WORDS);
}

// Relevance of a project for the searched words (0 = not matching)
function scoreProject(p, words) {
    if (words.length === 0) return 1;
    let score = 0;
    let matchedWords = 0;
    for (const word of words) {
        let wordScore = 0;
        if (p.name === word) wordScore += 12;
        else if (p.titleWords.includes(word)) wordScore += 8;
        else if (p.title.includes(word)) wordScore += 5;
        if (p.keywords.has(word)) wordScore += 4;
        else if (word.length >= 3 && p.keywordList.some(k => k.startsWith(word))) wordScore += 2;
        if (p.language === word) wordScore += 3;
        if (word.length >= 3 && p.description.includes(word)) wordScore += 1;
        if (wordScore > 0) matchedWords++;
        score += wordScore;
    }
    // projects matching all the words come first
    return matchedWords === words.length ? score * 2 : score;
}

// Filter, sort and show the projects for the current search
function runSearch() {
    const words = getSearchWords(state.query);
    const scored = [];
    projects.forEach(p => {
        const score = scoreProject(p, words);
        if (score > 0) scored.push({ p, score });
    });

    // number of results of each category, shown on the chips
    const counts = { None: scored.length };
    scored.forEach(({ p }) => { counts[p.category] = (counts[p.category] || 0) + 1; });
    updateChips(counts);

    const filtered = state.category === 'None'
        ? scored
        : scored.filter(({ p }) => p.category === state.category);

    const sortConfig = orderByOptions.find(option => option.id === orderBy.value);
    if (sortConfig) {
        filtered.sort((a, b) => sortConfig.func(a.p.item, b.p.item));
    } else if (words.length) {
        filtered.sort((a, b) => b.score - a.score || (b.p.item.stars ?? 0) - (a.p.item.stars ?? 0));
    }

    results = filtered.map(({ p }) => p.item);
    rendered = 0;
    const cardGrid = document.getElementById('cardGrid');
    cardGrid.textContent = ''; // Clear existing cards
    cardGrid.setAttribute('aria-busy', 'false');
    renderNextPage();
    updateSummary(words);
    updateEmptyState(words, counts);
    syncUrl();
}

function renderNextPage() {
    const cardGrid = document.getElementById('cardGrid');
    const fragment = document.createDocumentFragment();
    results.slice(rendered, rendered + PAGE_SIZE).forEach((item, index) => {
        fragment.appendChild(createCard(item, index));
    });
    rendered = Math.min(rendered + PAGE_SIZE, results.length);
    cardGrid.appendChild(fragment);

    const loadMore = document.getElementById('loadMore');
    loadMore.hidden = rendered >= results.length;
    watchLoadMore();
}

// next cards when the end of the list gets close (the button stays as fallback)
let loadMoreObserver = null;
function watchLoadMore() {
    const loadMore = document.getElementById('loadMore');
    if (!('IntersectionObserver' in window) || loadMore.hidden) return;
    if (!loadMoreObserver) {
        loadMoreObserver = new IntersectionObserver(entries => {
            if (entries.some(entry => entry.isIntersecting) && rendered < results.length) {
                renderNextPage();
            }
        }, { rootMargin: '600px 0px' });
    }
    // observing again re-checks the position (the button can still be on screen after a page)
    loadMoreObserver.unobserve(loadMore);
    loadMoreObserver.observe(loadMore);
}

function updateChips(counts) {
    document.querySelectorAll('#categoryChips .chip').forEach(chip => {
        const active = chip.dataset.category === state.category;
        chip.classList.toggle('is-active', active);
        chip.setAttribute('aria-pressed', String(active));
        chip.querySelector('.chip-count').textContent = (counts[chip.dataset.category] || 0).toLocaleString('en');
    });
}

function categoryName(id) {
    return categories.find(c => c.id === id)?.name || id;
}

function updateSummary(words) {
    const summary = document.getElementById('resultsSummary');
    const count = document.createElement('strong');
    count.textContent = results.length.toLocaleString('en');
    summary.textContent = '';
    summary.append(count, results.length === 1 ? ' project' : ' projects');
    if (words.length) {
        const query = document.createElement('span');
        query.className = 'hl';
        query.textContent = state.query.trim();
        summary.append(' for “', query, '”');
    }
    if (state.category !== 'None') {
        summary.append(` in ${categoryName(state.category)}`);
    }
}

function makeChip(label, onClick) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip';
    chip.textContent = label;
    chip.addEventListener('click', onClick);
    return chip;
}

function updateEmptyState(words, counts) {
    const emptyState = document.getElementById('emptyState');
    emptyState.hidden = results.length > 0;
    if (results.length > 0) return;

    const suggestions = document.getElementById('emptySuggestions');
    suggestions.textContent = '';
    if (state.category !== 'None' && counts.None > 0) {
        suggestions.appendChild(makeChip(`✨ Search in all categories (${counts.None})`, () => setCategory('None')));
    }
    popularKeywords.forEach(keyword => {
        suggestions.appendChild(makeChip(`#${keyword}`, () => {
            state.category = 'None';
            setQuery(keyword);
        }));
    });
    document.getElementById('emptyText').textContent = words.length
        ? 'Try other words, or one of these:'
        : 'Try one of these:';
}

// Keep the search in the address bar: the page can be shared or reloaded
function syncUrl() {
    const params = new URLSearchParams();
    if (state.query.trim()) params.set('q', state.query.trim());
    if (state.category !== 'None') params.set('cat', state.category);
    if (orderBy.value !== 'None') params.set('sort', orderBy.value);
    const query = params.toString();
    history.replaceState(null, '', query ? `?${query}` : window.location.pathname);
}

function createCard(item, index) {
    const template = document.getElementById('card-template');
    const card = template.content.cloneNode(true);
    card.querySelector('.card').style.setProperty('--i', Math.min(index, 12));

    // Determine repository type from the host (a project without repo must not break the whole list)
    const repoUrl = safeUrl(item.repo);
    const repoHost = repoUrl ? new URL(repoUrl).hostname.replace(/^www\./, "") : "";
    const repoType = repoHost === "github.com" ? "github" :
                     repoHost === "gitlab.com" ? "gitlab" : "homepage";

    // Project data comes from crawled third-party repositories: never put it into innerHTML
    const title = String(item.title || 'Untitled');
    const slash = title.lastIndexOf('/');
    card.querySelector('.card-owner').textContent = slash > 0 ? title.slice(0, slash + 1) : '';
    card.querySelector('.card-name').textContent = slash > 0 ? title.slice(slash + 1) : title;
    const titleLink = card.querySelector('.card-title-link');
    if (repoUrl) titleLink.href = repoUrl;

    const description = card.querySelector('.card-description');
    description.textContent = item.description || '';
    description.hidden = !item.description;

    const category = card.querySelector('.card-category');
    category.dataset.category = String(item.category || '').toLowerCase();
    category.querySelector('.card-category-img').src = `imgs/explorer/category/${encodeURIComponent(item.category)}.png`;
    category.querySelector('.card-category-name').textContent = categoryName(item.category);

    card.querySelector('.card-poc').hidden = !item.poc;

    // the first keywords are usually the repository topics
    const tags = card.querySelector('.card-tags');
    const keywords = [...new Set((Array.isArray(item.keywords) ? item.keywords : []).map(k => String(k).toLowerCase()))];
    // some extracted keywords are only punctuation (e.g. "."): not useful as tags
    keywords.filter(k => k.length <= 30 && /[a-z0-9]/.test(k)).slice(0, 3).forEach(keyword => {
        const tag = document.createElement('button');
        tag.type = 'button';
        tag.className = 'tag';
        tag.dataset.tag = keyword;
        tag.title = `Search “${keyword}”`;
        tag.textContent = keyword;
        tags.appendChild(tag);
    });

    if (item.language) {
        setStat(card.querySelector('.language'), "imgs/explorer/code-icon.png", item.language);
    }
    if (item.stars) {
        setStat(card.querySelector('.stars'), "imgs/explorer/star-icon.png",
                compactNumber.format(item.stars), `${item.stars.toLocaleString('en')} stars`);
    }

    const repoLink = card.querySelector('.repo-link');
    if (repoUrl) {
        repoLink.href = repoUrl;
        // there is no "homepage-logo.png": generic repositories use the homepage icon
        repoLink.querySelector('.repo-logo').src = repoType === "homepage"
            ? "imgs/explorer/homepage-icon.png"
            : `imgs/explorer/${repoType}-logo.png`;
    } else {
        repoLink.hidden = true;
    }

    const websiteUrl = safeUrl(item.website);
    if (websiteUrl) {
        const websiteLink = card.querySelector('.website-link');
        websiteLink.href = websiteUrl;
        websiteLink.hidden = false;
    }

    return card;
}

// Grey cards shown while projects.json is downloading
function showSkeletons() {
    const cardGrid = document.getElementById('cardGrid');
    cardGrid.textContent = '';
    for (let i = 0; i < 8; i++) {
        const card = document.createElement('div');
        card.className = 'card skeleton';
        card.setAttribute('aria-hidden', 'true');
        ['short', 'title', '', '', 'footer'].forEach(type => {
            const line = document.createElement('div');
            line.className = `skeleton-line ${type}`.trim();
            card.appendChild(line);
        });
        cardGrid.appendChild(card);
    }
}

async function loadTemplate() {
    const response = await fetch('card.html');
    const templateHTML = await response.text();
    document.body.insertAdjacentHTML('beforeend', templateHTML);
}

function setQuery(query) {
    searchInput.value = query;
    state.query = query;
    updateClearButton();
    runSearch();
    window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
}

function setCategory(category) {
    state.category = category;
    runSearch();
}

function updateClearButton() {
    document.getElementById('clearSearch').hidden = !searchInput.value;
}

function initEvents() {
    const form = document.getElementById('searchForm');
    let debounce = null;

    // results while typing
    searchInput.addEventListener('input', () => {
        updateClearButton();
        clearTimeout(debounce);
        debounce = setTimeout(() => {
            state.query = searchInput.value;
            runSearch();
        }, 200);
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        clearTimeout(debounce);
        state.query = searchInput.value;
        runSearch();
        // close the keyboard on phones
        if (window.matchMedia('(pointer: coarse)').matches) searchInput.blur();
    });

    document.getElementById('clearSearch').addEventListener('click', () => {
        setQuery('');
        searchInput.focus();
    });

    document.getElementById('categoryChips').addEventListener('click', (event) => {
        const chip = event.target.closest('.chip');
        if (chip) setCategory(chip.dataset.category);
    });

    orderBy.addEventListener('change', runSearch);

    // tags and categories on the cards start a new search
    document.getElementById('cardGrid').addEventListener('click', (event) => {
        // a tag is a new search, in all the categories
        const tag = event.target.closest('.tag');
        if (tag) {
            state.category = 'None';
            setQuery(tag.dataset.tag);
            return;
        }
        const category = event.target.closest('.card-category');
        if (category) {
            setCategory(category.dataset.category);
            window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
        }
    });

    document.querySelector('#loadMore button').addEventListener('click', renderNextPage);
    document.getElementById('btnGridView').addEventListener('click', setGridView);
    document.getElementById('btnListView').addEventListener('click', setListView);
}

/* Initialize functions */
window.onload = async () => {
    showSkeletons();
    initEvents();
    try {
        await Promise.all([loadTemplate(), loadFilterCategories(), loadOrderByConfig(), loadProjects()]);
    } catch (error) {
        console.error('Error loading projects:', error);
        document.getElementById('resultsSummary').textContent = 'Cannot load the projects, please reload the page.';
        document.getElementById('cardGrid').textContent = '';
        return;
    }

    const urlParams = new URL(document.URL).searchParams;
    // only known values from the address bar
    const category = urlParams.get("cat");
    if (category && categories.some(c => c.id === category)) {
        state.category = category;
    }
    const sort = urlParams.get("sort");
    if (sort && orderByOptions.some(option => option.id === sort)) {
        orderBy.value = sort;
    }
    state.query = (urlParams.get("q") || "").slice(0, 100);
    searchInput.value = state.query;
    updateClearButton();
    runSearch();
};


// Funzioni per cambiare vista

function setView(mode) {
    const grid = document.getElementById('cardGrid');
    grid.classList.toggle('list-mode', mode === 'list');
    // Aggiorna stato pulsanti
    document.getElementById('btnGridView').setAttribute('aria-pressed', String(mode !== 'list'));
    document.getElementById('btnListView').setAttribute('aria-pressed', String(mode === 'list'));
    // Salva preferenza utente
    savePreference('viewMode', mode);
}

function setGridView() {
    setView('grid');
}

function setListView() {
    setView('list');
}

// Carica la preferenza all'avvio della pagina
document.addEventListener('DOMContentLoaded', () => {
    setView(readPreference('viewMode') === 'list' ? 'list' : 'grid');
});
