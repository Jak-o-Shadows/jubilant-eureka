"""
Generates Python classes for tcod-ecs components based on an XSD schema.
"""
import xmlschema
from jinja2 import Environment, FileSystemLoader


def to_class_name(tag_name: str) -> str:
    """Converts a tag_name like 'my-tag' to a Python ClassName 'MyTag'."""
    return "".join(part.capitalize() for part in tag_name.split("_"))


def map_xsd_to_python_type(xsd_type: str) -> str:
    """Maps XSD simple types to Python types."""
    type_map = {
        "xs:string": "str",
        "xs:integer": "int",
        "xs:decimal": "float",
        "xs:boolean": "bool",
    }
    return type_map.get(xsd_type, "str")  # Default to string for unknown types


def generate_ecs_components(schema_path: str, template_dir: str, template_name: str, output_path: str):
    """
    Parses an XSD schema and generates tcod-ecs component classes.

    :param schema_path: Path to the input XSD schema file.
    :param template_dir: Directory where the Jinja2 template is located.
    :param template_name: Name of the Jinja2 template file.
    :param output_path: Path to the output Python file.
    """
    print(f"Parsing schema '{schema_path}' to generate ECS components...")
    schema = xmlschema.XMLSchema11(schema_path)

    component_definitions = []

    # Iterate through all global elements defined in the schema
    for name, xsd_element in schema.elements.items():
        # We are interested in elements that represent components.
        # In our schema, these are all top-level elements except 'root' and 'entitytag'.
        if name in ('root', 'entitytag'):
            continue

        definition = {
            "class_name": to_class_name(name),
            "tag_name": name,
            "simple_members": [],
        }

        # Handle simple types like <blah> which have no children
        if xsd_element.type.is_simple():
            definition["simple_members"].append({
                "prop_name": "value",  # A default name for the single value
                "py_type": map_xsd_to_python_type(xsd_element.type.prefixed_name),
            })
        # Handle complex types like <btag>
        elif hasattr(xsd_element.type, 'content') and hasattr(xsd_element.type.content, 'iter_elements'):
            for child_elem in xsd_element.type.content.iter_elements():
                # For ECS, we flatten sub-components. A component should not contain another component object.
                # We'll handle relations during the loading process.
                if child_elem.ref:
                    print(f"Warning: Sub-component reference '{child_elem.name}' in '{name}' is ignored for ECS component generation.")
                    continue
                
                definition["simple_members"].append({
                    "prop_name": child_elem.name,
                    "py_type": map_xsd_to_python_type(child_elem.type.prefixed_name),
                })

        component_definitions.append(definition)

    # Set up Jinja2 environment and render the template
    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(template_name)
    generated_code = template.render(components=component_definitions)

    # Write the generated code to the output file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(generated_code)

    print(f"ECS component generation complete. Components saved to '{output_path}'.")


if __name__ == "__main__":
    # Configuration
    input_schema = "generated_schema.xsd"
    output_py_file = "ecs_components.py"
    template_folder = "."
    template_file = "ecs_components.py.j2"

    generate_ecs_components(input_schema, template_folder, template_file, output_py_file)