"use strict";

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } }

function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); return Constructor; }

/**
 * EzCo User Manual - Main JavaScript
 * Handles navigation, theme switching, and interactive features
 */
var EzCoManual =
/*#__PURE__*/
function () {
  function EzCoManual() {
    _classCallCheck(this, EzCoManual);

    this.sections = [];
    this.currentSection = null;
    this.theme = localStorage.getItem('ezco-manual-theme') || 'light';
    this.init();
  }

  _createClass(EzCoManual, [{
    key: "init",
    value: function init() {
      var _this = this;

      this.setupTheme();
      this.setupNavigation();
      this.setupScrollSpy();
      this.setupResponsiveMenu();
      this.setupKeyboardNavigation();
      this.setupPrintButton();
      this.setupTooltips();
      this.collectSections(); // Initialize after DOM is ready

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
          _this.updateActiveSection();
        });
      } else {
        this.updateActiveSection();
      }
    }
    /**
     * Theme Management
     */

  }, {
    key: "setupTheme",
    value: function setupTheme() {
      var _this2 = this;

      // Apply saved theme
      document.documentElement.setAttribute('data-theme', this.theme); // Create theme toggle button

      var themeToggle = document.createElement('button');
      themeToggle.className = 'theme-toggle';
      themeToggle.innerHTML = this.theme === 'dark' ? '☀️' : '🌙';
      themeToggle.setAttribute('aria-label', 'Toggle theme');
      themeToggle.setAttribute('data-tooltip', this.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
      themeToggle.addEventListener('click', function () {
        _this2.toggleTheme();
      });
      document.body.appendChild(themeToggle); // Auto-detect system theme preference

      if (window.matchMedia) {
        var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', function (e) {
          if (!localStorage.getItem('ezco-manual-theme')) {
            _this2.setTheme(e.matches ? 'dark' : 'light');
          }
        });
      }
    }
  }, {
    key: "toggleTheme",
    value: function toggleTheme() {
      var newTheme = this.theme === 'light' ? 'dark' : 'light';
      this.setTheme(newTheme);
    }
  }, {
    key: "setTheme",
    value: function setTheme(theme) {
      this.theme = theme;
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('ezco-manual-theme', theme); // Update toggle button

      var themeToggle = document.querySelector('.theme-toggle');

      if (themeToggle) {
        themeToggle.innerHTML = theme === 'dark' ? '☀️' : '🌙';
        themeToggle.setAttribute('data-tooltip', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
      }
    }
    /**
     * Navigation Management
     */

  }, {
    key: "setupNavigation",
    value: function setupNavigation() {
      var _this3 = this;

      // Smooth scrolling for anchor links (same page only)
      document.addEventListener('click', function (e) {
        var link = e.target.closest('a[href^="#"]');

        if (link) {
          var href = link.getAttribute('href'); // Only handle pure hash links (same page navigation)

          if (href.startsWith('#') && !href.includes('.html')) {
            e.preventDefault();
            var target = document.querySelector(href);

            if (target) {
              _this3.scrollToElement(target);
            }
          }
        }
      }); // Handle section navigation for toc-links

      var tocLinks = document.querySelectorAll('.toc-link');
      tocLinks.forEach(function (link) {
        var href = link.getAttribute('href'); // Only handle same-page hash links

        if (href.startsWith('#') && !href.includes('.html')) {
          link.addEventListener('click', function (e) {
            e.preventDefault();
            var targetId = href.substring(1);
            var target = document.getElementById(targetId);

            if (target) {
              _this3.scrollToElement(target);

              _this3.setActiveSection(targetId);
            }
          });
        } // External page links (like files/advanced-features.html#archives) will work normally

      });
    }
  }, {
    key: "scrollToElement",
    value: function scrollToElement(element) {
      var headerHeight = document.querySelector('.header').offsetHeight;
      var elementPosition = element.offsetTop - headerHeight - 20;
      window.scrollTo({
        top: elementPosition,
        behavior: 'smooth'
      });
    }
    /**
     * Scroll Spy for Active Section Highlighting
     */

  }, {
    key: "setupScrollSpy",
    value: function setupScrollSpy() {
      var _this4 = this;

      var sections = document.querySelectorAll('.section[id]');
      var options = {
        rootMargin: '-80px 0px -40% 0px',
        threshold: 0.1
      };
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            _this4.setActiveSection(entry.target.id);
          }
        });
      }, options);
      sections.forEach(function (section) {
        observer.observe(section);
      }); // Fallback for browsers without IntersectionObserver

      if (!window.IntersectionObserver) {
        window.addEventListener('scroll', this.debounce(function () {
          _this4.updateActiveSection();
        }, 100));
      }
    }
  }, {
    key: "setActiveSection",
    value: function setActiveSection(sectionId) {
      // Remove active class from all links
      document.querySelectorAll('.toc-link').forEach(function (link) {
        link.classList.remove('active');
      }); // Add active class to current section link

      var activeLink = document.querySelector("a[href=\"#".concat(sectionId, "\"]"));

      if (activeLink) {
        activeLink.classList.add('active');
      }

      this.currentSection = sectionId; // Update URL without scrolling

      if (history.replaceState) {
        history.replaceState(null, null, "#".concat(sectionId));
      }
    }
  }, {
    key: "updateActiveSection",
    value: function updateActiveSection() {
      var sections = document.querySelectorAll('.section[id]');
      var scrollPos = window.scrollY + 100;

      for (var i = sections.length - 1; i >= 0; i--) {
        var section = sections[i];

        if (section.offsetTop <= scrollPos) {
          this.setActiveSection(section.id);
          break;
        }
      }
    }
    /**
     * Responsive Menu
     */

  }, {
    key: "setupResponsiveMenu",
    value: function setupResponsiveMenu() {
      var sidebar = document.querySelector('.sidebar');
      var content = document.querySelector('.content'); // Create mobile menu toggle

      var menuToggle = document.createElement('button');
      menuToggle.className = 'mobile-menu-toggle';
      menuToggle.innerHTML = '☰';
      menuToggle.setAttribute('aria-label', 'Toggle menu');
      menuToggle.style.display = 'none'; // Add toggle to header

      var headerContent = document.querySelector('.header-content');

      if (headerContent) {
        headerContent.insertBefore(menuToggle, headerContent.firstChild);
      } // Toggle menu on mobile


      menuToggle.addEventListener('click', function () {
        sidebar.classList.toggle('sidebar-open');
        menuToggle.classList.toggle('active');
      }); // Close menu when clicking outside on mobile

      document.addEventListener('click', function (e) {
        if (window.innerWidth <= 768 && !sidebar.contains(e.target) && !menuToggle.contains(e.target)) {
          sidebar.classList.remove('sidebar-open');
          menuToggle.classList.remove('active');
        }
      }); // Handle window resize

      window.addEventListener('resize', function () {
        if (window.innerWidth > 768) {
          sidebar.classList.remove('sidebar-open');
          menuToggle.classList.remove('active');
          menuToggle.style.display = 'none';
        } else {
          menuToggle.style.display = 'block';
        }
      }); // Initialize mobile state

      if (window.innerWidth <= 768) {
        menuToggle.style.display = 'block';
      }
    }
    /**
     * Keyboard Navigation
     */

  }, {
    key: "setupKeyboardNavigation",
    value: function setupKeyboardNavigation() {
      var _this5 = this;

      document.addEventListener('keydown', function (e) {
        // ESC key closes mobile menu
        if (e.key === 'Escape') {
          var sidebar = document.querySelector('.sidebar');
          var menuToggle = document.querySelector('.mobile-menu-toggle');
          sidebar.classList.remove('sidebar-open');
          if (menuToggle) menuToggle.classList.remove('active');
        } // Arrow keys for section navigation


        if (e.ctrlKey || e.metaKey) {
          switch (e.key) {
            case 'ArrowUp':
              e.preventDefault();

              _this5.navigateToPreviousSection();

              break;

            case 'ArrowDown':
              e.preventDefault();

              _this5.navigateToNextSection();

              break;

            case 'Home':
              e.preventDefault();

              _this5.navigateToFirstSection();

              break;

            case 'End':
              e.preventDefault();

              _this5.navigateToLastSection();

              break;
          }
        } // Theme toggle with T key


        if (e.key === 't' && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();

          _this5.toggleTheme();
        }
      });
    }
    /**
     * Section Navigation Methods
     */

  }, {
    key: "collectSections",
    value: function collectSections() {
      this.sections = Array.from(document.querySelectorAll('.section[id]')).map(function (section) {
        return section.id;
      });
    }
  }, {
    key: "navigateToPreviousSection",
    value: function navigateToPreviousSection() {
      var currentIndex = this.sections.indexOf(this.currentSection);

      if (currentIndex > 0) {
        var previousSection = this.sections[currentIndex - 1];
        var element = document.getElementById(previousSection);

        if (element) {
          this.scrollToElement(element);
        }
      }
    }
  }, {
    key: "navigateToNextSection",
    value: function navigateToNextSection() {
      var currentIndex = this.sections.indexOf(this.currentSection);

      if (currentIndex < this.sections.length - 1) {
        var nextSection = this.sections[currentIndex + 1];
        var element = document.getElementById(nextSection);

        if (element) {
          this.scrollToElement(element);
        }
      }
    }
  }, {
    key: "navigateToFirstSection",
    value: function navigateToFirstSection() {
      if (this.sections.length > 0) {
        var element = document.getElementById(this.sections[0]);

        if (element) {
          this.scrollToElement(element);
        }
      }
    }
  }, {
    key: "navigateToLastSection",
    value: function navigateToLastSection() {
      if (this.sections.length > 0) {
        var element = document.getElementById(this.sections[this.sections.length - 1]);

        if (element) {
          this.scrollToElement(element);
        }
      }
    }
    /**
     * Print Functionality
     */

  }, {
    key: "setupPrintButton",
    value: function setupPrintButton() {
      var printButton = document.createElement('button');
      printButton.className = 'print-button btn btn-secondary';
      printButton.innerHTML = '🖨️ Print';
      printButton.style.cssText = "\n            position: fixed;\n            bottom: 20px;\n            right: 20px;\n            z-index: 999;\n            display: none;\n            box-shadow: var(--shadow-lg);\n            border-radius: 50px;\n            padding: 0.75rem 1.5rem;\n            font-weight: 500;\n            transition: all 0.3s ease;\n        ";
      printButton.addEventListener('click', function () {
        window.print();
      });
      document.body.appendChild(printButton); // Show print button on larger screens

      var mediaQuery = window.matchMedia('(min-width: 768px)');

      var handleMediaQuery = function handleMediaQuery(e) {
        printButton.style.display = e.matches ? 'block' : 'none';
      };

      mediaQuery.addEventListener('change', handleMediaQuery);
      handleMediaQuery(mediaQuery);
    }
    /**
     * Tooltips
     */

  }, {
    key: "setupTooltips",
    value: function setupTooltips() {
      var _this6 = this;

      // Enhanced tooltip functionality
      document.addEventListener('mouseover', function (e) {
        var element = e.target.closest('[data-tooltip]');

        if (element && !element.querySelector('.tooltip-content')) {
          _this6.showTooltip(element);
        }
      });
      document.addEventListener('mouseout', function (e) {
        var element = e.target.closest('[data-tooltip]');

        if (element) {
          _this6.hideTooltip(element);
        }
      });
    }
  }, {
    key: "showTooltip",
    value: function showTooltip(element) {
      var tooltipText = element.getAttribute('data-tooltip');
      if (!tooltipText) return;
      var tooltip = document.createElement('div');
      tooltip.className = 'tooltip-content';
      tooltip.textContent = tooltipText;
      tooltip.style.cssText = "\n            position: fixed;\n            background: var(--bg-primary);\n            color: var(--text-primary);\n            padding: 0.5rem;\n            border-radius: 4px;\n            font-size: 0.8rem;\n            white-space: nowrap;\n            border: 1px solid var(--border-primary);\n            box-shadow: var(--shadow-md);\n            z-index: 1000;\n            pointer-events: none;\n            opacity: 0;\n            transition: opacity 0.3s ease;\n        ";
      element.appendChild(tooltip); // Position tooltip

      var rect = element.getBoundingClientRect();
      var tooltipRect = tooltip.getBoundingClientRect();
      var top = rect.top - tooltipRect.height - 5;
      var left = rect.left + (rect.width - tooltipRect.width) / 2; // Adjust if tooltip goes off screen

      if (top < 0) {
        top = rect.bottom + 5;
      }

      if (left < 0) {
        left = 5;
      }

      if (left + tooltipRect.width > window.innerWidth) {
        left = window.innerWidth - tooltipRect.width - 5;
      }

      tooltip.style.top = "".concat(top, "px");
      tooltip.style.left = "".concat(left, "px");
      tooltip.style.position = 'fixed'; // Fade in

      setTimeout(function () {
        tooltip.style.opacity = '1';
      }, 10);
    }
  }, {
    key: "hideTooltip",
    value: function hideTooltip(element) {
      var tooltip = element.querySelector('.tooltip-content');

      if (tooltip) {
        tooltip.style.opacity = '0';
        setTimeout(function () {
          if (tooltip.parentNode) {
            tooltip.parentNode.removeChild(tooltip);
          }
        }, 300);
      }
    }
    /**
     * Utility Functions
     */

  }, {
    key: "debounce",
    value: function debounce(func, wait) {
      var timeout;
      return function executedFunction() {
        for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
          args[_key] = arguments[_key];
        }

        var later = function later() {
          clearTimeout(timeout);
          func.apply(void 0, args);
        };

        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    }
  }, {
    key: "throttle",
    value: function throttle(func, limit) {
      var inThrottle;
      return function () {
        var args = arguments;
        var context = this;

        if (!inThrottle) {
          func.apply(context, args);
          inThrottle = true;
          setTimeout(function () {
            return inThrottle = false;
          }, limit);
        }
      };
    }
    /**
     * Page Navigation Functions (for external use)
     */

  }, {
    key: "showSection",
    value: function showSection(sectionId) {
      var element = document.getElementById(sectionId);

      if (element) {
        this.scrollToElement(element);
        this.setActiveSection(sectionId);
      }
    }
  }, {
    key: "goToPage",
    value: function goToPage(page) {
      // Handle pagination logic if needed
      console.log("Navigating to page: ".concat(page));
    }
  }]);

  return EzCoManual;
}(); // CSS for mobile menu toggle (added via JavaScript)


var mobileMenuStyles = "\n.mobile-menu-toggle {\n    display: none;\n    background: none;\n    border: none;\n    color: white;\n    font-size: 1.5rem;\n    cursor: pointer;\n    padding: 0.5rem;\n    border-radius: 4px;\n    transition: background-color 0.3s ease;\n}\n\n.mobile-menu-toggle:hover {\n    background: rgba(255, 255, 255, 0.1);\n}\n\n.mobile-menu-toggle.active {\n    background: rgba(255, 255, 255, 0.2);\n}\n\n@media (max-width: 768px) {\n    .sidebar.sidebar-open {\n        position: fixed;\n        top: 80px;\n        left: 0;\n        width: 100%;\n        height: calc(100vh - 80px);\n        z-index: 999;\n        transform: translateX(0);\n        transition: transform 0.3s ease;\n    }\n    \n    .sidebar:not(.sidebar-open) {\n        transform: translateX(-100%);\n        transition: transform 0.3s ease;\n    }\n}\n\n.print-button {\n    box-shadow: var(--shadow-lg);\n    border-radius: 50px;\n    padding: 0.75rem 1.5rem;\n    font-weight: 500;\n    transition: all 0.3s ease;\n}\n\n.print-button:hover {\n    transform: translateY(-2px);\n    box-shadow: var(--shadow-xl);\n}\n"; // Add mobile menu styles to head

var styleSheet = document.createElement('style');
styleSheet.textContent = mobileMenuStyles;
document.head.appendChild(styleSheet); // Initialize the manual

var ezcoManual = new EzCoManual(); // Make some functions globally available

window.showSection = function (sectionId) {
  return ezcoManual.showSection(sectionId);
};

window.ezcoManual = ezcoManual; // Export for module systems if needed

if (typeof module !== 'undefined' && module.exports) {
  module.exports = EzCoManual;
}