from bs4 import BeautifulSoup, element
from html import escape
from urllib.parse import urlparse
from pathlib import PurePosixPath

def is_relative_url(url):
    parsed = urlparse(url)
    return not parsed.scheme and not parsed.netloc

def clean_href(href: str) -> str:
    """ Make sure the href doesn't start or end with a / """
    if href[0] == "/":
        href = href[1:]
    if href[-1] == "/":
        href = href[:-1]
    return href

def section_links(parent_entry: element.Tag, list_entry: element.Tag) -> dict:
    section_result = []
    for child in list_entry.children:
        if type(child) is element.Tag and child.name == "li":
            section_result.append(convert_tag_to_link(child))
    return {
                "type": "section",
                "text": parent_entry.contents[0].contents[0],
                "items": section_result
            }

def convert_tag_to_link(item_entry: element.Tag) -> dict:
    # The a tag is a child of the li tag
    a_tag = item_entry.contents[0]
    return {
            "type": "link",
            "text": a_tag.contents[0],
            "href": clean_href(a_tag["href"])
        }

def process_section(result, child, section):
    # Is there a new unordered list within this section?
    if section != []:
        # Only add a starting divider if there is already content
        if result != []:
            result.append({ "type": "divider" })
        # Now append the current page and the section links. The
        # ul tag is the only child returned, hence [0]
        result.append(section_links(child, section[0]))
        result.append({ "type": "divider" })
    else:
        result.append(convert_tag_to_link(child))

def process_ul_children(result, ul):
    for child in ul.children:
        if type(child) is element.Tag and child.name == "li":
            section = child.find_all("ul", limit=1)
            process_section(result, child, section)

def convert_nav_html_to_json(html: str) -> list:
    result = []
    soup = BeautifulSoup(html, "html.parser")
    top_level_tags = soup.find_all(recursive=False)

    caption = None
    for tag in top_level_tags:
        if type(tag) is element.Tag and tag.name == "p" and tag.has_attr("class") and "caption" in tag["class"]:
            span = tag.findChild("span")
            caption = span.text
        elif type(tag) is element.Tag and tag.name == "ul":
            if caption is not None:
                local_result = []
                process_ul_children(local_result, tag)
                result.append({
                    "type": "section-group",
                    "title": caption,
                    "items": local_result
                })
                caption = None
            else:
                process_ul_children(result, tag)
    return result

def escape_encoded_alt_text(html: str) -> str:
    edited = False
    soup = BeautifulSoup(html, "html.parser")
    images = soup.find_all('img')
    for img in images:
        if img['alt'] != "":
            # At this point, Beautiful Soup has done what a browser does - decode
            # any encoded attributes. So we need to re-encode the string, see if
            # there are any ampersands and, if so, re-encode them again.
            interim = escape(img['alt'])
            if interim.find("&") != -1:
                img['alt'] = escape(interim)
                edited = True

    if edited:
        html = str(soup)
    return html

def re_encode_span_tags(span_tags, edited) -> bool:
    for span_tag in span_tags:
        content = span_tag.string
        if content is not None:
            interim = escape(content)
            if interim.find("&") != -1:
                span_tag.string = escape(interim)
                edited = True
    return edited

def escape_encoded_pre_text(html: str) -> str:
    # The reason for this function is because, when the browser loads the
    # HTML from the JSON data, it decodes any encoded attributes, such as
    # &lt; and &gt;, so we need to re-encode them to prevent the browser
    # from decoding them.
    #
    # There are two separate search cases that are implemented here:
    #
    # 1. The <span> tags that are used to format code in the HTML, which
    #    are used in the "pre" tags.
    # 2. The <pre> tags themselves, which may contain code that has been
    #    formatted with HTML entities, such as &lt; and &gt;.

    edited = False
    soup = BeautifulSoup(html, "html.parser")

    span_tags = soup.find_all('span', class_="pre")
    edited = re_encode_span_tags(span_tags, edited)

    pre_tags = soup.find_all('pre')
    for pre_tag in pre_tags:
        span_tags = pre_tag.find_all("span")
        edited = re_encode_span_tags(span_tags, edited)

    if edited:
        html = str(soup)
    return html

def relative_traversal(from_path, to_path):
    from_parts = PurePosixPath(from_path).parts
    to_parts = PurePosixPath(to_path).parts

    # Find common prefix length
    common_length = 0
    for f, t in zip(from_parts, to_parts):
        if f == t:
            common_length += 1
        else:
            break

    # Steps up from 'from_path' to common ancestor
    # Need to reduce the step count by one because of the way
    # Next.js handles routes.
    up_steps = len(from_parts) - common_length - 1
    down_path = to_parts[common_length:]

    result = "../" * up_steps + "/".join(down_path)
    return result

def process_relative_links(link: dict, page_filename: str, page_filename_head: str) -> bool:
    # Check for relative links that need adjusting relative to where
    # we are in the URL structure. Do this *before* performing the link
    # mapping because the latter introduces more relative links to check.
    href_link = link['href']
    print(f"rewrite_hub_links: adjusting relative link: {href_link}")
    if page_filename_head != page_filename:
        if is_relative_url(href_link) and href_link[0] not in ['#', '/']:
            if href_link.startswith(page_filename_head):
                # We need to drop the bit that goes up to the first / in
                # the link because otherwise it gets duplicated when
                # Next.js processes it.
                link['href'] = href_link[len(page_filename_head)+1:]
                print(f"rewrite_hub_links: new relative link: {link['href']}")
                return True
            # If we aren't on the same path, and we don't have any traversal
            # at the start of the path, calculate the traversal required.
            if not href_link.startswith("../"):
                new_path = relative_traversal(page_filename, href_link)
                if new_path != href_link:
                    link['href'] = new_path
                    print(f"rewrite_hub_links: new relative link: {link['href']}")
                    return True
            print("rewrite_hub_links: no change")
    else:
        print("rewrite_hub_links: no relative link adjustment needed")
    return False

def process_link_mappings(link: dict, link_mappings: dict) -> bool:
    for key in link_mappings:
        # Check if the href starts with the key
        if link['href'].startswith(key):
            # We have a match, so strip the key from the href
            link['href'] = link['href'].replace(key, "")
            # We also have to remove ".html" from the end of the link
            link['href'] = link['href'].replace(".html", "")
            # If we're just left with "index", replace it with the value from the dictionary,
            # which will also be the documentation root name
            if link['href'] == "index":
                link['href'] = link_mappings[key]
            # Do we have a link that ENDS with "/index"? If we do, remove it
            if link['href'].endswith("/index"):
                link['href'] = link['href'].replace("/index", "")
            # Now put it all together ...
            # So we should end up with something like:
            # /library/onelab/onelab
            # /library/laa/laa_getting_started
            link['href'] = f"/library/{link_mappings[key]}/{link['href']}"
            return True
    return False

def rewrite_hub_links(html: str, link_mappings: dict, page_filename: str) -> str:
    print(f"rewrite_hub_links: page_filename={page_filename}")
    edited = False
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all('a')
    # Need to calculate what the start of page_filename looks like
    # up to the first separator.
    page_filename_head, _, _ = page_filename.partition("/")
    print(f"rewrite_hub_links: page_filename_head={page_filename_head}")
    for link in links:
        if process_relative_links(link, page_filename, page_filename_head):
            edited = True
        if process_link_mappings(link, link_mappings):
            edited = True

    if edited:
        html = str(soup)
    return html
