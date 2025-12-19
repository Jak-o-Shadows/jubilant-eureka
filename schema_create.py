import os

import lxml
import lxml.etree
from jinja2 import Environment, FileSystemLoader
from collections import defaultdict, Counter


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

    If it is an entitytag, it is an entity
    If it is a component, it is a component
    If it has children, it is a container for data
    otherwise, it is a value
    """
    if element.tag == "entitytag":
        return "entity"
    if element.tag == "component":
        return "component"
    if len(element):
        return "datadef"
    return "value"


def get_element_type_name(element):
    """Creates a unique type name from tag and 'type' attribute if it exists."""
    tag = element.tag
    type_attr = element.attrib.get("type")
    if type_attr:
        # Sanitize attribute value for use in a type name
        safe_type_attr = "".join(c if c.isalnum() else '_' for c in type_attr)
        return f"{tag}_{safe_type_attr}_type"
    return f"{tag}Type"


def analyze_element(element, entities, components, datadefs, flat):
    """
    Analyzes an XML element and recursively analyzes its children to build schema definitions.
    """
    current_type_name = get_element_type_name(element)

    # Determine what type this element is
    ecs_type = infer_ecs_type(element)
    if ecs_type != "entity":
        # If we have already processed this exact type, we can skip it.
        #    As entites reuse tags, must always process them
        if current_type_name in entities or current_type_name in components or current_type_name in datadefs or current_type_name in flat:
            return


    match ecs_type:
        case "entity":
            # For xs:alternative, we need to define each unique entity structure as a separate type.
            # We'll create a variant name based on the sorted list of its child tags.
            child_tag_counts = Counter(child.tag for child in element)
            children_defs = []
            for tag, count in child_tag_counts.items():
                max_occurs = "unbounded" if count > 1 else "1"
                children_defs.append({"name": tag, "maxOccurs": max_occurs})

            child_tags = children_defs
            variant_name = element.attrib.get("variant")
            variant_type_name = f"entity_{variant_name}_type"

            # Only define this variant if we haven't seen it before.
            if variant_type_name not in entities:
                entities[variant_type_name] = {
                    "name": element.tag,
                    "variant_name": variant_name,
                    "variant_type_name": variant_type_name,
                    "children": child_tags
                }
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
                child_ecs_type = infer_ecs_type(child)
                if child_ecs_type == "component" or child_ecs_type == "datadef":
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
        case "datadef":
            # This is a data definition, a container for values or other datadefs.
            definition = {
                "name": element.tag,
                "absolute_name": current_type_name,
                "ecs_type": element.attrib.get("type"),
                "members": [],
                "children": []
            }
            for child in element:
                child_ecs_type = infer_ecs_type(child)
                if child_ecs_type == "component" or child_ecs_type == "datadef":
                    definition["children"].append({
                        "name": child.tag,
                        "type": get_element_type_name(child)
                    })
                else:  # It's a value/member field
                    definition['members'].append({
                        "name": child.tag,
                        "type": infer_data_type(child.text)
                    })
            datadefs[current_type_name] = definition
        case "value":
            # Only add them if their parent isn't a component or datadef
            # as they will be defined locally within the component's complexType.
            if element.getparent() is not None:
                parent_ecs_type = infer_ecs_type(element.getparent())
                if parent_ecs_type != "component" and parent_ecs_type != "datadef":
                    definition = {
                    "name": element.tag,
                    "absolute_name": current_type_name,
                    "type": infer_data_type(element.text)
                    }
                    flat[current_type_name] = definition

    # After processing the current element, recurse into its children
    # to ensure their definitions are also created.
    for child in element:
        analyze_element(child, entities, components, datadefs, flat)


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
    datadefs = {}
    flat = {}
    # Recurse over the children of the root, as root itself is not defined in the XSD
    for child in root:
        analyze_element(child, entities, components, datadefs, flat)


    # For the root element's <xs:all>, we only want unique tag names.
    all_defs = list(components.values()) + list(datadefs.values())
    unique_root_refs = list({d['name']: d for d in all_defs}.values())


    template_context = {
        "root_element": root.tag,
        "entity_base_name": "entitytag", # The common tag name for all entities
        # Reverse the order to have the innermost appear first, in order to satisfy dependencies
        #   Yes, this relies on dicts being ordered, which they are now
        "entities": list(entities.values())[::-1],
        "components": list(components.values())[::-1],
        "datadefs": list(datadefs.values())[::-1],
        "root_children_defs": unique_root_refs[::-1],
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
