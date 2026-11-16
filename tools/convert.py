"""One-off converter: source/pages/*.html (old SBI pages) -> content/*.html

Each output file is a small front-matter header plus the cleaned article HTML.
Strips the SBI wrapper, ads, social widgets, forms, tracking attributes and dead links.

Existing content files are NOT overwritten unless you pass --force, so hand edits are safe.
Usage:  python3 tools/convert.py [--force]
"""
import html, json, os, re, sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'source', 'pages')
OUT = os.path.join(ROOT, 'content')
SITE = json.load(open(os.path.join(ROOT, 'site.json')))
REDIRECTS = SITE['redirects']
HOST = 'essential-music-practice.com'
FORCE = '--force' in sys.argv

# Pages written by hand in content/ (never generated from the old page).
HAND_WRITTEN = {'index', 'practice-makes-perfect', 'how-to-practice', 'contact',
                'practical-practice', 'music-practice-blog', 'privacy-policy'}
# Old pages that are deliberately not migrated and have no redirect.
NOT_MIGRATED = {'chat', 'sjrehearsal'}

SECTION = {
    'technique': '''efficient-practice faster-progress slow-practice learning-new-pieces count-out-loud
        speeding-up recording-practice regular-practice-review one-week-study music-practice-games
        stay-motivated practice-tracks minus-one-cds slow-down-music transcribe-music
        holiday-music-practice''',
    'scales': 'scales-practice learning-scales scale-practice-tips how-to-speed-up-scales scalebox-app',
    'planning': '''planning-practice practice-planning-charts music-practice-charts practice-targets
        musical-goals music-goals fail-to-achieve-goals lesson-notes music-lesson-notes file-music''',
    'performing': 'performance-anxiety practice-performing beta-blockers biofeedback encourage-performance',
    'parents': '''kids-and-practice encourage-practice start-learning learn-an-instrument
        school-music-equipment licensing-practice-makes-perfect''',
    'tools': '''metronome which-metronome electronic-or-clockwork boss-db90 digital-audio-recorder
        zoom-digital-recorder zoom-h2 zoom-h4n music-practice-software piano-software ear-master
        music-practice-books sheet-music download-sheet-music online-music-courses online-piano-lessons
        learn-to-play-keyboard learn-to-play-bass-guitar learning-to-play-bass-guitar-the-story-so-far''',
    'inspiration': 'quotes-about-music quotes-by-musicians',
}
SLUG_SECTION = {slug: sec for sec, slugs in SECTION.items() for slug in slugs.split()}

# Outbound links that were dead when the old site was crawled (16 Nov 2026): keep the text, drop the link.
DEAD_HOSTS = ('astore.amazon.', 'sitesell.com', 'lulu.com/content', 'lulu.com/shop', 'click.linksynergy.com',
              'bit.ly/ScrDlN', 'musicianshealth.com', 'tes.co.uk/article', 'pocketsongs.com',
              'sonycreativesoftware.com', 'www.http//', 'essential-music.practice.com',
              'essential-music-theory.com/contact.html', 'play.google.com/store/apps/details?id=co.uk.scalebox',
              'id593299414', 'id436394592', 'id527626664', 'id454753605', 'get.adobe.com', 'goo.gl/')
DEAD_AMAZON = ('B001B8PIIE', 'B001FA1O0E', 'B002VSA7R0', 'gp/redirect.html')
AFFILIATE = ('zzounds.com', 'amazon.', 'amzn.to', 'clickbank.net', 'shareasale.com', 'avangate.com',
             'itunes.apple.com', 'e-junkie.com')
DEAD_INTERNAL = ('/getting-over-the-plateau.html', '/onclick=')

lastmod = {}
sm = open(os.path.join(ROOT, 'source', 'sitemap-original.xml'), errors='ignore').read()
for loc, lm in re.findall(r'<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>', sm):
    lastmod[loc.rstrip('/').split('/')[-1].replace('.html', '') or 'index'] = lm[:10]
lastmod['www.essential-music-practice.com'] = lastmod.get('index', '')

IMAGES = set(os.listdir(os.path.join(ROOT, 'static', 'images')))


def fix_href(href):
    """Return a cleaned href, or None to unwrap the link (keep its text)."""
    href = html.unescape(href).strip()
    if href.startswith('//'):
        href = 'https:' + href
    if 'learn.essential-music-practice.com' in href:
        return SITE['course_url']
    m = re.match(r'https?://(?:www\.)?' + re.escape(HOST) + r'(/.*)?$', href)
    if m:
        href = m.group(1) or '/'
    if href.startswith('/') or not re.match(r'[a-z]+:', href):
        if not href.startswith(('/', '#')):
            href = '/' + href
        path, _, frag = href.partition('#')
        if frag in ('INV', 'SOUND') or path.endswith('-comment-form.html'):
            return None
        path = re.sub(r'(\.pdf)/$', r'\1', path)
        if path == '/music-practice-charts':
            path = '/music-practice-charts.html'
        if path in DEAD_INTERNAL or path.startswith('/%E2%80%9D'):
            return None
        path = REDIRECTS.get(path, path)
        return path + ('#' + frag if frag else '')
    if any(d in href for d in DEAD_HOSTS) or any(d in href for d in DEAD_AMAZON):
        return None
    return href


KEEP = {'p', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'a', 'img', 'strong', 'em', 'blockquote', 'br', 'hr',
        'table', 'thead', 'tbody', 'tr', 'td', 'th', 'figure', 'aside', 'sup', 'sub'}
RENAME = {'b': 'strong', 'i': 'em', 'h1': 'h2'}
VOID = {'br', 'hr', 'img'}


class Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.h1 = None
        self._in_h1 = False
        self._h1buf = []
        self.divs = []      # closing tag to emit for each open <div>
        self.links = []     # True if the open <a> was emitted

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'h1' and self.h1 is None:
            self._in_h1 = True
            return
        if self._in_h1:
            if tag == 'br':
                self._h1buf.append(' ')
            return
        if tag == 'div':
            cls = a.get('class', '') or ''
            if 'ImageBlock' in cls:
                side = 'right' if 'Right' in cls else 'left' if 'Left' in cls else 'center'
                self.out.append('<figure class="img-%s">' % side)
                self.divs.append('</figure>')
            elif 'CalloutBox' in cls:
                self.out.append('<aside class="callout">')
                self.divs.append('</aside>')
            else:
                self.divs.append('')
            return
        tag = RENAME.get(tag, tag)
        if tag not in KEEP:
            return
        if tag == 'a':
            href = fix_href(a['href']) if a.get('href') else None
            if href is None:
                self.links.append(False)
                return
            self.links.append(True)
            extra = ''
            if re.match(r'https?:', href):
                rel = 'sponsored nofollow noopener' if any(x in href for x in AFFILIATE) else 'noopener'
                extra = ' rel="%s" target="_blank"' % rel
            self.out.append('<a href="%s"%s>' % (html.escape(href, quote=True), extra))
            return
        if tag == 'img':
            src = html.unescape(a.get('src', ''))
            name = src.rsplit('/', 1)[-1]
            if HOST in src or src.startswith('/'):
                if name not in IMAGES:
                    return
                src = '/images/' + name
            elif 'e-junkie.com' in src or 'shareasale.com' in src or not src:
                return
            dims = ''
            for k in ('width', 'height'):
                v = (a.get(k) or '').split('.')[0]
                if v.isdigit():
                    dims += ' %s="%s"' % (k, v)
            self.out.append('<img src="%s" alt="%s"%s loading="lazy">' % (
                html.escape(src, quote=True), html.escape(a.get('alt') or '', quote=True), dims))
            return
        self.out.append('<%s>' % tag)

    def handle_endtag(self, tag):
        if tag == 'h1' and self._in_h1:
            self._in_h1 = False
            self.h1 = ' '.join(''.join(self._h1buf).split())
            return
        if self._in_h1:
            return
        if tag == 'div':
            if self.divs:
                self.out.append(self.divs.pop())
            return
        tag = RENAME.get(tag, tag)
        if tag == 'a':
            if self.links and self.links.pop():
                self.out.append('</a>')
            return
        if tag in KEEP and tag not in VOID:
            self.out.append('</%s>' % tag)

    def handle_data(self, data):
        if self._in_h1:
            self._h1buf.append(data)
        else:
            self.out.append(html.escape(data, quote=False))


def clean(raw):
    a = raw.find('id="ContentColumn"')
    b = raw.find('id="FooterWrapper"')
    if a < 0:
        return None, ''
    c = raw[raw.find('>', a) + 1:b]
    prev = None
    while prev != c:  # site-wide SBI blocks (promo box, what's new, forms, visitor submissions)
        prev = c
        c = re.sub(r'<!-- start: ((?:shared|tool)_blocks\.[^ ]+) -->.*?<!-- end: \1 -->', '', c, flags=re.S)
    c = re.sub(r'<!--.*?-->', '', c, flags=re.S)
    c = re.sub(r'<(script|style|form|ins|noscript|iframe|select|textarea)\b.*?</\1>', '', c, flags=re.S | re.I)
    c = re.sub(r'<div class="pinit".*?</div>', '', c, flags=re.S)
    p = Cleaner()
    p.feed(c)
    out = ''.join(p.out)
    out = out.replace('\xa0', ' ')
    out = re.sub(r'\(\s*(?:This|this)?\s*(?:page |link )?opens? in a new window[^)]*\)', '', out)
    out = re.sub(r'<a [^>]*>\s*(?:<strong>)?\s*Return to [^<]*(?:</strong>)?\s*</a>', '', out, flags=re.I)
    out = re.sub(r'<a [^>]*>\s*</a>', '', out)
    out = re.sub(r'(<br>\s*){2,}', '<br>', out)
    out = re.sub(r'<(h[234])>\s*(?:<strong>)?\s*(?:<br>)?\s*(.*?)\s*(?:<br>)?\s*(?:</strong>)?\s*</\1>', r'<\1>\2</\1>', out, flags=re.S)
    for _ in range(4):
        out = re.sub(r'<(p|strong|em|h2|h3|h4|li|figure|aside|blockquote|span)>(\s|<br>)*</\1>', '', out)
    out = re.sub(r'<p>\s*<br>\s*', '<p>', out)
    out = re.sub(r'\s*<br>\s*</p>', '</p>', out)
    out = re.sub(r'(<hr>\s*)+', '<hr>\n', out)
    out = re.sub(r'(\s*<hr>\s*)+$', '', out.strip())
    out = re.sub(r'[ \t]+', ' ', out)
    out = re.sub(r'\s*\n\s*', '\n', out)
    out = re.sub(r'</(p|h2|h3|h4|ul|ol|figure|aside|table|blockquote)>', r'</\1>\n', out)
    out = re.sub(r'<p>\s*(?=<(?:p|h2|h3|h4|ul|ol|figure|aside|table|hr|blockquote)\b)', '', out)
    out = re.sub(r'(</(?:p|h2|h3|h4|ul|ol|figure|aside|table|blockquote)>)\s*</p>', r'\1', out)
    out = re.sub(r'<p>\s*</p>', '', out)
    out = re.sub(r'\n{2,}', '\n', out).strip()
    return p.h1, out


def meta(raw, name):
    m = re.search(r'<meta\s+name="%s"\s+content="(.*?)"' % name, raw, re.S | re.I)
    if not m:
        return ''
    return ' '.join(re.sub(r'<[^>]+>', '', html.unescape(html.unescape(m.group(1)))).split())


def main():
    os.makedirs(OUT, exist_ok=True)
    made = skipped = dropped = 0
    for f in sorted(os.listdir(SRC)):
        slug = f[:-5]
        if slug in HAND_WRITTEN or slug in NOT_MIGRATED or '/' + f in REDIRECTS:
            dropped += 1
            continue
        dest = os.path.join(OUT, f)
        if os.path.exists(dest) and not FORCE:
            skipped += 1
            continue
        raw = open(os.path.join(SRC, f), errors='ignore').read()
        h1, body = clean(raw)
        if h1 is None and not body:
            print('no content column, skipped:', f)
            continue
        t = re.search(r'<title>(.*?)</title>', raw, re.S | re.I)
        title = ' '.join(re.sub(r'<[^>]+>', '', html.unescape(t.group(1))).split()) if t else slug
        fm = ['---', 'title: ' + (h1 or title), 'description: ' + meta(raw, 'description'),
              'section: ' + SLUG_SECTION.get(slug, 'page'), 'updated: ' + lastmod.get(slug, ''), '---', '']
        open(dest, 'w').write('\n'.join(fm) + body + '\n')
        made += 1
    print('written %d, kept existing %d, not migrated (redirected or hand-written) %d' % (made, skipped, dropped))


if __name__ == '__main__':
    main()
