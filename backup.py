#!/usr/bin/env python3

import re
from os.path import basename
from urllib.parse import urlsplit, urljoin

import requests
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify
from htmlmin import minify

ROOT_URL = 'https://www.oxy.edu/computer-science/'
DOMAIN = '://'.join(urlsplit(ROOT_URL)[:2])

KEEP_TAGS = set([
    'img',
])

BLOCK_TAGS = set([
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'div',
    'p',
    'ul',
])

DELETE_CLASSES = set([
    'element-invisible',
    'breadcrumb',
    'visible-xs',
    'visible-sm',
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
    return BeautifulSoup(minify(response.text, remove_empty_space=True), 'html.parser')


def get_content(soup):
    content = soup.select('div.main')
    if not content:
        content = soup.select('div.main-text')
    content = max(content, key=(lambda soupette: len(soupette.prettify())))
    # replace relative links with absolute links
    for tag_name, attr in [('a', 'href'), ('img', 'src')]:
        for tag in content.find_all(tag_name):
            if attr in tag.attrs and tag[attr].startswith('/') and not tag[attr].startswith('//'):
                tag[attr] = DOMAIN + tag[attr]
    # remove special classes
    for delete_class in DELETE_CLASSES:
        for tag in content.select(f'.{delete_class}'):
            tag.decompose()
    # remove spurious container divs
    for div in content.find_all('div'):
        should_unwrap = all(
            (not child.name or child.name in BLOCK_TAGS)
            for child in div.contents if child.name
        )
        if should_unwrap:
            div.unwrap()
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
    # fix the first heading
    content.select('h1,h2,h3,h4,h5,h6')[0].name = 'h1'
    # use consecutively-sized headings
    heading_level = 0
    heading_skip = 0
    headings = 6 * [0]
    for child in content.select('*'):
        if not child.name or child.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            continue
        level = int(child.name[1])
        headings[level - 1] = 1
        correct_level = sum(headings[:level])
        headings[level:] = (6 - level) * [0]
        child.name = f'h{correct_level}'
    return content


def get_asides(soup):
    return list(soup.find_all('aside'))


def soup_to_md(soup):
    # convert top-level elements individually to remove leading space
    top_elements = []
    for element in soup.contents:
        if element.name in COPY_TAGS:
            top_elements.append(to_pretty_html(element))
        else:
            # convert HTML to markdown
            markdown = markdownify(str(element), heading_style='ATX', bullets='*').strip()
            # remove blank lines
            markdown = '\n'.join(line.rstrip() for line in markdown.splitlines() if line.strip())
            top_elements.append(markdown.strip())
    # combine into single string
    markdown = '\n\n'.join(top_elements)
    # remove trailing whitespace
    markdown = '\n'.join(line.rstrip() for line in markdown.splitlines())
    # remove consecutive blank lines
    markdown = re.sub('\n\n\n+', '\n\n', markdown)
    # convert tabs to spaces
    markdown = markdown.replace('\t', '    ')
    # remove some Unicode characters
    for codepoint in DELETE_UNICODE:
        markdown = markdown.replace(chr(codepoint), '')
    # convert the other Unicode characters
    for char in set(re.findall('[^ -~\n]', markdown)):
        markdown = markdown.replace(char, f'&#{ord(char)};')
    return markdown.strip()


def to_pretty_html(soup):
    return '\n'.join([
        4 * re.match('( *)', line).group(1) + line.strip()
        for line in soup.prettify().splitlines()
    ])


def main():
    for url in get_all_urls():
        soup = get_page(url)
        print(url)
        content = get_content(soup)
        if url == ROOT_URL:
            slug = 'index'
        else:
            slug = basename(urlsplit(url).path)
        with open(f'html/{slug}.html', 'w') as fd:
            fd.write(to_pretty_html(content))
        with open(f'md/{slug}.md', 'w') as fd:
            fd.write(soup_to_md(content))


if __name__ == '__main__':
    main()
