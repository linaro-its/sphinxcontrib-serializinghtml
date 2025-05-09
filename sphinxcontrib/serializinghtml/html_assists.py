from bs4 import BeautifulSoup, element
import sys
from html import escape

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
                "type": "expandable-link-group",
                "text": parent_entry.contents[0].contents[0],
                "href": clean_href(parent_entry.contents[0]["href"]),
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

def process_section(result, child, section, pending_divider) -> bool:
    if section != []:
                # Yes, there is, so we have a sub-section. If we've got some content
                # already, add a divider.
        if result != []:
            result.append({ "type": "divider" })
                # Now append the current page and the section links. The
                # ul tag is the only child returned, hence [0]
        result.append(section_links(child, section[0]))
                # If there are any "normal" entries after this section
                # add a divider first
        pending_divider = True
    else:
        if pending_divider:
            result.append({ "type": "divider" })
            pending_divider = False
        result.append(convert_tag_to_link(child))
    return pending_divider

def process_ul_children(result, ul):
    pending_divider = False
    for child in ul.children:
        if type(child) is element.Tag and child.name == "li":
            # Is there a new unordered list within this section?
            section = child.find_all("ul", limit=1)
            pending_divider = process_section(result, child, section, pending_divider)

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

def escape_encoded_pre_text(html: str) -> str:
    edited = False
    soup = BeautifulSoup(html, "html.parser")
    spans = soup.find_all('span', class_="pre")
    for span in spans:
        # At this point, Beautiful Soup has done what a browser does - decode
        # any encoded attributes. So we need to re-encode the string, see if
        # there are any ampersands and, if so, re-encode them again.
        interim = escape(span.string)
        if interim.find("&") != -1:
            span.string = escape(interim)
            edited = True

    if edited:
        html = str(soup)
    return html

def rewrite_hub_links(html: str, link_mappings: dict) -> str:
    edited = False
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all('a')
    for link in links:
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
                edited = True
                break

    if edited:
        html = str(soup)
    return html
