import os
from pathlib import Path

import xmlschema
from jinja2 import Environment, FileSystemLoader


def to_snake_case(name: str) -> str:
    """Converts a name to snake_case."""
    return name.replace("-", "_")


def to_class_name(tag_name: str) -> str:
    """Converts a tag_name like 'my-tag' to a Python ClassName 'MyTag'."""
    return "".join(part.capitalize() for part in tag_name.split('_'))


def map_xsd_to_python_type(xsd_type: str) -> str:
    """Maps XSD simple types to Python types."""
    type_map = {
        "xs:string": "str",
        "xs:integer": "int",
        "xs:decimal": "float",
    }
    return type_map.get(xsd_type, "str")  # Default to string for unknown types


if __name__ == "__main__":
    filepath_schema = "generated_schema.xsd"
    output_file = "generated_bindings.py"
    template_dir = "."
    template_name = "codegen.py.j2"

    print(f"Parsing schema '{filepath_schema}'...")
    # Use xmlschema to schema, as it is more schema-feature aware than lxml
    schema = xmlschema.XMLSchema11(filepath_schema)
    
    component_definitions = []
    
    # Iterate through all global elements defined in the schema
    for name, xsd_element in schema.elements.items():
        # We are interested in components, which are complex types but not the root.
        # We will handle 'entitytag' specially.
        if not xsd_element.type.is_complex() or name == 'root' or name == 'entitytag':
            continue

        definition = {
            "class_name": to_class_name(name),
            "tag_name": name,
            "simple_members": [],
            "sub_components": [],
        }

        # Process child elements from the <xs:sequence>
        if hasattr(xsd_element.type, 'content') and hasattr(xsd_element.type.content, 'iter_elements'):
            for child_elem in xsd_element.type.content.iter_elements():
                if child_elem.ref: # It's a sub-component, e.g. <xs:element ref="etag"/>
                    definition["sub_components"].append({
                        "prop_name": to_snake_case(child_elem.name),
                        "class_name": to_class_name(child_elem.name),
                        "tag_name": child_elem.name,
                    })
                else: # It's a simple member, e.g. <xs:element name="value1" type="xs:string"/>
                    definition["simple_members"].append({
                        "prop_name": to_snake_case(child_elem.name),
                        "py_type": map_xsd_to_python_type(child_elem.type.prefixed_name),
                        "tag_name": child_elem.name,
                    })
        
        component_definitions.append(definition)

    # Create the simple type map for the template
    simple_type_map = {}
    for name, xsd_element in schema.elements.items():
        if not xsd_element.type.is_complex():
            # The value is the Python type name as a string, e.g., "str", "int"
            simple_type_map[name] = map_xsd_to_python_type(xsd_element.type.prefixed_name)

    # Set up Jinja2 environment and render the template
    env = Environment(loader=FileSystemLoader(str(template_dir)), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(template_name)
    generated_code = template.render(
        components=component_definitions,
        # Pass the pre-processed map to the template
        simple_type_map=simple_type_map
    )

    # Write the generated code to the output file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(generated_code)

    print(f"Code generation complete. Bindings saved to '{output_file}'.")
