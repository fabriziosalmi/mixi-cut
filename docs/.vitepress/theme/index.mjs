import DefaultTheme from 'vitepress/theme'
import './custom.css'

/**
 * Split the text content of an element into per-character <span class="char">
 * wrappers with staggered animation-delay. CSS does the actual animation.
 * Idempotent via data-split flag.
 */
function splitChars(el, { charDelay = 25, startDelay = 0 } = {}) {
  if (!el || el.dataset.split) return
  const text = el.textContent
  if (!text) return
  el.dataset.split = '1'
  // preserve any trailing nodes? for the hero it's plain text.
  el.textContent = ''
  const frag = document.createDocumentFragment()
  let charIdx = 0
  for (const ch of text) {
    const span = document.createElement('span')
    span.className = 'char'
    // Non-breaking space so wrapping stays natural but space is still animated
    span.textContent = ch === ' ' ? '\u00A0' : ch
    span.style.animationDelay = `${startDelay + charIdx * charDelay}ms`
    // Each word break lets the line reflow; wrap-safe inline-block
    frag.appendChild(span)
    charIdx++
  }
  el.appendChild(frag)
}

function applyHeroCrumble() {
  // VitePress renders hero name/text/tagline with these class names.
  const name = document.querySelector('.VPHero .name .clip')
    || document.querySelector('.VPHero .name')
  const text = document.querySelector('.VPHero .text')
  const tagline = document.querySelector('.VPHero .tagline')

  // Title: snappy, 40ms/char
  splitChars(name,    { charDelay: 40, startDelay: 0 })
  // Main line: starts after title, a hair faster
  splitChars(text,    { charDelay: 15, startDelay: 220 })
  // Tagline: starts last, even faster since it is longer
  splitChars(tagline, { charDelay: 8,  startDelay: 450 })
}

export default {
  extends: DefaultTheme,
  enhanceApp({ router }) {
    if (typeof window === 'undefined') return
    const run = () => {
      // Run after VitePress/Vue paints the hero
      requestAnimationFrame(() => requestAnimationFrame(applyHeroCrumble))
    }
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      run()
    } else {
      window.addEventListener('DOMContentLoaded', run, { once: true })
    }
    // Re-apply when navigating back to the home page via SPA routing
    if (router && typeof router.onAfterRouteChanged !== 'undefined') {
      const prev = router.onAfterRouteChanged
      router.onAfterRouteChanged = (to) => {
        if (typeof prev === 'function') prev(to)
        run()
      }
    }
  }
}
