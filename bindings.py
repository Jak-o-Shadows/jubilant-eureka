
import lxml.etree

from generated_bindings import *

class File:
    """
    Represents a parsed XML file, providing access to its root-level components and entities.
    """
    def __init__(self, filepath: str):
        self._element = lxml.etree.parse(filepath).getroot()

        entity_tag_name = "entitytag"
        self.entities = [Entity(elem) for elem in self._element.findall(entity_tag_name)]
        self.root_datadefs= [DATA_TAG_TO_CLASS_MAP[elem.tag](elem) for elem in self._element.iterchildren() if elem.tag != entity_tag_name]
