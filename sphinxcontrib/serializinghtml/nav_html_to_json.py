from bs4 import BeautifulSoup, element
import json
import sys

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

def convert_nav_html_to_json(html: str) -> list:
    result = []
    soup = BeautifulSoup(html, "html.parser")

    # Start with the unordered list
    ul = soup.ul
    pending_divider = False
    # Iterate through list items
    while ul is not None:
        for child in ul.children:
            if type(child) is element.Tag and child.name == "li":
                # Is there a new unordered list within this section?
                section = child.find_all("ul", limit=1)
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
        while True:
            ul = ul.next_sibling
            if ul is None or type(ul) is element.Tag:
                break
            # Not an acceptable type - loop and get the next sibling
    return result
