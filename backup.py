#!/usr/bin/env python3

import re
from html.entities import codepoint2name
from os.path import basename
from urllib.parse import urlsplit, urljoin

try:
    import requests
    from bs4 import BeautifulSoup, Comment
    from markdownify import markdownify
except ModuleNotFoundError as err:
    import sys
    from os import execv
    from os.path import exists, expanduser
    VENV = 'cs-backup'
    VENV_PYTHON = expanduser(f'~/.venv/{VENV}/bin/python3')
    if not exists(VENV_PYTHON):
        raise FileNotFoundError(' '.join([
            f'tried load module "{err.name}" with venv "{VENV}"',
            f'but could not find executable {VENV_PYTHON}',
        ]))
    execv(VENV_PYTHON, [VENV_PYTHON, *sys.argv])

ROOT_URL = 'https://www.oxy.edu/computer-science/'
DOMAIN = '://'.join(urlsplit(ROOT_URL)[:2])

KEEP_TAGS = set([
    'img',
])

DELETE_CLASSES = set([
    'element-invisible',
    'breadcrumb',
])

DELETE_UNICODE = set([
    8203, # zero-width space
])

COPY_TAGS = set([
    'table',
])

def get_all_urls():
    urls = [ROOT_URL]
    soup = get_page(ROOT_URL)
    for link in soup.select('ul.menu a'):
        urls.append(urljoin(DOMAIN, link['href']))
    return urls


def get_page(url):
    response = requests.get(url)
    return BeautifulSoup(response.text, 'html.parser')


def get_content(soup):
    content = soup.select('div.main')
    if len(content) == 0:
        content = soup.select('div.main-text')
    content = max(content, key=(lambda soupette: len(soupette.prettify())))
    # replace relative links with absolute links
    for tag in content.find_all('a'):
        if 'href' in tag.attrs and tag['href'].startswith('/') and not tag['href'].startswith('//'):
            tag['href'] = DOMAIN + tag['href']
    # remove special classes
    for delete_class in DELETE_CLASSES:
        for tag in content.select(f'.{delete_class}'):
            tag.decompose()
    # remove spurious container divs
    for div in content.select('div'):
        if len(div.contents) == 1:
            div.replace_with(div.contents[0])
    # remove comments
    for comment in content(text=(lambda text: isinstance(text, Comment))):
        comment.extract()
    # remove all empty tags
    changed = True
    while changed:
        changed = False
        for tag in content.find_all(True):
            should_delete = (
                not any(
                    tag.name == keep_tag or tag.find(keep_tag)
                    for keep_tag in KEEP_TAGS
                )
                and not tag.text.strip()
            )
            if should_delete:
                tag.decompose()
                changed = True
    # use consecutively-sized headings
    headings = []
    for heading in content.select('h1,h2,h3,h4,h5,h6'):
        level = int(heading.name[1])
        orig = level
        while headings and level < headings[-1]:
            headings.pop()
        if not headings or level > headings[-1]:
            headings.append(level)
        heading.name = f'h{len(headings)}'
    # create the overall HTML
    html = '\n'.join(str(child) for child in content.contents)
    # remove blank lines
    html = '\n'.join(line for line in html.splitlines() if line.strip())
    return html


def get_asides(soup):
    return [aside.prettify() for aside in soup.select('aside')]


def html_to_md(html):
    # convert top-level elements individually to remove leading space
    top_elements = []
    for element in BeautifulSoup(html, 'html.parser').contents:
        if element.name in COPY_TAGS:
            top_elements.append('\n'.join([
                4 * re.match('( *)', line).group(1) + line.strip()
                for line in element.prettify().splitlines()
            ]))
        else:
            # convert HTML to markdown
            markdown = markdownify(str(element), heading_style='ATX', bullets='*').strip()
            # remove blank lines
            markdown = '\n'.join(line for line in markdown.splitlines() if line.strip())
            top_elements.append(markdown)
    # combine into single string
    markdown = '\n'.join(top_elements)
    # remove trailing whitespace
    markdown = '\n'.join(line.rstrip() for line in markdown.splitlines())
    # convert tabs to spaces
    markdown = markdown.replace('\t', '    ')
    # remove some Unicode characters
    for codepoint in DELETE_UNICODE:
        markdown = markdown.replace(chr(codepoint), '')
    # convert the other Unicode characters
    for char in set(re.findall('[^ -~\n]', markdown)):
        markdown = markdown.replace(char, f'&#{ord(char)};')
    return markdown


def main():
    for url in get_all_urls():
        soup = get_page(url)
        print(url)
        content = get_content(soup)
        asides = get_asides(soup)
        if url == ROOT_URL:
            slug = 'index'
        else:
            slug = basename(urlsplit(url).path)
        with open(f'html/{slug}.html', 'w') as fd:
            fd.write(content)
        with open(f'md/{slug}.md', 'w') as fd:
            fd.write(html_to_md(content))


if __name__ == '__main__':
    main()
