import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'MIXI-CUT',
  description: 'Open-source DVS timecode protocol for vinyl lathe cutting',
  base: '/mixi-cut/',
  // The hostname carries the base path on purpose: VitePress joins it with each
  // page's route, so without it every URL in the sitemap would point at a 404.
  sitemap: { hostname: 'https://fabriziosalmi.github.io/mixi-cut/' },
  head: [
    // Self-hosted fonts (docs/public/fonts) — no request to Google.
    ['link', { href: '/mixi-cut/fonts/fonts.css', rel: 'stylesheet' }],
    ['meta', { name: 'theme-color', content: '#0a0a0a' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'MIXI-CUT' }],
    ['meta', { property: 'og:description', content: 'Open-source DVS timecode for vinyl lathe cutting' }],
  ],
  themeConfig: {
    logo: false,
    siteTitle: 'MIXI-CUT',
    nav: [
      { text: 'Guide', link: '/guide/' },
      { text: 'Protocol', link: '/protocol' },
      { text: 'API', link: '/api/' },
      { text: 'Demo', link: '/demo/' },
    ],
    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Introduction', link: '/guide/' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Quick Start', link: '/guide/quickstart' },
          ]
        },
        {
          text: 'Guides',
          items: [
            { text: 'DJ Setup', link: '/guide/dj' },
            { text: 'Cutting Vinyl', link: '/guide/cutting' },
            { text: 'Decoder Implementation', link: '/guide/decoder' },
            { text: 'Hardware Build', link: '/guide/hardware' },
          ]
        },
        {
          text: 'Reference',
          items: [
            { text: 'Comparison', link: '/guide/comparison' },
          ]
        },
      ],
      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Protocol Constants', link: '/api/' },
            { text: 'CLI Commands', link: '/api/cli' },
            { text: 'Frame Format', link: '/api/frame' },
          ]
        },
      ],
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/fabriziosalmi/mixi-cut' }
    ],
    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright 2026 Fabrizio Salmi'
    },
    search: {
      provider: 'local'
    },
  },
})
