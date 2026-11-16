#!/usr/bin/env python3
"""Builds the static site into dist/.  No dependencies beyond Python 3.

    python3 build.py            build
    python3 build.py --serve    build, then serve dist/ on http://localhost:8000

site.json        every setting and all the sales copy (paths, offers, navigation, redirects)
content/*.html   one file per page: a short header (title, description, section, layout) + HTML body
static/          copied as-is (css, js, fonts, images, PDFs)

Page layouts (the `layout:` line in a content file):
    article   default. Practice tips and simple pages: dark title band, then the body.
    home      the home page, generated from site.json.
    offer     a sales page generated from site.json -> offers.<offer>.
    guide     the free-guide page.
    index     the practice tips index.
"""
import datetime, html, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')
SITE = json.load(open(os.path.join(ROOT, 'site.json'), encoding='utf-8'))
URL = SITE['url'].rstrip('/')
DRAFT = bool(SITE.get('draft'))
YEAR = datetime.date.today().year
ARROW = ' <span class="arrow" aria-hidden="true">→</span>'
THEMES = ('navy', 'violet')
THEME = SITE.get('theme', 'navy') if SITE.get('theme', 'navy') in THEMES else 'navy'

# Artwork is drawn in the navy palette; these swap its colours for the theme's CSS variables.
SVG_VARS = {'#0d1b2a': '--ink', '#14273d': '--ink-2', '#1e3653': '--ink-3', '#ffb703': '--accent', '#1f8a7d': '--art-2',
            '#1f8a7e': '--chip', '#f6f1e7': '--on-ink', '#a9b6c7': '--on-ink-muted'}


def themed(svg):
    def tag(m):
        t, styles = m.group(0), []

        def attr(am):
            if am.group(2).lower() in SVG_VARS:
                styles.append('%s:var(%s)' % (am.group(1), SVG_VARS[am.group(2).lower()]))
                return ''
            return am.group(0)
        t = re.sub(r'\s(fill|stroke)="(#[0-9a-fA-F]{6})"', attr, t)
        if ' font-family="' in t:
            t = re.sub(r'\sfont-family="[^"]*"', '', t)
            styles.append('font-family:var(--font-body)')
        if styles:
            end = '/>' if t.endswith('/>') else '>'
            t = t[:-len(end)] + ' style="%s"' % ';'.join(styles) + end
        return t
    return re.sub(r'<[a-zA-Z][^>]*>', tag, svg)


def e(s):
    return html.escape(s or '', quote=True)


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return f.read()


# ------------------------------------------------------------------ small pieces

def draft(label, note=False):
    """A visible tag for anything still waiting on the site owner. Only shown while draft is true."""
    if not DRAFT:
        return ''
    if note:
        return '<span class="draft-note"><strong>Draft:</strong> %s</span>' % e(label)
    return '<span class="draft-tag">%s</span>' % e(label)


def btn(label, href, cls='', arrow=True):
    rel = ' rel="noopener"' if href.startswith('http') else ''
    return '<a class="btn %s" href="%s"%s>%s%s</a>' % (cls, e(href), rel, e(label), ARROW if arrow else '')


def price(label, value):
    if not value and not DRAFT:
        return ''
    shown = '<span class="path__price-value">%s</span>' % e(value) if value else draft('Price to confirm')
    return '<p class="path__price"><span class="path__price-label">%s</span>%s</p>' % (e(label), shown)


def path_cards(compact=False):
    out = ['<ul class="grid grid--3 path-cards">']
    for p in SITE['paths']['items']:
        out.append(
            '<li><article class="card path%s">'
            '<p class="path__audience">%s</p><h3>%s</h3><p class="path__text">%s</p>%s%s'
            '</article></li>' % (
                ' path--compact' if compact else '', e(p['audience']), e(p['title']),
                e(p['short'] if compact else p['text']),
                price(p['price_label'], p.get('price') or SITE['offers'].get(p['slug'], {}).get('price')),
                btn(p['cta'], p['href'], 'btn--block' if compact else 'btn--block btn--dark')))
    out.append('</ul>')
    return ''.join(out)


def steps(items):
    lis = ''.join('<li class="step"><h3><span class="sr-only">Step %d: </span>%s</h3><p>%s</p></li>'
                  % (i + 1, e(s['title']), e(s['text'])) for i, s in enumerate(items))
    return '<ol class="grid grid--3 steps">%s</ol>' % lis


def form_shell(action, inner, not_connected):
    """A form that still renders when no endpoint is set, but disabled, with a note saying why."""
    attrs = ' action="%s"' % e(action) if action else ''
    note = '' if action else draft(not_connected, note=True)
    return ('<form class="form-shell"%s method="post"><fieldset%s>%s</fieldset>%s</form>'
            % (attrs, '' if action else ' disabled', inner, note))


def signup_form(field_id, button_cls=''):
    action = SITE['forms'].get('newsletter_action')
    if not action and not DRAFT:  # live site, no email provider: hand the guide over directly
        return '<p>%s</p>' % btn('Download the Free Guide (PDF)', SITE['free_guide_pdf'], button_cls, arrow=False)
    inner = ('<div class="form-row"><div class="field"><label for="%s">Email address</label>'
             '<input class="input" id="%s" name="email" type="email" autocomplete="email" placeholder="you@example.com" required></div>'
             '<button class="btn %s" type="submit">%s</button></div>' % (field_id, field_id, button_cls, e(SITE['lead_magnet']['button'])))
    return (form_shell(action, inner, 'Sign-up form not connected to an email provider yet.')
            + '<p class="form-small">No spam. Unsubscribe any time. See the <a href="/privacy-policy.html">privacy policy</a>.</p>')


def contact_form():
    action = SITE['forms'].get('contact_action')
    if not action and not DRAFT:
        return '<p class="notice">The contact form is being moved to the new site and will be back shortly.</p>'
    inner = ('<div class="form-stack">'
             '<div class="field"><label for="c-name">Your name</label><input class="input" id="c-name" name="name" autocomplete="name" required></div>'
             '<div class="field"><label for="c-email">Email address</label><input class="input" id="c-email" type="email" name="email" autocomplete="email" required></div>'
             '<div class="field"><label for="c-msg">Message</label><textarea class="textarea" id="c-msg" name="message" required></textarea></div>'
             '<p class="hp"><label>Leave this empty <input name="website" tabindex="-1" autocomplete="off"></label></p>'
             '<div><button class="btn btn--dark" type="submit">Send Message</button></div></div>')
    return form_shell(action, inner, 'Contact form not connected yet.')


LOGO = ('<a class="logo" href="/" aria-label="Essential Music Practice home">'
        '<svg class="logo__mark" viewBox="0 0 40 40" width="36" height="36" aria-hidden="true">'
        '<rect width="40" height="40" rx="10" fill="#ffb703"/>'
        '<path d="M8 29l8-5 8-5 8-5" fill="none" stroke="#0d1b2a" stroke-width="2.6" stroke-linecap="round"/>'
        '<g fill="#0d1b2a"><circle cx="8" cy="29" r="3.2"/><circle cx="16" cy="24" r="3.2"/><circle cx="24" cy="19" r="3.2"/><circle cx="32" cy="14" r="3.2"/></g>'
        '</svg><span class="logo__text">Essential<b>MusicPractice</b></span></a>')


def header():
    groups = []
    for i, g in enumerate(SITE['nav']):
        items = ''.join('<li><a href="%s"><span class="nav-panel__label">%s</span><span class="nav-panel__note">%s</span></a></li>'
                        % (e(it['href']), e(it['label']), e(it['note'])) for it in g['items'])
        groups.append(
            '<li class="nav-group"><button class="nav-group__btn" type="button" aria-expanded="false" aria-controls="nav-panel-%d">%s'
            '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
            '</button><ul class="nav-panel" id="nav-panel-%d">%s</ul></li>' % (i, e(g['label']), i, items))
    cta = SITE['primary_cta']
    return ('<header class="site-header"><div class="wrap site-header__bar">%s'
            '<button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav">'
            '<span class="menu-toggle__bars" aria-hidden="true"></span><span class="sr-only">Menu</span></button>'
            '<nav id="site-nav" class="site-nav" aria-label="Main"><ul class="site-nav__list">%s</ul>'
            '<a class="btn site-nav__cta" href="%s">%s</a></nav></div></header>'
            % (LOGO, ''.join(groups), e(cta['href']), e(cta['label'])))


def footer():
    cols = ''
    for c in SITE['footer']['columns']:
        links = ''.join('<li><a href="%s"%s>%s</a></li>' % (e(l['href']), ' rel="noopener"' if l['href'].startswith('http') else '', e(l['label']))
                        for l in c['links'])
        cols += '<nav aria-label="%s"><h2 class="site-footer__label">%s</h2><ul>%s</ul></nav>' % (e(c['label']), e(c['label']), links)
    legal = ''.join('<li><a href="%s">%s</a></li>' % (e(l['href']), e(l['label'])) for l in SITE['footer']['legal'])
    return ('<footer class="site-footer"><div class="wrap"><div class="site-footer__top">'
            '<div class="site-footer__brand">%s<p>%s</p></div>%s</div>'
            '<div class="site-footer__base"><p>© 2008–%d %s · %s. All rights reserved.</p>'
            '<ul class="site-footer__legal">%s</ul></div></div></footer>'
            % (LOGO, e(SITE['tagline']), cols, YEAR, e(SITE['name']), e(SITE['author']), legal))


ART = {
    'book': ('<rect x="150" y="52" width="200" height="262" rx="10" fill="#1f8a7d" transform="rotate(5 250 183)"/>'
             '<rect x="140" y="48" width="200" height="262" rx="10" fill="#f6f1e7"/><rect x="140" y="48" width="16" height="262" rx="6" fill="#ffb703"/>'
             '<rect x="176" y="80" width="130" height="14" rx="6" fill="#0d1b2a"/><rect x="176" y="104" width="92" height="14" rx="6" fill="#0d1b2a"/>'
             '<path d="M178 268l22-18 22-18 22-18 22-18 22-18 22-18" fill="none" stroke="#1f8a7d" stroke-width="4" stroke-linecap="round"/>'
             '<g fill="#0d1b2a"><circle cx="178" cy="268" r="7"/><circle cx="200" cy="250" r="7"/><circle cx="222" cy="232" r="7"/><circle cx="244" cy="214" r="7"/><circle cx="266" cy="196" r="7"/><circle cx="288" cy="178" r="7"/></g>'
             '<circle cx="310" cy="160" r="10" fill="#ffb703"/>'),
    'starter': ('<rect x="150" y="70" width="190" height="236" rx="10" fill="#ffb703" transform="rotate(-5 245 188)"/>'
                '<rect x="146" y="62" width="190" height="236" rx="10" fill="#f6f1e7"/>'
                '<rect x="170" y="92" width="110" height="14" rx="6" fill="#0d1b2a"/><rect x="170" y="116" width="70" height="10" rx="5" fill="#1f8a7d"/>'
                '<path d="M176 262h44v-38h44v-38h44" fill="none" stroke="#1f8a7d" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
                '<g fill="#0d1b2a"><circle cx="198" cy="262" r="8"/><circle cx="242" cy="224" r="8"/></g><circle cx="300" cy="186" r="12" fill="#ffb703" stroke="#0d1b2a" stroke-width="3"/>'),
    'course': ('<rect x="80" y="70" width="320" height="200" rx="16" fill="#f6f1e7"/><rect x="80" y="70" width="320" height="34" rx="16" fill="#1f8a7d"/><rect x="80" y="90" width="320" height="14" fill="#1f8a7d"/>'
               '<circle cx="240" cy="186" r="44" fill="#ffb703"/><path d="M226 164v44l38-22z" fill="#0d1b2a"/>'
               '<rect x="110" y="292" width="260" height="10" rx="5" fill="#1e3653"/><rect x="110" y="292" width="112" height="10" rx="5" fill="#ffb703"/>'),
    'guide': ('<rect x="150" y="50" width="200" height="268" rx="12" fill="#1f8a7d" transform="rotate(6 250 184)"/><rect x="140" y="46" width="200" height="268" rx="12" fill="#f6f1e7"/>'
              '<rect x="162" y="76" width="96" height="12" rx="6" fill="#ffb703"/><rect x="162" y="104" width="156" height="16" rx="6" fill="#0d1b2a"/><rect x="162" y="128" width="120" height="16" rx="6" fill="#0d1b2a"/>'
              '<g fill="#c9c1b1"><rect x="162" y="176" width="156" height="8" rx="4"/><rect x="162" y="196" width="140" height="8" rx="4"/><rect x="162" y="216" width="150" height="8" rx="4"/><rect x="162" y="236" width="110" height="8" rx="4"/></g>'
              '<circle cx="300" cy="278" r="18" fill="#ffb703"/>'),
    'library': ('<g><rect x="96" y="84" width="130" height="86" rx="12" fill="#f6f1e7"/><rect x="250" y="84" width="130" height="86" rx="12" fill="#1f8a7d"/>'
                '<rect x="96" y="194" width="130" height="86" rx="12" fill="#ffb703"/><rect x="250" y="194" width="130" height="86" rx="12" fill="#f6f1e7"/></g>'
                '<g fill="#0d1b2a"><rect x="114" y="104" width="70" height="10" rx="5"/><rect x="114" y="212" width="80" height="10" rx="5"/><rect x="268" y="212" width="64" height="10" rx="5"/></g>'
                '<rect x="268" y="104" width="76" height="10" rx="5" fill="#f6f1e7"/>'
                '<g fill="#c9c1b1"><rect x="114" y="126" width="94" height="7" rx="3"/><rect x="114" y="142" width="80" height="7" rx="3"/><rect x="268" y="234" width="94" height="7" rx="3"/><rect x="268" y="250" width="70" height="7" rx="3"/></g>'),
    'teachers': ('<rect x="70" y="80" width="250" height="160" rx="12" fill="#f6f1e7"/>'
                 '<g stroke="#0d1b2a" stroke-width="2"><line x1="96" y1="124" x2="294" y2="124"/><line x1="96" y1="142" x2="294" y2="142"/><line x1="96" y1="160" x2="294" y2="160"/><line x1="96" y1="178" x2="294" y2="178"/><line x1="96" y1="196" x2="294" y2="196"/></g>'
                 '<g fill="#1f8a7d"><circle cx="130" cy="187" r="9"/><circle cx="176" cy="169" r="9"/><circle cx="222" cy="151" r="9"/></g><circle cx="268" cy="133" r="10" fill="#ffb703"/>'
                 '<circle cx="372" cy="170" r="30" fill="#ffb703"/><path d="M318 310c0-48 24-78 54-78s54 30 54 78z" fill="#1f8a7d"/>'
                 '<rect x="70" y="240" width="250" height="10" rx="4" fill="#ffb703"/>'),
    'guideperson': ('<circle cx="240" cy="140" r="56" fill="#f6f1e7"/><path d="M130 320c0-66 49-106 110-106s110 40 110 106z" fill="#1f8a7d"/>'
                    '<path d="M350 96l34-34M372 118h44M328 74V30" stroke="#ffb703" stroke-width="8" stroke-linecap="round"/>'),
}


def art(kind):
    grid = ''.join('<line x1="%d" y1="0" x2="%d" y2="360"/>' % (i * 60, i * 60) for i in range(9))
    grid += ''.join('<line x1="0" y1="%d" x2="480" y2="%d"/>' % (i * 60, i * 60) for i in range(7))
    return ('<svg class="art" viewBox="0 0 480 360" aria-hidden="true" preserveAspectRatio="xMidYMid slice">'
            '<rect width="480" height="360" fill="#14273d"/><g fill="none" stroke="#1e3653" stroke-width="1">%s</g><g>%s</g></svg>'
            % (grid, ART.get(kind, '')))


_art = art
art = lambda kind: themed(_art(kind))


HERO_ART = '''<svg viewBox="0 0 520 460" width="520" height="460">
<rect x="24" y="36" width="472" height="388" rx="22" fill="#14273d" stroke="#1e3653" stroke-width="2"/>
<g stroke="#1e3653" stroke-width="1.5"><line x1="64" y1="176" x2="456" y2="176"/><line x1="64" y1="222" x2="456" y2="222"/><line x1="64" y1="268" x2="456" y2="268"/><line x1="64" y1="314" x2="456" y2="314"/><line x1="64" y1="360" x2="456" y2="360"/></g>
<path class="hero__fill" d="M84 360L144 329 204 298 264 267 324 236 384 205 444 174V360z" fill="#ffb703" opacity="0.1"/>
<path class="hero__line" d="M84 360L144 329 204 298 264 267 324 236 384 205 444 174" fill="none" stroke="#ffb703" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" pathLength="1"/>
<g fill="#f6f1e7"><ellipse cx="84" cy="360" rx="11" ry="8.5"/><ellipse cx="144" cy="329" rx="11" ry="8.5"/><ellipse cx="204" cy="298" rx="11" ry="8.5"/><ellipse cx="264" cy="267" rx="11" ry="8.5"/><ellipse cx="324" cy="236" rx="11" ry="8.5"/><ellipse cx="384" cy="205" rx="11" ry="8.5"/></g>
<circle cx="444" cy="174" r="15" fill="#ffb703"/><circle cx="444" cy="174" r="26" fill="none" stroke="#ffb703" stroke-width="2" opacity="0.45"/>
<g font-family="Roboto Variable, Roboto, sans-serif" font-size="14" font-weight="600" fill="#a9b6c7"><text x="84" y="392" text-anchor="middle">Accuracy</text><text x="264" y="392" text-anchor="middle">Listening</text><text x="430" y="392" text-anchor="middle">Performance</text></g>
<g transform="translate(56 64)"><rect width="190" height="44" rx="22" fill="#1f8a7e"/><path d="M22 22l7 7 13-14" fill="none" stroke="#f6f1e7" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
<text x="56" y="28" font-family="Roboto Variable, Roboto, sans-serif" font-size="16" font-weight="700" fill="#f6f1e7">Seven elements</text></g>
</svg>'''


LOGO = themed(LOGO)
HERO_ART = themed(HERO_ART)

# Optional, draft only ("theme_switcher": true in site.json): flip between themes on any page.
SWITCH = DRAFT and bool(SITE.get('theme_switcher'))
THEME_BOOT = ('<script>(function(){try{var q=new URLSearchParams(location.search).get("theme"),t=q||localStorage.getItem("emp-theme");'
              'if(t==="navy"||t==="violet"){document.documentElement.setAttribute("data-theme",t);if(q)localStorage.setItem("emp-theme",t);}}catch(e){}})();</script>')
THEME_SWITCH = ('<div class="theme-switch" role="group" aria-label="Preview theme"><span>Theme</span>'
                + ''.join('<button type="button" data-set-theme="%s">%s</button>' % (t, t.capitalize()) for t in THEMES) + '</div>')


# ------------------------------------------------------------------ page bodies

def home():
    h, t, p, pl, sh, lm, ts, cl = (SITE[k] for k in ('hero', 'trust', 'paths', 'plan', 'showcase', 'lead_magnet', 'testimonials', 'closing'))
    cta = SITE['primary_cta']
    pad = lambda n: '%02d' % n
    out = []
    # 1 hero: who it is for, the problem, the promise, one clear action
    out.append('<section class="hero section--dark"><div class="wrap hero__grid"><div class="hero__copy">'
               '<p class="eyebrow">%s</p><h1>%s</h1><p class="hero__problem">%s</p><p class="hero__solution">%s</p>'
               '<div class="hero__actions">%s%s</div></div><div class="hero__art" aria-hidden="true">%s</div></div>'
               '<div class="wrap"><div class="trust"><p class="trust__label">%s</p><ul class="trust__list">%s</ul></div></div></section>'
               % (e(h['eyebrow']), e(h['heading']), e(h['problem']), e(h['solution']),
                  btn(cta['label'], cta['href']), btn(h['secondary_cta']['label'], h['secondary_cta']['href'], 'btn--ghost', arrow=False),
                  HERO_ART, e(t['label']), ''.join('<li>%s</li>' % e(i) for i in t['items'])))
    # 2 paths: three ways in, split by who you are
    out.append('<section class="section" id="paths"><div class="wrap"><div class="center section-head"><p class="eyebrow">%s</p><h2>%s</h2></div>%s'
               '<p class="paths__aside">%s <a href="%s">%s</a></p></div></section>'
               % (e(p['eyebrow']), e(p['heading']), path_cards(), e(p['aside']['text']), e(p['aside']['href']), e(p['aside']['label'])))
    # 3 plan: three simple steps
    out.append('<section class="section section--dark plan"><div class="wrap"><div class="center section-head"><h2>%s</h2></div>%s'
               '<div class="center plan__cta">%s</div></div></section>' % (e(pl['heading']), steps(pl['steps']), btn(cta['label'], cta['href'])))
    # 4 showcase: numbered tour of everything on offer
    panels = ''.join(
        '<article class="showcase__panel card" id="showcase-panel-%d" data-panel="%d"><div class="showcase__art">%s</div>'
        '<div class="showcase__body"><p class="showcase__tag"><span>%s</span> <span class="showcase__num">%s</span></p>'
        '<h3>%s</h3><p class="showcase__meta">%s</p><p>%s</p>%s</div></article>'
        % (i, i, art(it['art']), e(it['tag']), pad(i + 1), e(it['title']), e(it['meta']), e(it['text']), btn(it['cta'], it['href'], 'btn--dark'))
        for i, it in enumerate(sh['items']))
    tabs = ''.join('<li><button type="button" data-tab="%d" aria-controls="showcase-panel-%d" aria-pressed="%s">'
                   '<span class="showcase__tabnum">%s</span> %s</button></li>' % (i, i, 'true' if i == 0 else 'false', pad(i + 1), e(it['tab']))
                   for i, it in enumerate(sh['items']))
    out.append('<section class="section showcase"><div class="wrap"><div class="showcase__head"><div><p class="eyebrow">%s</p><h2>%s</h2><p class="lede">%s</p></div>'
               '<div class="showcase__controls" hidden><p class="showcase__count" aria-live="polite"><span data-current>01</span> / %s</p>'
               '<button class="showcase__arrow" type="button" data-prev aria-label="Previous item">←</button>'
               '<button class="showcase__arrow" type="button" data-next aria-label="Next item">→</button></div></div>'
               '<div class="showcase__stage">%s</div><ol class="showcase__tabs" hidden>%s</ol></div></section>'
               % (e(sh['eyebrow']), e(sh['heading']), e(sh['intro']), pad(len(sh['items'])), panels, tabs))
    # 5 lead magnet
    out.append('<section class="section section--tint lead" id="free-guide"><div class="wrap lead__grid"><div class="lead__cover" aria-hidden="true">'
               '<div class="guide-cover"><span class="guide-cover__kicker">Free guide</span><span class="guide-cover__title">%s</span>'
               '<span class="guide-cover__sub">%s</span><span class="guide-cover__brand">%s</span></div></div>'
               '<div><p class="eyebrow">%s</p><h2>%s</h2><p class="lede">%s</p>%s</div></div></section>'
               % (e(lm['guide_title']), e(lm['guide_subtitle']), e(SITE['name']), e(lm['eyebrow']), e(lm['heading']), e(lm['text']),
                  signup_form('lead-email', 'btn--dark')))
    # 6 testimonials
    quotes = ''.join('<li><figure class="card quote"><p class="quote__group">%s</p><blockquote>“%s”</blockquote>'
                     '<figcaption><strong>%s</strong><span>%s</span></figcaption></figure></li>'
                     % (e(q['group']), e(q['quote']), e(q['name']), e(q.get('role', ''))) for q in ts['items'])
    if DRAFT:
        quotes += ''.join('<li><figure class="card quote quote--blank"><p class="quote__group">%s</p>'
                          '<blockquote aria-hidden="true"><span></span><span></span><span></span></blockquote>'
                          '<figcaption>%s</figcaption></figure></li>' % (e(g), draft('%s testimonial to add' % g))
                          for g in ts.get('placeholder_groups', []))
    if quotes:
        out.append('<section class="section testimonials"><div class="wrap"><div class="center section-head"><p class="eyebrow">%s</p><h2>%s</h2>'
                   '<p class="lede">%s</p></div><ul class="grid grid--3">%s</ul></div></section>'
                   % (e(ts['eyebrow']), e(ts['heading']), e(ts['intro']), quotes))
    # teachers: a separate audience, so a separate section rather than a fourth path
    tb = SITE.get('teachers_band')
    if tb:
        out.append('<section class="section section--tint" id="teachers"><div class="wrap grid grid--2 offer__split"><div><p class="eyebrow">%s</p>'
                   '<h2>%s</h2><p class="lede">%s</p><p style="margin-top:1.5rem">%s</p></div><ul class="ticks card">%s</ul></div></section>'
                   % (e(tb['eyebrow']), e(tb['heading']), e(tb['text']), btn(tb['cta']['label'], tb['cta']['href'], 'btn--dark'),
                      ''.join('<li>%s</li>' % e(x) for x in tb['points'])))
    # 7 closing: repeat the paths so the last thing on the page is the next step
    out.append('<section class="section section--dark closing"><div class="wrap"><div class="section-head closing__head"><p class="eyebrow">%s</p>'
               '<h2>%s</h2><p class="lede">%s</p></div>%s</div></section>' % (e(cl['eyebrow']), e(cl['heading']), e(cl['text']), path_cards(compact=True)))
    return '\n'.join(out)


def offer(key):
    """Sales page: hero, what's at stake, what you get, plan, guide, FAQ, closing call to action."""
    o = SITE['offers'][key]
    buy_url = o.get('buy_url')
    if buy_url:
        cta = btn(o.get('cta_buy', 'Buy Now'), buy_url)
    else:
        cta = btn(o['cta_wait'], o.get('cta_href', '/contact.html'))
    extra = ''
    if o.get('soon'):
        extra += '<p class="page-hero__price"><strong>Opening soon.</strong> Join the list to hear first.</p>'
    if o.get('show_price') and (o.get('price') or DRAFT):
        extra += '<p class="page-hero__price">Price: %s</p>' % ('<strong>%s</strong>' % e(o['price']) if o.get('price') else draft('Price to confirm'))
    prev = o.get('previous_edition')
    edition = ''
    if not buy_url and prev and prev.get('buy_url'):
        edition = ('<p class="edition-note">The new edition is on its way. Until it arrives you can still buy the first edition, '
                   '<a href="%s" rel="noopener">%s (%s)</a>.</p>' % (e(prev['buy_url']), e(prev['title']), e(prev['price'])))
    out = ['<section class="page-hero"><div class="wrap"><p class="eyebrow" style="color: var(--accent)">%s</p><h1>%s</h1><p class="lede">%s</p>'
           '<div class="page-hero__actions">%s%s</div>%s</div></section>' % (e(o['audience']), e(o['heading']), e(o['lead']), cta, extra, edition)]
    s = o['stakes']
    out.append('<section class="section"><div class="wrap grid grid--2 offer__split"><div><p class="eyebrow">The Problem</p><h2>%s</h2><p class="lede">%s</p></div>'
               '<ul class="ticks crosses card">%s</ul></div></section>' % (e(s['heading']), e(s['text']), ''.join('<li>%s</li>' % e(i) for i in s['items'])))
    of = o['offer']
    items = ''.join('<li class="card offer__item"><span class="offer__num" aria-hidden="true">%02d</span><h3>%s</h3><p>%s</p></li>'
                    % (n + 1, e(i['title']), e(i['text'])) for n, i in enumerate(of['items']))
    inc = ''
    if of.get('includes'):
        inc = ('<div class="offer__includes card"><h3>What Is Included</h3><ul class="ticks">%s</ul>%s</div>'
               % (''.join('<li>%s</li>' % e(i) for i in of['includes']), draft(of.get('includes_review', ''), note=True) if of.get('includes_review') else ''))
    out.append('<section class="section section--tint"><div class="wrap"><div class="offer__head"><p class="eyebrow">The Solution</p><h2>%s</h2>%s</div>'
               '<ul class="grid grid--3">%s</ul>%s</div></section>'
               % (e(of['heading']), draft(of['needs_review'], note=True) if of.get('needs_review') else '', items, inc))
    out.append('<section class="section section--dark"><div class="wrap"><div class="center offer__head"><h2>How It Works</h2></div>%s</div></section>' % steps(o['steps']))
    g = SITE['guide']
    out.append('<section class="section"><div class="wrap grid grid--2 offer__split"><div><p class="eyebrow">Your Guide</p>'
               '<h2>From a Teacher Who Learned It the Slow Way</h2><p class="lede">%s</p>'
               '<p><a class="offer__link" href="/simon-horsey.html">Meet Simon <span aria-hidden="true">→</span></a></p>%s</div>'
               '<ul class="ticks card">%s</ul></div></section>'
               % (e(g['lead']), draft(g['needs_review'], note=True), ''.join('<li>%s</li>' % e(c) for c in g['credentials'])))
    faqs = [f for f in o.get('faqs', []) if f.get('a') or DRAFT]
    if faqs:
        out.append('<section class="section section--tint"><div class="wrap narrow"><h2>Questions People Ask</h2><div class="faq">%s</div></div></section>'
                   % ''.join('<details><summary>%s</summary><div>%s</div></details>'
                             % (e(f['q']), '<p>%s</p>' % e(f['a']) if f.get('a') else draft('Answer to add')) for f in faqs))
    out.append('<section class="section section--dark center"><div class="wrap"><h2 class="offer__closing">%s</h2>%s</div></section>' % (e(o['closing']), cta))
    return '\n'.join(out)


def guide_page():
    lm = SITE['lead_magnet']
    return ('<section class="page-hero"><div class="wrap"><p class="eyebrow" style="color: var(--accent)">%s</p><h1>%s</h1><p class="lede">%s</p>'
            '<div style="margin-top:1.75rem;max-width:560px">%s</div></div></section>'
            '<section class="section center"><div class="wrap"><h2>Ready for the Full Method?</h2>'
            '<p class="lede">The guide gets you started. The Practice Code takes you the rest of the way.</p><p>%s</p></div></section>'
            % (e(lm['eyebrow']), e(lm['heading']), e(lm['text']), signup_form('guide-email'), btn(SITE['primary_cta']['label'], SITE['primary_cta']['href'], 'btn--dark')))


def article_list(pages, section_id, exclude=None, limit=None):
    items = [p for p in pages if p['section'] == section_id and p['slug'] != exclude]
    if limit:
        items = items[:limit]
    return ''.join('<li><a href="%s">%s</a></li>' % (p['path'], e(p['nav_title'])) for p in items)


def tips_index(pages):
    out = ['<section class="page-hero"><div class="wrap"><p class="eyebrow" style="color: var(--accent)">Free library</p><h1>Practice Tips</h1>'
           '<p class="lede">Every article on the site, by topic. New here? Start with the free guide, then pick whatever is bothering you this week.</p>'
           '<div class="page-hero__actions">%s</div></div></section><section class="section"><div class="wrap">'
           % btn('Get the Free Guide', '/how-to-practice.html')]
    for s in SITE['sections']:
        items = article_list(pages, s['id'])
        if items:
            out.append('<div class="topic" id="%s"><h2>%s</h2><p class="topic-blurb">%s</p><ul class="link-list">%s</ul></div>'
                       % (s['id'], e(s['title']), e(s['blurb']), items))
    out.append('</div></section>')
    return ''.join(out)


def article(page, pages, body):
    sec = {s['id']: s for s in SITE['sections']}.get(page['section'])
    crumb = ('<p class="crumb"><a href="/music-practice-blog.html">Practice Tips</a> · <a href="/music-practice-blog.html#%s">%s</a></p>'
             % (sec['id'], e(sec['title']))) if sec else ''
    out = ['<section class="page-hero page-hero--article"><div class="wrap">%s<h1>%s</h1></div></section>' % (crumb, e(page['title'])),
           '<section class="article"><div class="wrap"><div class="prose">%s</div></div></section>' % body]
    if sec:
        out.append('<section class="section section--tint"><div class="wrap next-step"><div><p class="eyebrow">The full method</p>'
                   '<h2>Want All of It in One Place?</h2><p class="lede">Everything I teach about practice is in The Practice Code: seven elements, a handful of students who got stuck exactly where you are, and no jargon.</p></div>'
                   '<div class="next-step__actions">%s%s</div></div></section>'
                   % (btn('Explore The Practice Code', '/the-practice-code.html', 'btn--dark'), btn('Get the Free Guide', '/how-to-practice.html', 'btn--ghost', arrow=False)))
        related = article_list(pages, page['section'], exclude=page['slug'], limit=9)
        if related:
            out.append('<section class="section related"><div class="wrap"><h2>More on %s</h2><ul class="link-list">%s</ul></div></section>'
                       % (e(sec['title'].lower()), related))
    return '\n'.join(out)


# ------------------------------------------------------------------ build

def load_pages():
    pages = []
    for f in sorted(os.listdir(os.path.join(ROOT, 'content'))):
        if not f.endswith('.html'):
            continue
        raw = read('content/' + f)
        meta, body = {}, raw
        m = re.match(r'---\n(.*?)\n---\n?(.*)$', raw, re.S)
        if m:
            body = m.group(2)
            for line in m.group(1).splitlines():
                k, _, v = line.partition(':')
                meta[k.strip()] = v.strip()
        slug = f[:-5]
        pages.append({'slug': slug, 'path': '/' if slug == 'index' else '/' + f,
                      'title': meta.get('title', slug), 'nav_title': meta.get('nav_title') or meta.get('title', slug),
                      'description': meta.get('description', ''), 'section': meta.get('section', 'page'),
                      'layout': meta.get('layout', 'article'), 'offer': meta.get('offer', ''),
                      'updated': meta.get('updated', ''), 'noindex': meta.get('noindex', '') == 'true', 'body': body})
    return pages


def json_ld(page):
    author = {'@type': 'Person', 'name': SITE['author'], 'url': URL + '/simon-horsey.html'}
    if page['layout'] == 'home':
        d = {'@type': 'WebSite', 'name': SITE['name'], 'url': URL + '/', 'author': author}
    elif page['offer'] in ('book', 'first-steps'):
        d = {'@type': 'Book', 'name': SITE['offers'][page['offer']]['product'], 'author': author, 'description': page['description'], 'url': URL + page['path']}
    elif page['layout'] == 'article' and page['section'] != 'page':
        d = {'@type': 'Article', 'headline': page['title'], 'description': page['description'], 'author': author, 'mainEntityOfPage': URL + page['path']}
        if page['updated']:
            d['dateModified'] = page['updated']
    else:
        return ''
    d = dict({'@context': 'https://schema.org'}, **d)
    return '<script type="application/ld+json">%s</script>' % json.dumps(d, ensure_ascii=False)


def fill_body(page):
    """Content files may use {{contact_form}}, {{signup_form}} and {{draft: some note}}."""
    body = page['body'].replace('{{contact_form}}', contact_form()).replace('{{signup_form}}', signup_form('page-email', 'btn--dark'))
    return re.sub(r'\{\{draft:\s*(.*?)\}\}', lambda m: draft(m.group(1), note=True), body)


def resolve(redirects):
    out = {}
    for src, dst in redirects.items():
        seen = set()
        while dst in redirects and dst not in seen:
            seen.add(dst)
            dst = redirects[dst]
        out[src] = dst
    return out


def build():
    pages = load_pages()
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    shutil.copytree(os.path.join(ROOT, 'static'), DIST)
    head, foot = header(), footer()
    for page in pages:
        layout = page['layout']
        if layout == 'home':
            main, title, desc = home(), SITE['title'], SITE['description']
        elif layout == 'offer':
            o = SITE['offers'][page['offer']]
            main, title, desc = offer(page['offer']), '%s | %s' % (o['page_title'], SITE['name']), o['description']
        elif layout == 'guide':
            main, title, desc = guide_page(), '%s | %s' % (page['title'], SITE['name']), page['description']
        elif layout == 'index':
            main, title, desc = tips_index(pages), '%s | %s' % (page['title'], SITE['name']), page['description']
        else:
            main, title, desc = article(page, pages, fill_body(page)), '%s | %s' % (page['title'], SITE['name']), page['description']
        page['description'] = desc
        robots = '<meta name="robots" content="noindex, nofollow">' if (DRAFT or page['noindex']) else ''
        doc = ('<!doctype html>\n<html lang="%s" data-theme="%s">\n<head>\n<meta charset="utf-8">%s\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
               '<title>%s</title>\n<meta name="description" content="%s">\n<link rel="canonical" href="%s">\n%s\n'
               '<meta name="theme-color" content="#0d1b2a">\n<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
               '<meta property="og:type" content="website">\n<meta property="og:site_name" content="%s">\n<meta property="og:title" content="%s">\n'
               '<meta property="og:description" content="%s">\n<meta property="og:url" content="%s">\n<meta property="og:image" content="%s/music-practice-fb.png">\n'
               '<link rel="alternate" type="application/rss+xml" title="%s" href="/music-practice.xml">\n'
                              '<link rel="stylesheet" href="/css/site.css">\n%s\n</head>\n<body>\n<a class="skip" href="#main">Skip to content</a>\n%s\n'
               '<main id="main">\n%s\n</main>\n%s\n%s<script src="/js/site.js" defer></script>\n</body>\n</html>\n'
               % (e(SITE['locale']), THEME, THEME_BOOT if SWITCH else '', e(title), e(desc), URL + page['path'], robots, e(SITE['name']), e(title), e(desc), URL + page['path'], URL,
                  e(SITE['name']), json_ld(page), head, main, foot, THEME_SWITCH if SWITCH else ''))
        with open(os.path.join(DIST, 'index.html' if page['slug'] == 'index' else page['slug'] + '.html'), 'w', encoding='utf-8') as f:
            f.write(doc)

    redirects = resolve(SITE['redirects'])
    with open(os.path.join(DIST, '_redirects'), 'w') as f:
        # With html_handling "none" (which keeps the old .html addresses) Cloudflare does not serve
        # index.html at "/" by itself, so the home page is proxied to it.
        f.write('# Generated from site.json by build.py\n/ /index.html 200\n')
        for src, dst in redirects.items():
            f.write('%s %s 301\n' % (src, dst))
    indexable = [p for p in pages if not p['noindex'] and p['slug'] != '404']
    with open(os.path.join(DIST, 'sitemap.xml'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for p in indexable:
            f.write('  <url><loc>%s%s</loc>%s</url>\n' % (URL, p['path'], '<lastmod>%s</lastmod>' % p['updated'] if p['updated'] else ''))
        f.write('</urlset>\n')
    with open(os.path.join(DIST, 'robots.txt'), 'w') as f:
        f.write('User-agent: *\nDisallow: /*.pdf$\n\nSitemap: %s/sitemap.xml\n' % URL)
    feed = sorted([p for p in indexable if p['section'] != 'page' and p['updated']], key=lambda p: p['updated'], reverse=True)[:20]
    with open(os.path.join(DIST, 'music-practice.xml'), 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>\n<title>%s</title>\n<link>%s/</link>\n<description>%s</description>\n'
                % (e(SITE['name']), URL, e(SITE['tagline'])))
        for p in feed:
            f.write('<item><title>%s</title><link>%s%s</link><guid>%s%s</guid><description>%s</description></item>\n'
                    % (e(p['title']), URL, p['path'], URL, p['path'], e(p['description'])))
        f.write('</channel></rss>\n')
    print('built %d pages, %d redirects, draft=%s -> dist/' % (len(pages), len(redirects), DRAFT))


if __name__ == '__main__':
    build()
    if '--serve' in sys.argv:
        import functools, http.server
        port = int(os.environ.get('PORT', '8000'))
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIST)
        print('serving http://localhost:%d' % port)
        http.server.ThreadingHTTPServer(('127.0.0.1', port), handler).serve_forever()
