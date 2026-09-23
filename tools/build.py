#!/usr/bin/env python3
"""Сборка сайта: общие шапка, подвал и блог-блоки во всех страницах.

Страницы остаются обычным HTML. Скрипт заменяет только участки между
маркерами вида

    <!-- build:header -->  ...  <!-- /build:header -->

и пересобирает sitemap.xml. Всё остальное в файлах не трогается,
поэтому текст страниц и статей можно править руками.

Запуск из корня проекта:
    python3 tools/build.py          — собрать
    python3 tools/build.py --check  — только проверить, всё ли собрано (код 1, если нет)

Зависимостей нет, нужен только Python 3.8+.
"""

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://shakonuko.com"
PARTIALS = ROOT / "partials"

# Пункты основного меню: (ключ, подпись, путь от корня сайта; "" — главная)
NAV = [
    ("home", "Главная", ""),
    ("about", "Обо мне", "about.html"),
    ("services", "Услуги", "services.html"),
    ("blog", "Блог", "blog/"),
    ("contacts", "Контакты", "contacts.html"),
]

# Страницы сайта (кроме статей блога — они находятся автоматически).
#   nav      — какой пункт меню подсветить (None — никакой)
#   cta      — куда ведут кнопки «Записаться»
#   sitemap  — (priority, changefreq) или None, если страницу не нужно индексировать
#   root     — префикс ссылок, если нужен не относительный (для 404.html)
PAGES = {
    "index.html":      dict(nav="home",     sitemap=("1.0", "monthly")),
    "about.html":      dict(nav="about",    sitemap=("0.8", "yearly")),
    "services.html":   dict(nav="services", sitemap=("0.9", "monthly")),
    "contacts.html":   dict(nav="contacts", sitemap=("0.7", "yearly"), cta="#form"),
    "blog/index.html": dict(nav="blog",     sitemap=("0.8", "monthly")),
    "privacy.html":    dict(nav=None,       sitemap=("0.2", "yearly")),
    # 404 открывается по любому адресу, поэтому ссылки в ней — от корня сайта
    "404.html":        dict(nav=None,       sitemap=None, root="/"),
}

MONTHS = ("января февраля марта апреля мая июня июля "
          "августа сентября октября ноября декабря").split()


# ---------------------------------------------------------------- утилиты

def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def human_date(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def rel_root(path):
    """Префикс до корня сайта для файла: '' или '../'."""
    return "../" * (len(Path(path).parts) - 1)


def href(root, target):
    """Ссылка на страницу сайта: главная — на каталог, без index.html."""
    return (root + target) or "./"


def url_of(path):
    """Канонический адрес страницы."""
    p = str(path).replace("\\", "/")
    if p == "index.html":
        return SITE + "/"
    if p.endswith("/index.html"):
        return f"{SITE}/{p[:-len('index.html')]}"
    return f"{SITE}/{p}"


def partial(name, **values):
    text = (PARTIALS / name).read_text(encoding="utf-8")
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", val)
    left = re.findall(r"\{\{\w+\}\}", text)
    if left:
        raise SystemExit(f"partials/{name}: не заполнены {', '.join(sorted(set(left)))}")
    return text.rstrip("\n")


def replace_region(text, name, content, path, required=True):
    pattern = re.compile(
        r"(<!-- build:%s -->)(.*?)(<!-- /build:%s -->)" % (re.escape(name), re.escape(name)),
        re.S,
    )
    if not pattern.search(text):
        if required:
            raise SystemExit(f"{path}: нет маркера <!-- build:{name} -->")
        return text
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", text, count=1)


def ld_script(obj):
    body = json.dumps(obj, ensure_ascii=False, indent=1)
    return f'<script type="application/ld+json">\n{body}\n</script>'


# ---------------------------------------------------------------- статьи

def meta(text, attr, name):
    m = re.search(r'<meta %s="%s" content="([^"]*)">' % (attr, re.escape(name)), text)
    return html.unescape(m.group(1)) if m else None


def load_posts():
    posts = []
    for path in sorted((ROOT / "blog").glob("*.html")):
        if path.name == "index.html":
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()

        title = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
        lead = re.search(r'<p class="article__lead">(.*?)</p>', text, re.S)
        body = re.search(r'<article class="article">(.*?)</article>', text, re.S)
        published = meta(text, "property", "article:published_time")
        modified = meta(text, "property", "article:modified_time") or published
        missing = [n for n, v in (("<h1>", title), ('<p class="article__lead">', lead),
                                  ('<article class="article">', body),
                                  ("article:published_time", published)) if not v]
        if missing:
            raise SystemExit(f"{rel}: не хватает {', '.join(missing)}")

        # время чтения — по тексту статьи без служебных блоков
        plain = re.sub(r"<!-- build:.*?<!-- /build:[\w-]+ -->", " ", body.group(1), flags=re.S)
        plain = re.sub(r"<[^>]+>", " ", plain)
        words = len(html.unescape(plain).split())
        minutes = max(1, round(words / 160))

        posts.append(dict(
            path=rel, file=path.name, url=url_of(rel),
            title=re.sub(r"\s+", " ", title.group(1)).strip(),
            description=meta(text, "name", "description") or "",
            lead=re.sub(r"\s+", " ", lead.group(1)).strip(),
            published=published, modified=modified,
            words=words, minutes=minutes,
            reading=f"{minutes} {plural(minutes, 'минута', 'минуты', 'минут')} чтения",
        ))
    posts.sort(key=lambda p: p["published"], reverse=True)
    return posts


def post_meta_html(p):
    return (f'    <p class="article__meta"><span>Лариса Шаканукова</span>'
            f'<span aria-hidden="true">·</span>'
            f'<time datetime="{p["published"][:10]}">{human_date(p["published"])}</time>'
            f'<span aria-hidden="true">·</span><span>{p["reading"]}</span></p>')


def post_nav_html(posts, i):
    newer = posts[i - 1] if i > 0 else None
    older = posts[i + 1] if i < len(posts) - 1 else None
    out = ['  <nav class="post-nav" aria-label="Другие статьи">']
    if older:
        out.append(f'    <a class="post-nav__item" href="{older["file"]}"><span>Предыдущая</span>'
                   f'<strong>{older["title"]}</strong></a>')
    if newer:
        out.append(f'    <a class="post-nav__item post-nav__item--next" href="{newer["file"]}">'
                   f'<span>Следующая</span><strong>{newer["title"]}</strong></a>')
    out.append("  </nav>")
    return "\n".join(out)


def post_ld(p):
    return ld_script({"@context": "https://schema.org", "@graph": [
        {"@type": "BlogPosting", "@id": p["url"] + "#post",
         "headline": p["title"], "description": p["description"],
         "inLanguage": "ru-RU", "url": p["url"],
         "image": SITE + "/assets/img/og-image.jpg",
         "datePublished": p["published"], "dateModified": p["modified"],
         "wordCount": p["words"], "timeRequired": f'PT{p["minutes"]}M',
         "author": {"@type": "Person", "@id": SITE + "/#person",
                    "name": "Шаканукова Лариса Тольбиевна", "url": SITE + "/about.html"},
         "publisher": {"@id": SITE + "/#person"},
         "mainEntityOfPage": {"@type": "WebPage", "@id": p["url"]},
         "isPartOf": {"@type": "Blog", "@id": SITE + "/blog/#blog"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Блог", "item": SITE + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": p["url"]}]},
    ]})


def blog_entries_html(posts):
    out = []
    for p in posts:
        out.append(f"""      <article class="entry">
        <h2 class="entry__title"><a href="{p['file']}">{p['title']}</a></h2>
        <p class="entry__excerpt">{p['lead']}</p>
        <p class="entry__meta"><span><time datetime="{p['published'][:10]}">{human_date(p['published'])}</time> · {p['reading']}</span><span class="entry__cue">Читать →</span></p>
      </article>""")
    return "\n".join(out)


def blog_ld(posts):
    url = SITE + "/blog/"
    return ld_script({"@context": "https://schema.org", "@graph": [
        {"@type": "Blog", "@id": url + "#blog", "name": "Блог Ларисы Шакануковой",
         "url": url, "inLanguage": "ru-RU",
         "description": "Заметки психоаналитического психотерапевта о психических защитах, "
                        "самосаботаже и о том, как устроена психика.",
         "author": {"@type": "Person", "@id": SITE + "/#person",
                    "name": "Шаканукова Лариса Тольбиевна"},
         "blogPost": [{"@type": "BlogPosting", "headline": p["title"], "url": p["url"],
                       "datePublished": p["published"], "description": p["description"]}
                      for p in posts]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Блог", "item": url}]},
    ]})


def latest_posts_html(posts, limit=4):
    out = []
    for p in posts[:limit]:
        out.append(f'        <a class="post" href="blog/{p["file"]}">\n'
                   f'          <span class="post__title">{p["title"]}</span>'
                   f'<span class="post__cue">Читать →</span>\n        </a>')
    return "\n".join(out)


# ---------------------------------------------------------------- общие части

def shared_regions(path, text, nav_key, cta_target, root=None):
    root = rel_root(path) if root is None else root
    nav = "\n".join(
        f'      <a class="nav__link" href="{href(root, target)}"'
        + (' aria-current="page"' if key == nav_key else "") + f">{label}</a>"
        for key, label, target in NAV)
    footer_nav = "\n".join(
        f'          <a href="{href(root, target)}">{label}</a>' for _, label, target in NAV)
    rules = "#rules" if path == "services.html" else root + "services.html#rules"
    cta = cta_target or root + "contacts.html"

    text = replace_region(text, "head", partial("head.html", root=root), path)
    text = replace_region(text, "header", partial(
        "header.html", root=root, home=href(root, ""), nav=nav, cta=cta), path)
    text = replace_region(text, "footer", partial(
        "footer.html", root=root, footer_nav=footer_nav, rules=rules, cta=cta), path)
    return text


def sitemap(posts):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, cfg in PAGES.items():
        if not cfg["sitemap"]:
            continue
        priority, freq = cfg["sitemap"]
        out += ["  <url>", f"    <loc>{url_of(path)}</loc>",
                f"    <changefreq>{freq}</changefreq>", f"    <priority>{priority}</priority>",
                "  </url>"]
    for p in posts:
        out += ["  <url>", f"    <loc>{p['url']}</loc>", f"    <lastmod>{p['modified'][:10]}</lastmod>",
                "    <changefreq>yearly</changefreq>", "    <priority>0.6</priority>", "  </url>"]
    out.append("</urlset>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- сборка

def build(check=False):
    posts = load_posts()
    results = {}

    for path, cfg in PAGES.items():
        file = ROOT / path
        if not file.exists():
            raise SystemExit(f"нет файла {path} — уберите его из PAGES или создайте")
        text = file.read_text(encoding="utf-8")
        new = shared_regions(path, text, cfg["nav"], cfg.get("cta"), cfg.get("root"))
        if path == "index.html":
            new = replace_region(new, "latest-posts", latest_posts_html(posts), path)
        if path == "blog/index.html":
            new = replace_region(new, "posts", blog_entries_html(posts), path)
            new = replace_region(new, "blog-ld", blog_ld(posts), path)
        results[file] = (text, new)

    for i, p in enumerate(posts):
        file = ROOT / p["path"]
        text = file.read_text(encoding="utf-8")
        new = shared_regions(p["path"], text, None, None)
        new = replace_region(new, "post-meta", post_meta_html(p), p["path"])
        new = replace_region(new, "post-nav", post_nav_html(posts, i), p["path"])
        new = replace_region(new, "post-ld", post_ld(p), p["path"])
        results[file] = (text, new)

    sm = ROOT / "sitemap.xml"
    results[sm] = (sm.read_text(encoding="utf-8") if sm.exists() else "", sitemap(posts))

    changed = [f for f, (old, new) in results.items() if old != new]
    if check:
        for f in changed:
            print("не собрано:", f.relative_to(ROOT))
        print("всё собрано" if not changed else f"нужно пересобрать: {len(changed)}")
        return 1 if changed else 0

    for f in changed:
        f.write_text(results[f][1], encoding="utf-8")
        print("обновлён:", f.relative_to(ROOT))
    print(f"готово: страниц {len(PAGES)}, статей {len(posts)}, изменено файлов {len(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(build(check="--check" in sys.argv))
