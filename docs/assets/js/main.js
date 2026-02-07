/**
 * ZERG Landing Page — Interactive Features
 * All features wrapped in an IIFE to avoid global scope pollution.
 * Each feature initializer is wrapped in try/catch for graceful degradation.
 */
(function () {
  'use strict';

  var NAV_HEIGHT = 64;

  // -------------------------------------------------------------------------
  // Feature 1: Dark / Light Mode Toggle
  // -------------------------------------------------------------------------
  function initThemeToggle() {
    var toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    var html = document.documentElement;
    var darkIcon = toggle.querySelector('.dark-icon');
    var lightIcon = toggle.querySelector('.light-icon');

    function applyTheme(isDark) {
      if (isDark) {
        html.classList.add('dark');
        if (darkIcon) darkIcon.classList.remove('hidden');
        if (lightIcon) lightIcon.classList.add('hidden');
      } else {
        html.classList.remove('dark');
        if (darkIcon) darkIcon.classList.add('hidden');
        if (lightIcon) lightIcon.classList.remove('hidden');
      }
    }

    // Determine initial theme
    var stored = null;
    try {
      stored = localStorage.getItem('theme');
    } catch (e) {
      // localStorage may be unavailable (private browsing, etc.)
    }

    if (stored === 'light') {
      applyTheme(false);
    } else if (stored === 'dark') {
      applyTheme(true);
    } else {
      // No stored preference — check system preference
      var prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
      applyTheme(!prefersLight);
    }

    toggle.addEventListener('click', function () {
      var isDark = html.classList.toggle('dark');
      applyTheme(isDark);
      try {
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
      } catch (e) {
        // Silently fail if localStorage is unavailable
      }
    });
  }

  // -------------------------------------------------------------------------
  // Feature 2: Mobile Hamburger Menu
  // -------------------------------------------------------------------------
  function initMobileMenu() {
    var btn = document.getElementById('mobile-menu-btn');
    var menu = document.getElementById('mobile-menu');
    if (!btn || !menu) return;

    function closeMenu() {
      menu.classList.add('hidden');
      btn.setAttribute('aria-expanded', 'false');
    }

    function openMenu() {
      menu.classList.remove('hidden');
      btn.setAttribute('aria-expanded', 'true');
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var isOpen = btn.getAttribute('aria-expanded') === 'true';
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    // Close when clicking a nav link inside mobile menu
    var links = menu.querySelectorAll('a');
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener('click', closeMenu);
    }

    // Close when clicking outside
    document.addEventListener('click', function (e) {
      if (!menu.classList.contains('hidden') && !menu.contains(e.target) && !btn.contains(e.target)) {
        closeMenu();
      }
    });
  }

  // -------------------------------------------------------------------------
  // Feature 3: Copy-to-Clipboard
  // -------------------------------------------------------------------------
  function initCopyButtons() {
    var buttons = document.querySelectorAll('.copy-btn');
    if (!buttons.length) return;

    function fallbackCopy(text) {
      var textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand('copy');
      } catch (e) {
        // Copy failed silently
      }
      document.body.removeChild(textarea);
    }

    function handleCopy(btn) {
      // Get text from data-copy attribute
      var text = btn.getAttribute('data-copy');
      if (!text) {
        // Fallback: try to find associated code element
        var codeBlock = btn.parentElement;
        var codeEl = codeBlock ? codeBlock.querySelector('code') : null;
        if (codeEl) {
          text = codeEl.textContent;
        }
      }
      if (!text) return;

      // Attempt clipboard API first, fallback to textarea
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        navigator.clipboard.writeText(text).catch(function () {
          fallbackCopy(text);
        });
      } else {
        fallbackCopy(text);
      }

      // Visual feedback
      var labelSpan = btn.querySelector('span');
      var originalText = labelSpan ? labelSpan.textContent : '';
      btn.classList.add('copied');
      if (labelSpan) {
        labelSpan.textContent = 'Copied!';
      }

      setTimeout(function () {
        btn.classList.remove('copied');
        if (labelSpan) {
          labelSpan.textContent = originalText;
        }
      }, 2000);
    }

    for (var i = 0; i < buttons.length; i++) {
      (function (btn) {
        btn.addEventListener('click', function () {
          handleCopy(btn);
        });
      })(buttons[i]);
    }
  }

  // -------------------------------------------------------------------------
  // Feature 4: FAQ Accordion Enhancement (smooth height animation)
  // -------------------------------------------------------------------------
  function initFaqAccordion() {
    var faqSection = document.getElementById('faq');
    if (!faqSection) return;

    var detailsElements = faqSection.querySelectorAll('details');
    if (!detailsElements.length) return;

    for (var i = 0; i < detailsElements.length; i++) {
      (function (details) {
        var summary = details.querySelector('summary');
        var answer = details.querySelector('.faq-answer');
        if (!summary || !answer) return;

        // Track animation state
        var isAnimating = false;

        summary.addEventListener('click', function (e) {
          e.preventDefault();

          if (isAnimating) return;
          isAnimating = true;

          if (details.open) {
            // Closing: animate height to 0, then remove open
            var startHeight = answer.scrollHeight;
            answer.style.overflow = 'hidden';
            answer.style.height = startHeight + 'px';

            // Force reflow
            answer.offsetHeight; // eslint-disable-line no-unused-expressions

            answer.style.transition = 'height 0.3s ease';
            answer.style.height = '0px';

            var onClose = function () {
              answer.removeEventListener('transitionend', onClose);
              details.removeAttribute('open');
              answer.style.height = '';
              answer.style.overflow = '';
              answer.style.transition = '';
              isAnimating = false;
            };
            answer.addEventListener('transitionend', onClose);
          } else {
            // Opening: set open, animate from 0 to scrollHeight
            details.setAttribute('open', '');
            var targetHeight = answer.scrollHeight;
            answer.style.overflow = 'hidden';
            answer.style.height = '0px';

            // Force reflow
            answer.offsetHeight; // eslint-disable-line no-unused-expressions

            answer.style.transition = 'height 0.3s ease';
            answer.style.height = targetHeight + 'px';

            var onOpen = function () {
              answer.removeEventListener('transitionend', onOpen);
              answer.style.height = '';
              answer.style.overflow = '';
              answer.style.transition = '';
              isAnimating = false;
            };
            answer.addEventListener('transitionend', onOpen);
          }
        });
      })(detailsElements[i]);
    }
  }

  // -------------------------------------------------------------------------
  // Feature 5: Scroll Animations (IntersectionObserver on .fade-in)
  // -------------------------------------------------------------------------
  function initScrollAnimations() {
    var elements = document.querySelectorAll('.fade-in');
    if (!elements.length) return;

    if (!('IntersectionObserver' in window)) {
      // Fallback: make everything visible immediately
      for (var i = 0; i < elements.length; i++) {
        elements[i].classList.add('visible');
      }
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        for (var j = 0; j < entries.length; j++) {
          if (entries[j].isIntersecting) {
            entries[j].target.classList.add('visible');
            observer.unobserve(entries[j].target);
          }
        }
      },
      { threshold: 0.1 }
    );

    for (var k = 0; k < elements.length; k++) {
      observer.observe(elements[k]);
    }
  }

  // -------------------------------------------------------------------------
  // Feature 6: Stat Counter Animation
  // -------------------------------------------------------------------------
  function initStatCounters() {
    var statsSection = document.getElementById('stats');
    if (!statsSection) return;

    var counters = statsSection.querySelectorAll('[data-target]');
    if (!counters.length) return;

    var hasAnimated = false;

    function animateCounter(el) {
      var target = parseInt(el.getAttribute('data-target'), 10);
      if (isNaN(target)) return;

      // Detect suffix by checking for a child span (e.g. the "%" span)
      var suffixSpan = el.querySelector('span');
      var suffix = '';
      if (suffixSpan) {
        suffix = suffixSpan.textContent;
      }

      var duration = 2000; // ms
      var startTime = null;

      function step(timestamp) {
        if (!startTime) startTime = timestamp;
        var progress = Math.min((timestamp - startTime) / duration, 1);

        // Ease-out quadratic
        var easedProgress = 1 - (1 - progress) * (1 - progress);
        var current = Math.floor(easedProgress * target);

        if (suffix) {
          el.textContent = current;
          // Re-create the suffix span
          var newSpan = document.createElement('span');
          newSpan.className = suffixSpan ? suffixSpan.className : '';
          newSpan.textContent = suffix;
          el.appendChild(newSpan);
        } else {
          el.textContent = String(current);
        }

        if (progress < 1) {
          requestAnimationFrame(step);
        }
      }

      requestAnimationFrame(step);
    }

    if (!('IntersectionObserver' in window)) {
      // Fallback: animate immediately
      for (var i = 0; i < counters.length; i++) {
        animateCounter(counters[i]);
      }
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        for (var j = 0; j < entries.length; j++) {
          if (entries[j].isIntersecting && !hasAnimated) {
            hasAnimated = true;
            for (var k = 0; k < counters.length; k++) {
              animateCounter(counters[k]);
            }
            observer.disconnect();
          }
        }
      },
      { threshold: 0.3 }
    );

    observer.observe(statsSection);
  }

  // -------------------------------------------------------------------------
  // Feature 7: Smooth Scroll
  // -------------------------------------------------------------------------
  function initSmoothScroll() {
    document.addEventListener('click', function (e) {
      // Walk up to find the closest anchor with href starting with #
      var anchor = e.target.closest('a[href^="#"]');
      if (!anchor) return;

      var href = anchor.getAttribute('href');
      if (!href || href === '#') return;

      var targetEl = document.querySelector(href);
      if (!targetEl) return;

      e.preventDefault();

      var top = targetEl.getBoundingClientRect().top + window.pageYOffset - NAV_HEIGHT;
      window.scrollTo({ top: top, behavior: 'smooth' });
    });
  }

  // -------------------------------------------------------------------------
  // Feature 8: Active Nav Highlighting
  // -------------------------------------------------------------------------
  function initActiveNav() {
    var sections = document.querySelectorAll('section[id]');
    if (!sections.length) return;

    // Collect all nav links (desktop + mobile)
    var navContainer = document.querySelector('[role="navigation"][aria-label="Main navigation"]');
    var mobileNav = document.getElementById('mobile-menu');
    var navLinks = [];

    if (navContainer) {
      var desktopLinks = navContainer.querySelectorAll('a[href^="#"]');
      for (var i = 0; i < desktopLinks.length; i++) {
        navLinks.push(desktopLinks[i]);
      }
    }
    if (mobileNav) {
      var mobileLinks = mobileNav.querySelectorAll('a[href^="#"]');
      for (var j = 0; j < mobileLinks.length; j++) {
        navLinks.push(mobileLinks[j]);
      }
    }

    if (!navLinks.length) return;

    var activeClass = 'nav-active';

    // Inject a minimal style for the active indicator
    var style = document.createElement('style');
    style.textContent = '.nav-active { color: var(--accent-purple) !important; opacity: 1 !important; }';
    document.head.appendChild(style);

    function clearActive() {
      for (var k = 0; k < navLinks.length; k++) {
        navLinks[k].classList.remove(activeClass);
      }
    }

    function setActive(sectionId) {
      clearActive();
      for (var k = 0; k < navLinks.length; k++) {
        if (navLinks[k].getAttribute('href') === '#' + sectionId) {
          navLinks[k].classList.add(activeClass);
        }
      }
    }

    if (!('IntersectionObserver' in window)) return;

    var observer = new IntersectionObserver(
      function (entries) {
        for (var m = 0; m < entries.length; m++) {
          if (entries[m].isIntersecting) {
            setActive(entries[m].target.id);
          }
        }
      },
      {
        rootMargin: '-' + NAV_HEIGHT + 'px 0px -50% 0px',
        threshold: 0
      }
    );

    for (var n = 0; n < sections.length; n++) {
      observer.observe(sections[n]);
    }
  }

  // -------------------------------------------------------------------------
  // Initialize all features on DOM ready
  // -------------------------------------------------------------------------
  function init() {
    var features = [
      { name: 'themeToggle', fn: initThemeToggle },
      { name: 'mobileMenu', fn: initMobileMenu },
      { name: 'copyButtons', fn: initCopyButtons },
      { name: 'faqAccordion', fn: initFaqAccordion },
      { name: 'scrollAnimations', fn: initScrollAnimations },
      { name: 'statCounters', fn: initStatCounters },
      { name: 'smoothScroll', fn: initSmoothScroll },
      { name: 'activeNav', fn: initActiveNav }
    ];

    for (var i = 0; i < features.length; i++) {
      try {
        features[i].fn();
      } catch (e) {
        // Graceful degradation: log but don't break other features
        if (typeof console !== 'undefined' && console.error) {
          console.error('ZERG: Failed to init ' + features[i].name, e);
        }
      }
    }
  }

  // Run init when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
