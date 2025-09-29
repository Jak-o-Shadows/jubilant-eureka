import os

import lxml
import lxml.etree
from jinja2 import Environment, FileSystemLoader
from collections import defaultdict


def infer_data_type(value):
    """Infers the XSD data type from a string value."""
    if value is None:
        return "xs:string"  # Default for empty elements
    
    value = value.strip()
    if not value:
        return "xs:string"

    try:
        int(value)
        return "xs:integer"
    except ValueError:
        pass

    try:
        float(value)
        return "xs:decimal"
    except ValueError:
        pass

    return "xs:string"

def infer_ecs_type(element):
    """Infer what ECS type this element is

    If it has a type, and children, it is an component
    """
    if element.attrib.get("type"):
        if element.tag == "entitytag":
            ecs_type = "entity"
        else:
            ecs_type = "component"
    else:
        ecs_type = "value"
    return ecs_type


def get_element_type_name(element):
    """Creates a unique type name from tag and 'type' attribute if it exists."""
    tag = element.tag
    type_attr = element.attrib.get("type")
    if type_attr:
        # Sanitize attribute value for use in a type name
        safe_type_attr = "".join(c if c.isalnum() else '_' for c in type_attr)
        return f"{tag}_{safe_type_attr}_type"
    return f"{tag}Type"


def analyze_element(element, entities, components, flat):
    """
    Analyzes an XML element and recursively analyzes its children to build schema definitions.
    """
    current_type_name = get_element_type_name(element)

    # If we have already processed this exact type, we can skip it.
    if current_type_name in entities or current_type_name in components or current_type_name in flat:
        return

    # Determine what type this element is
    ecs_type = infer_ecs_type(element)
    match ecs_type:
        case "entity":
            # Entities can contain any of the components. Because of this, pretty damn hard
            #   to provide a schema for them
            pass
        case "component":
            # As a component, must look at it's children. They can be components or values
            #   The component is defined in the XSD, with any child components defined
            #   separately in the xsd
            definition = {
                "name": element.tag,
                "absolute_name": current_type_name,
                "ecs_type": element.attrib.get("type"),
                "members": [],
                "children": []
            }
            for child in element:
                if infer_ecs_type(child) == "component":
                    definition["children"].append({
                        "name": child.tag,
                        "type": get_element_type_name(child)
                    })
                else:  # It's a value/member field
                    definition['members'].append({
                        "name": child.tag,
                        "type": infer_data_type(child.text)
                    })
            components[current_type_name] = definition
        case "value":
            # Only add them if their parent isn't a component
            # as they will be defined locally within the component's complexType.
            if element.getparent() is not None and infer_ecs_type(element.getparent()) != "component":
                definition = {
                "name": element.tag,
                "absolute_name": current_type_name,
                "type": infer_data_type(element.text)
                }
                flat[current_type_name] = definition

    # After processing the current element, recurse into its children
    # to ensure their definitions are also created.
    for child in element:
        analyze_element(child, entities, components, flat)

            



def generate_schema(xml_file_path, template_dir, template_name):
    """
    Generates an XSD schema from an XML file.

    :param xml_file_path: Path to the input XML file.
    :param template_dir: Directory where the Jinja2 template is located.
    :param template_name: Name of the Jinja2 template file.
    :return: The generated XSD content as a string.
    """
    try:
        parser = lxml.etree.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
        tree = lxml.etree.parse(xml_file_path, parser)
        root = tree.getroot()
    except lxml.etree.XMLSyntaxError as e:
        print(f"Error: Could not parse XML file '{xml_file_path}'.")
        print(f"Details: {e}")
        return None
    except FileNotFoundError:
        print(f"Error: XML file not found at '{xml_file_path}'.")
        return None

    # These dictionaries will hold the definitions for each unique type
    entities = {}
    components = {}
    flat = {}
    # Recurse over the children of the root, as root itself is not defined in the XSD
    for child in root:
        analyze_element(child, entities, components, flat)


    template_context = {
        "root_element": root.tag,
        # Reverse the order to have the innermost appear first, in order to satisfy dependencies
        #   Yes, this relies on dicts being ordered, which they are now
        "entities": list(entities.values())[::-1],
        "components": list(components.values())[::-1],
        "flat": list(flat.values())[::-1]
    }

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(template_name)

    # Render the template
    return template.render(template_context)


if __name__ == '__main__':
    # Configuration
    input_xml = "file.xml"
    output_xsd = "generated_schema.xsd"
    template_folder = "."
    template_file = "schema.xsd.j2"

    print(f"Generating XSD for '{input_xml}'...")

    # Generate the schema content
    xsd_content = generate_schema(input_xml, template_folder, template_file)

    # Write to output file
    if xsd_content:
        with open(output_xsd, 'w', encoding='utf-8') as f:
            f.write(xsd_content)
        print(f"Successfully generated schema and saved to '{output_xsd}'")
