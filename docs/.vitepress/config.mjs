import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'MIXI-CUT',
  description: 'Open-source DVS timecode protocol for vinyl lathe cutting',
  base: '/mixi-cut/',
  head: [
    ['link', { rel: 'preconnect', href: 'https://fonts.googleapis.com' }],
    ['link', { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' }],
    ['link', { href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap', rel: 'stylesheet' }],
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
