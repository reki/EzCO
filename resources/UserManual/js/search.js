/**
 * EzCo User Manual - Search Functionality
 * Handles text search, highlighting, and filtering
 */

class ManualSearch {
    constructor() {
        this.searchIndex = [];
        this.currentResults = [];
        this.currentResultIndex = -1;
        this.searchBox = null;
        this.searchBtn = null;
        this.isJapanese = document.documentElement.lang === 'ja';
        this.init();
    }

    init() {
        this.setupSearchElements();
        this.buildSearchIndex();
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
    }

    setupSearchElements() {
        this.searchBox = document.getElementById('searchBox');
        this.searchBtn = document.getElementById('searchBtn');
        
        if (!this.searchBox || !this.searchBtn) {
            console.warn('Search elements not found');
            return;
        }

        this.createSearchResults();
    }

    createSearchResults() {
        const resultsContainer = document.createElement('div');
        resultsContainer.id = 'searchResults';
        resultsContainer.className = 'search-results';
        resultsContainer.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--bg-primary);
            border: 1px solid var(--border-primary);
            border-top: none;
            border-radius: 0 0 6px 6px;
            max-height: 300px;
            overflow-y: auto;
            z-index: 1000;
            display: none;
            box-shadow: var(--shadow-lg);
        `;

        const searchContainer = this.searchBox.parentElement;
        searchContainer.style.position = 'relative';
        searchContainer.appendChild(resultsContainer);
    }

    buildSearchIndex() {
        this.searchIndex = [];
        this.indexSections(document.querySelectorAll('.section, .config-section'));
        this.indexApiMembers();
        this.indexApiFields();
        this.indexActions();
        this.indexCodeExamples();
        console.log(`Search index built with ${this.searchIndex.length} entries`);
    }

    indexSections(sections) {
        sections.forEach(section => {
            const sectionId = section.id;
            const isConfig = section.classList.contains('config-section');
            const heading = isConfig
                ? section.querySelector(':scope > h3')
                : section.querySelector('h2');
            const sectionTitle = heading?.textContent || '';

            if (sectionTitle) {
                this.searchIndex.push({
                    type: 'section',
                    id: sectionId,
                    title: sectionTitle,
                    content: sectionTitle,
                    names: [],
                    element: heading
                });
            }

            const subsections = isConfig
                ? section.querySelectorAll('h4')
                : section.querySelectorAll('h3, h4');
            subsections.forEach(subsection => {
                const subsectionTitle = subsection.textContent;
                const subsectionId = subsection.id || this.generateId(subsectionTitle);

                if (!subsection.id) {
                    subsection.id = subsectionId;
                }

                this.searchIndex.push({
                    type: 'subsection',
                    id: subsectionId,
                    sectionId: sectionId,
                    title: subsectionTitle,
                    content: subsectionTitle,
                    names: [],
                    element: subsection
                });
            });

            const paragraphs = section.querySelectorAll('p, li, td');
            paragraphs.forEach((paragraph, index) => {
                const content = paragraph.textContent.trim();
                if (content.length > 10) {
                    this.searchIndex.push({
                        type: 'content',
                        id: `${sectionId}-content-${index}`,
                        sectionId: sectionId,
                        title: sectionTitle,
                        content: content,
                        names: [],
                        element: paragraph
                    });
                }
            });

            const tables = section.querySelectorAll('table');
            tables.forEach((table, tableIndex) => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row, rowIndex) => {
                    if (row.hasAttribute('data-action-id')) return;
                    const cells = row.querySelectorAll('td, th');
                    const rowContent = Array.from(cells).map(cell => cell.textContent.trim()).join(' ');

                    if (rowContent.length > 5) {
                        this.searchIndex.push({
                            type: 'table',
                            id: `${sectionId}-table-${tableIndex}-row-${rowIndex}`,
                            sectionId: sectionId,
                            title: sectionTitle,
                            content: rowContent,
                            names: [],
                            element: row
                        });
                    }
                });
            });
        });
    }

    indexActions() {
        document.querySelectorAll('[data-action-id]').forEach(row => {
            const actionId = row.dataset.actionId;
            const cells = row.querySelectorAll('td');
            const title = cells[0]?.textContent?.trim() || actionId;
            const content = Array.from(cells).map(cell => cell.textContent.trim()).join(' ');
            const section = row.closest('.section, .config-section');
            this.searchIndex.push({
                type: 'action',
                id: `action-${actionId}`,
                sectionId: section?.id || '',
                title: title,
                content: content,
                names: [actionId],
                element: row
            });
        });
    }

    indexCodeExamples() {
        document.querySelectorAll('.config-example').forEach((example, index) => {
            const content = example.textContent.trim();
            if (!content) return;
            const section = example.closest('.section, .config-section');
            const heading = section?.querySelector('h2, h3');
            this.searchIndex.push({
                type: 'content',
                id: `${section?.id || 'example'}-code-${index}`,
                sectionId: section?.id || '',
                title: heading?.textContent || 'Code',
                content: content,
                names: [],
                element: example
            });
        });
    }

    indexApiMembers() {
        document.querySelectorAll('.api-member').forEach(article => {
            const sigEl = article.querySelector('.api-sig');
            const code = sigEl?.querySelector('code')?.textContent?.trim() || '';
            if (!code) return;

            const names = this.extractApiNames(code);
            const title = names.length ? names.join(' / ') : code;
            const body = article.querySelector('.api-body')?.textContent?.trim() || '';
            const section = article.closest('.section, .config-section');

            this.searchIndex.push({
                type: 'api',
                id: article.id || this.generateId(title),
                sectionId: section?.id || '',
                title: title,
                content: `${code} ${body}`,
                names: names,
                element: sigEl || article
            });
        });
    }

    indexApiFields() {
        document.querySelectorAll('.api-field').forEach((field, index) => {
            const nameEl = field.querySelector('.api-field-name');
            const name = nameEl?.textContent?.trim() || '';
            if (!name) return;

            const desc = field.querySelector('p')?.textContent?.trim() || '';
            const section = field.closest('.section, .config-section');

            this.searchIndex.push({
                type: 'api',
                id: field.id || `${section?.id || 'field'}-${this.generateId(name)}-${index}`,
                sectionId: section?.id || '',
                title: name,
                content: `${name} ${desc}`,
                names: [name],
                element: nameEl
            });
        });
    }

    extractApiNames(sig) {
        const names = [];
        const seen = new Set();
        const re = /\b(?:host\.|root\.)?([A-Za-z_][A-Za-z0-9_]*)\s*\(/g;
        let match;
        while ((match = re.exec(sig)) !== null) {
            const name = match[1];
            const key = name.toLowerCase();
            if (seen.has(key)) continue;
            seen.add(key);
            names.push(name);
        }
        return names;
    }

    generateId(text) {
        return text.toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/\s+/g, '-')
            .substring(0, 50);
    }

    setupEventListeners() {
        if (!this.searchBox || !this.searchBtn) return;

        this.searchBox.addEventListener('input', this.debounce((e) => {
            const query = e.target.value.trim();
            if (query.length >= 2) {
                this.performSearch(query);
            } else {
                this.hideSearchResults();
                this.clearHighlights();
            }
        }, 300));

        this.searchBtn.addEventListener('click', () => {
            const query = this.searchBox.value.trim();
            if (query.length >= 2) {
                this.performSearch(query);
            }
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-container')) {
                this.hideSearchResults();
            }
        });

        this.searchBox.addEventListener('keydown', (e) => {
            const resultsContainer = document.getElementById('searchResults');
            if (!resultsContainer || resultsContainer.style.display === 'none') return;

            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    this.navigateResults(1);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    this.navigateResults(-1);
                    break;
                case 'Enter':
                    e.preventDefault();
                    this.selectCurrentResult();
                    break;
                case 'Escape':
                    e.preventDefault();
                    this.hideSearchResults();
                    this.clearHighlights();
                    break;
            }
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                if (this.searchBox) {
                    this.searchBox.focus();
                    this.searchBox.select();
                }
            }
        });
    }

    performSearch(query) {
        const normalizedQuery = this.normalizeSearchTerm(query);
        const results = this.searchInIndex(normalizedQuery);
        
        this.currentResults = results;
        this.currentResultIndex = -1;
        
        this.displaySearchResults(results, query);
        this.highlightSearchTerms(query);
    }

    normalizeSearchTerm(term) {
        return term.toLowerCase().trim().replace(/\s+/g, ' ');
    }

    searchInIndex(query) {
        const words = query.split(' ').filter(word => word.length > 0);
        const results = [];

        this.searchIndex.forEach(item => {
            const content = item.content.toLowerCase();
            const title = item.title.toLowerCase();
            
            let score = 0;
            let matches = 0;

            const names = (item.names || []).map(name => name.toLowerCase());
            const titleTokens = title.split(/[^a-z0-9_]+/).filter(Boolean);

            words.forEach(word => {
                if (names.includes(word) || titleTokens.includes(word)) {
                    score += 25;
                    matches++;
                } else if (title.includes(word)) {
                    score += 10;
                    matches++;
                } else if (content.includes(word)) {
                    score += 5;
                    matches++;
                } else if (this.fuzzyMatch(content, word) || this.fuzzyMatch(title, word)) {
                    score += 2;
                    matches++;
                }
            });

            if (matches === words.length) {
                results.push({
                    ...item,
                    score: score,
                    matchedWords: words
                });
            }
        });

        return results.sort((a, b) => {
            if (a.score !== b.score) {
                return b.score - a.score;
            }
            
            const typePriority = { api: 5, section: 4, subsection: 3, content: 2, table: 1 };
            return (typePriority[b.type] || 0) - (typePriority[a.type] || 0);
        }).slice(0, 10);
    }

    fuzzyMatch(text, word) {
        if (word.length < 3) return false;
        
        const regex = new RegExp(word.split('').join('.*'), 'i');
        return regex.test(text);
    }

    displaySearchResults(results, query) {
        const resultsContainer = document.getElementById('searchResults');
        if (!resultsContainer) return;

        if (results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="search-no-results">
                    ${this.isJapanese ? '検索結果が見つかりませんでした' : 'No results found'}
                </div>
            `;
            resultsContainer.style.display = 'block';
            return;
        }

        const resultItems = results.map((result, index) => {
            const typeLabel = this.getTypeLabel(result.type);
            const snippet = this.generateSnippet(result.content, query);
            
            return `
                <div class="search-result-item" data-index="${index}">
                    <div class="search-result-type">${typeLabel}</div>
                    <div class="search-result-title">${this.highlightText(result.title, query)}</div>
                    <div class="search-result-snippet">${snippet}</div>
                </div>
            `;
        }).join('');

        resultsContainer.innerHTML = resultItems;
        resultsContainer.style.display = 'block';

        const resultElements = resultsContainer.querySelectorAll('.search-result-item');
        resultElements.forEach((element, index) => {
            element.addEventListener('click', () => {
                this.selectResult(index);
            });

            element.addEventListener('mouseenter', () => {
                this.highlightResult(index);
            });
        });
    }

    getTypeLabel(type) {
        const labels = {
            api: 'API',
            action: this.isJapanese ? 'アクション' : 'Action',
            section: this.isJapanese ? 'セクション' : 'Section',
            subsection: this.isJapanese ? 'サブセクション' : 'Subsection',
            content: this.isJapanese ? 'コンテンツ' : 'Content',
            table: this.isJapanese ? 'テーブル' : 'Table'
        };
        return labels[type] || type;
    }

    generateSnippet(content, query, maxLength = 150) {
        const words = query.toLowerCase().split(' ');
        const lowerContent = content.toLowerCase();
        
        let startIndex = -1;
        for (const word of words) {
            const index = lowerContent.indexOf(word);
            if (index !== -1 && (startIndex === -1 || index < startIndex)) {
                startIndex = index;
            }
        }

        if (startIndex === -1) {
            return content.substring(0, maxLength) + (content.length > maxLength ? '...' : '');
        }

        const snippetStart = Math.max(0, startIndex - 50);
        const snippetEnd = Math.min(content.length, startIndex + maxLength);
        let snippet = content.substring(snippetStart, snippetEnd);

        if (snippetStart > 0) snippet = '...' + snippet;
        if (snippetEnd < content.length) snippet = snippet + '...';

        return this.highlightText(snippet, query);
    }

    highlightText(text, query) {
        const words = query.split(' ').filter(word => word.length > 0);
        let highlightedText = text;

        words.forEach(word => {
            const regex = new RegExp(`(${this.escapeRegex(word)})`, 'gi');
            highlightedText = highlightedText.replace(regex, '<mark>$1</mark>');
        });

        return highlightedText;
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    navigateResults(direction) {
        const results = document.querySelectorAll('.search-result-item');
        if (results.length === 0) return;

        if (this.currentResultIndex >= 0) {
            results[this.currentResultIndex].classList.remove('highlighted');
        }

        this.currentResultIndex += direction;
        if (this.currentResultIndex < 0) {
            this.currentResultIndex = results.length - 1;
        } else if (this.currentResultIndex >= results.length) {
            this.currentResultIndex = 0;
        }

        this.highlightResult(this.currentResultIndex);
        results[this.currentResultIndex].scrollIntoView({ block: 'nearest' });
    }

    highlightResult(index) {
        const results = document.querySelectorAll('.search-result-item');
        if (results.length === 0) return;

        results.forEach(result => result.classList.remove('highlighted'));

        if (index >= 0 && index < results.length) {
            results[index].classList.add('highlighted');
            this.currentResultIndex = index;
        }
    }

    selectCurrentResult() {
        if (this.currentResultIndex >= 0 && this.currentResultIndex < this.currentResults.length) {
            this.selectResult(this.currentResultIndex);
        }
    }

    selectResult(index) {
        if (index < 0 || index >= this.currentResults.length) return;

        const result = this.currentResults[index];
        
        this.navigateToResult(result);
        this.hideSearchResults();
        this.searchBox.blur();
    }

    navigateToResult(result) {
        let targetElement = result.element;

        if (targetElement) {
            if (window.ezcoManual && window.ezcoManual.scrollToElement) {
                window.ezcoManual.scrollToElement(targetElement);
            } else {
                const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
                const elementPosition = targetElement.offsetTop - headerHeight - 20;
                
                window.scrollTo({
                    top: elementPosition,
                    behavior: 'smooth'
                });
            }

            if (result.sectionId && window.ezcoManual && window.ezcoManual.setActiveSection) {
                window.ezcoManual.setActiveSection(result.sectionId);
            }
        }
    }

    highlightSearchTerms(query) {
        this.clearHighlights();

        const words = query.split(' ').filter(word => word.length > 0);
        if (words.length === 0) return;

        const walker = document.createTreeWalker(
            document.querySelector('.content'),
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        const textNodes = [];
        let node;
        while (node = walker.nextNode()) {
            textNodes.push(node);
        }

        textNodes.forEach(textNode => {
            const parent = textNode.parentNode;
            if (parent.tagName === 'MARK' || parent.closest('mark')) return;

            let text = textNode.textContent;
            let hasMatch = false;

            words.forEach(word => {
                const regex = new RegExp(`(${this.escapeRegex(word)})`, 'gi');
                if (regex.test(text)) {
                    text = text.replace(regex, '<mark class="search-highlight">$1</mark>');
                    hasMatch = true;
                }
            });

            if (hasMatch) {
                const wrapper = document.createElement('span');
                wrapper.innerHTML = text;
                parent.replaceChild(wrapper, textNode);
            }
        });
    }

    clearHighlights() {
        const highlights = document.querySelectorAll('.search-highlight');
        highlights.forEach(highlight => {
            const parent = highlight.parentNode;
            parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
            parent.normalize();
        });

        const wrappers = document.querySelectorAll('span:empty');
        wrappers.forEach(wrapper => {
            if (wrapper.parentNode) {
                wrapper.parentNode.removeChild(wrapper);
            }
        });
    }

    hideSearchResults() {
        const resultsContainer = document.getElementById('searchResults');
        if (resultsContainer) {
            resultsContainer.style.display = 'none';
        }
        this.currentResultIndex = -1;
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Search results styling
const searchStyles = `
.search-results {
    font-family: inherit;
}

.search-result-item {
    padding: 0.75rem;
    border-bottom: 1px solid var(--border-primary);
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.search-result-item:hover,
.search-result-item.highlighted {
    background: var(--bg-secondary);
}

.search-result-item:last-child {
    border-bottom: none;
}

.search-result-type {
    font-size: 0.7rem;
    color: var(--primary-500);
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}

.search-result-title {
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.25rem;
    font-size: 0.9rem;
}

.search-result-snippet {
    font-size: 0.8rem;
    color: var(--text-tertiary);
    line-height: 1.4;
}

.search-no-results {
    padding: 1rem;
    text-align: center;
    color: var(--text-tertiary);
    font-style: italic;
}

.search-highlight {
    background: #fff3cd;
    color: #856404;
    padding: 0.1rem 0.2rem;
    border-radius: 2px;
    font-weight: 500;
}

[data-theme="dark"] .search-highlight {
    background: #4a4a0a;
    color: #ffd700;
}

.search-result-item mark {
    background: var(--primary-100);
    color: var(--primary-800);
    padding: 0.1rem 0.2rem;
    border-radius: 2px;
}

[data-theme="dark"] .search-result-item mark {
    background: var(--primary-800);
    color: var(--primary-100);
}
`;

const searchStyleSheet = document.createElement('style');
searchStyleSheet.textContent = searchStyles;
document.head.appendChild(searchStyleSheet);

// Initialize search when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const manualSearch = new ManualSearch();
    window.manualSearch = manualSearch;
});
 