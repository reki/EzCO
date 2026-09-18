/**
 * EzCo User Manual - Main JavaScript
 * Handles navigation, theme switching, and interactive features
 */

class EzCoManual {
    constructor() {
        this.sections = [];
        this.currentSection = null;
        this.theme = localStorage.getItem('ezco-manual-theme') || 'light';
        this.init();
    }

    init() {
        this.setupTheme();
        this.setupNavigation();
        this.setupScrollSpy();
        this.setupResponsiveMenu();
        this.setupKeyboardNavigation();
        this.setupPrintButton();
        this.setupTooltips();
        this.collectSections();
        
        // Initialize after DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.updateActiveSection();
            });
        } else {
            this.updateActiveSection();
        }
    }

    /**
     * Theme Management
     */
    setupTheme() {
        // Apply saved theme
        document.documentElement.setAttribute('data-theme', this.theme);
        
        // Create theme toggle button
        const themeToggle = document.createElement('button');
        themeToggle.className = 'theme-toggle';
        themeToggle.innerHTML = this.theme === 'dark' ? '☀️' : '🌙';
        themeToggle.setAttribute('aria-label', 'Toggle theme');
        themeToggle.setAttribute('data-tooltip', this.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
        
        themeToggle.addEventListener('click', () => {
            this.toggleTheme();
        });
        
        document.body.appendChild(themeToggle);
        
        // Auto-detect system theme preference
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', (e) => {
                if (!localStorage.getItem('ezco-manual-theme')) {
                    this.setTheme(e.matches ? 'dark' : 'light');
                }
            });
        }
    }

    toggleTheme() {
        const newTheme = this.theme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }

    setTheme(theme) {
        this.theme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('ezco-manual-theme', theme);
        
        // Update toggle button
        const themeToggle = document.querySelector('.theme-toggle');
        if (themeToggle) {
            themeToggle.innerHTML = theme === 'dark' ? '☀️' : '🌙';
            themeToggle.setAttribute('data-tooltip', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
        }
    }

    /**
     * Navigation Management
     */
    setupNavigation() {
        // Smooth scrolling for anchor links (same page only)
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[href^="#"]');
            if (link) {
                const href = link.getAttribute('href');
                // Only handle pure hash links (same page navigation)
                if (href.startsWith('#') && !href.includes('.html')) {
                    e.preventDefault();
                    const target = document.querySelector(href);
                    if (target) {
                        this.scrollToElement(target);
                    }
                }
            }
        });

        // Handle section navigation for toc-links
        const tocLinks = document.querySelectorAll('.toc-link');
        tocLinks.forEach(link => {
            const href = link.getAttribute('href');
            // Only handle same-page hash links
            if (href.startsWith('#') && !href.includes('.html')) {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const targetId = href.substring(1);
                    const target = document.getElementById(targetId);
                    if (target) {
                        this.scrollToElement(target);
                        this.setActiveSection(targetId);
                    }
                });
            }
            // External page links (like files/advanced-features.html#archives) will work normally
        });
    }

    scrollToElement(element) {
        const headerHeight = document.querySelector('.header').offsetHeight;
        const elementPosition = element.offsetTop - headerHeight - 20;
        
        window.scrollTo({
            top: elementPosition,
            behavior: 'smooth'
        });
    }

    /**
     * Scroll Spy for Active Section Highlighting
     */
    setupScrollSpy() {
        // 目次にある節・小節を、見出しを通過した順に追跡する
        window.addEventListener('scroll', this.debounce(() => {
            this.updateActiveSection();
        }, 100));
    }

    getNavigationTargets() {
        const targets = [];
        const seen = new Set();
        document.querySelectorAll('.toc-link[href^="#"]').forEach(link => {
            const id = link.getAttribute('href').substring(1);
            const target = document.getElementById(id);
            if (target && !seen.has(id)) {
                seen.add(id);
                targets.push(target);
            }
        });
        return targets.sort((left, right) => left.offsetTop - right.offsetTop);
    }

    setActiveSection(sectionId) {
        // Remove active class from all links
        document.querySelectorAll('.toc-link').forEach(link => {
            link.classList.remove('active');
        });

        // Add active class to current section link
        const activeLink = document.querySelector(`a[href="#${sectionId}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }

        this.currentSection = sectionId;
        
        // Update URL without scrolling
        if (history.replaceState) {
            history.replaceState(null, null, `#${sectionId}`);
        }
    }

    updateActiveSection() {
        const sections = this.getNavigationTargets();
        const headerHeight = document.querySelector('.header')?.offsetHeight || 0;
        const scrollPos = window.scrollY + headerHeight + 24;

        for (let i = sections.length - 1; i >= 0; i--) {
            const section = sections[i];
            if (section.offsetTop <= scrollPos) {
                this.setActiveSection(section.id);
                break;
            }
        }
    }

    /**
     * Responsive Menu
     */
    setupResponsiveMenu() {
        const sidebar = document.querySelector('.sidebar');
        const content = document.querySelector('.content');
        
        // Create mobile menu toggle
        const menuToggle = document.createElement('button');
        menuToggle.className = 'mobile-menu-toggle';
        menuToggle.innerHTML = '☰';
        menuToggle.setAttribute('aria-label', 'Toggle menu');
        menuToggle.style.display = 'none';
        
        // Add toggle to header
        const headerContent = document.querySelector('.header-content');
        if (headerContent) {
            headerContent.insertBefore(menuToggle, headerContent.firstChild);
        }

        // Toggle menu on mobile
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('sidebar-open');
            menuToggle.classList.toggle('active');
        });

        // Close menu when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 && 
                !sidebar.contains(e.target) && 
                !menuToggle.contains(e.target)) {
                sidebar.classList.remove('sidebar-open');
                menuToggle.classList.remove('active');
            }
        });

        // Handle window resize
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                sidebar.classList.remove('sidebar-open');
                menuToggle.classList.remove('active');
                menuToggle.style.display = 'none';
            } else {
                menuToggle.style.display = 'block';
            }
        });

        // Initialize mobile state
        if (window.innerWidth <= 768) {
            menuToggle.style.display = 'block';
        }
    }

    /**
     * Keyboard Navigation
     */
    setupKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // ESC key closes mobile menu
            if (e.key === 'Escape') {
                const sidebar = document.querySelector('.sidebar');
                const menuToggle = document.querySelector('.mobile-menu-toggle');
                sidebar.classList.remove('sidebar-open');
                if (menuToggle) menuToggle.classList.remove('active');
            }

            // Arrow keys for section navigation
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'ArrowUp':
                        e.preventDefault();
                        this.navigateToPreviousSection();
                        break;
                    case 'ArrowDown':
                        e.preventDefault();
                        this.navigateToNextSection();
                        break;
                    case 'Home':
                        e.preventDefault();
                        this.navigateToFirstSection();
                        break;
                    case 'End':
                        e.preventDefault();
                        this.navigateToLastSection();
                        break;
                }
            }

            // Theme toggle with T key
            if (e.key === 't' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.toggleTheme();
            }
        });
    }

    /**
     * Section Navigation Methods
     */
    collectSections() {
        this.sections = Array.from(document.querySelectorAll('.section[id]')).map(section => section.id);
    }

    navigateToPreviousSection() {
        const currentIndex = this.sections.indexOf(this.currentSection);
        if (currentIndex > 0) {
            const previousSection = this.sections[currentIndex - 1];
            const element = document.getElementById(previousSection);
            if (element) {
                this.scrollToElement(element);
            }
        }
    }

    navigateToNextSection() {
        const currentIndex = this.sections.indexOf(this.currentSection);
        if (currentIndex < this.sections.length - 1) {
            const nextSection = this.sections[currentIndex + 1];
            const element = document.getElementById(nextSection);
            if (element) {
                this.scrollToElement(element);
            }
        }
    }

    navigateToFirstSection() {
        if (this.sections.length > 0) {
            const element = document.getElementById(this.sections[0]);
            if (element) {
                this.scrollToElement(element);
            }
        }
    }

    navigateToLastSection() {
        if (this.sections.length > 0) {
            const element = document.getElementById(this.sections[this.sections.length - 1]);
            if (element) {
                this.scrollToElement(element);
            }
        }
    }

    /**
     * Print Functionality
     */
    setupPrintButton() {
        const printButton = document.createElement('button');
        printButton.className = 'print-button btn btn-secondary';
        printButton.innerHTML = '🖨️ Print';
        printButton.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 999;
            display: none;
            box-shadow: var(--shadow-lg);
            border-radius: 50px;
            padding: 0.75rem 1.5rem;
            font-weight: 500;
            transition: all 0.3s ease;
        `;
        
        printButton.addEventListener('click', () => {
            window.print();
        });
        
        document.body.appendChild(printButton);
        
        // Show print button on larger screens
        const mediaQuery = window.matchMedia('(min-width: 768px)');
        const handleMediaQuery = (e) => {
            printButton.style.display = e.matches ? 'block' : 'none';
        };
        
        mediaQuery.addEventListener('change', handleMediaQuery);
        handleMediaQuery(mediaQuery);
    }

    /**
     * Tooltips
     */
    setupTooltips() {
        // Enhanced tooltip functionality
        document.addEventListener('mouseover', (e) => {
            const element = e.target.closest('[data-tooltip]');
            if (element && !element.querySelector('.tooltip-content')) {
                this.showTooltip(element);
            }
        });

        document.addEventListener('mouseout', (e) => {
            const element = e.target.closest('[data-tooltip]');
            if (element) {
                this.hideTooltip(element);
            }
        });
    }

    showTooltip(element) {
        const tooltipText = element.getAttribute('data-tooltip');
        if (!tooltipText) return;

        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip-content';
        tooltip.textContent = tooltipText;
        tooltip.style.cssText = `
            position: fixed;
            background: var(--bg-primary);
            color: var(--text-primary);
            padding: 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            white-space: nowrap;
            border: 1px solid var(--border-primary);
            box-shadow: var(--shadow-md);
            z-index: 1000;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;

        element.appendChild(tooltip);
        
        // Position tooltip
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        
        let top = rect.top - tooltipRect.height - 5;
        let left = rect.left + (rect.width - tooltipRect.width) / 2;
        
        // Adjust if tooltip goes off screen
        if (top < 0) {
            top = rect.bottom + 5;
        }
        if (left < 0) {
            left = 5;
        }
        if (left + tooltipRect.width > window.innerWidth) {
            left = window.innerWidth - tooltipRect.width - 5;
        }
        
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
        tooltip.style.position = 'fixed';
        
        // Fade in
        setTimeout(() => {
            tooltip.style.opacity = '1';
        }, 10);
    }

    hideTooltip(element) {
        const tooltip = element.querySelector('.tooltip-content');
        if (tooltip) {
            tooltip.style.opacity = '0';
            setTimeout(() => {
                if (tooltip.parentNode) {
                    tooltip.parentNode.removeChild(tooltip);
                }
            }, 300);
        }
    }

    /**
     * Utility Functions
     */
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

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * Page Navigation Functions (for external use)
     */
    showSection(sectionId) {
        const element = document.getElementById(sectionId);
        if (element) {
            this.scrollToElement(element);
            this.setActiveSection(sectionId);
        }
    }

    goToPage(page) {
        // Handle pagination logic if needed
        console.log(`Navigating to page: ${page}`);
    }
}

// CSS for mobile menu toggle (added via JavaScript)
const mobileMenuStyles = `
.mobile-menu-toggle {
    display: none;
    background: none;
    border: none;
    color: white;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 4px;
    transition: background-color 0.3s ease;
}

.mobile-menu-toggle:hover {
    background: rgba(255, 255, 255, 0.1);
}

.mobile-menu-toggle.active {
    background: rgba(255, 255, 255, 0.2);
}

@media (max-width: 768px) {
    .sidebar.sidebar-open {
        position: fixed;
        top: 80px;
        left: 0;
        width: 100%;
        height: calc(100vh - 80px);
        z-index: 999;
        transform: translateX(0);
        transition: transform 0.3s ease;
    }
    
    .sidebar:not(.sidebar-open) {
        transform: translateX(-100%);
        transition: transform 0.3s ease;
    }
}

.print-button {
    box-shadow: var(--shadow-lg);
    border-radius: 50px;
    padding: 0.75rem 1.5rem;
    font-weight: 500;
    transition: all 0.3s ease;
}

.print-button:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-xl);
}
`;

// Add mobile menu styles to head
const styleSheet = document.createElement('style');
styleSheet.textContent = mobileMenuStyles;
document.head.appendChild(styleSheet);

// Initialize the manual
const ezcoManual = new EzCoManual();

// Make some functions globally available
window.showSection = (sectionId) => ezcoManual.showSection(sectionId);
window.ezcoManual = ezcoManual;

// Export for module systems if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EzCoManual;
}
 