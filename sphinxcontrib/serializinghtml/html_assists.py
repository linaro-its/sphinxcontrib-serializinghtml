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

    # Start with the unordered list
    ul = soup.ul
    # Iterate through list items
    while ul is not None:
        process_ul_children(result, ul)
        while True:
            ul = ul.next_sibling
            if ul is None or type(ul) is element.Tag:
                break
            # Not an acceptable type - loop and get the next sibling
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

def matched_pre(span) -> bool:
    """ Check if this span is specifying the "pre" class """
    if "class" not in span:
        return False
    classes = span["class"]
    for this_class in classes:
        if this_class == "pre":
            return True
    return False

def escape_encoded_pre_text(html: str) -> str:
    edited = False
    soup = BeautifulSoup(html, "html.parser")
    spans = soup.find_all('span')
    for span in spans:
        if matched_pre(span):
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
