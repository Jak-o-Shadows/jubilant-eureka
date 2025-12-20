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
        "xs:boolean": "bool",
    }
    return type_map.get(xsd_type, "str")  # Default to string for unknown types


def map_xsd_to_matlab_caster(xsd_type: str) -> str:
    """Maps XSD simple types to MATLAB casting functions."""
    type_map = {
        "xs:string": "string",
        "xs:integer": "str2double",
        "xs:decimal": "str2double",
        "xs:boolean": "logical",
    }
    return type_map.get(xsd_type, "string")  # Default to string


if __name__ == "__main__":
    filepath_schema = "generated_schema.xsd"
    output_file = "generated_bindings.py"
    template_dir = "."
    template_name = "codegen.py.j2"

    print(f"Parsing schema '{filepath_schema}'...")
    # Use xmlschema as it understands schema features better than lxml
    schema = xmlschema.XMLSchema11(filepath_schema)

    data_definitions = []
    component_definitions = []

    # --- Data elements (complex types that are not containers like root/entity/component)
    print("Processing data definitions...")
    for name, xsd_element in schema.elements.items():
        if not xsd_element.type.is_complex() or name in ["root", "entitytag", "component"]:
            continue

        definition = {
            "class_name": to_class_name(name),
            "tag_name": name,
            "simple_members": [],
            "sub_components": [],
        }

        if hasattr(xsd_element.type, "content") and hasattr(xsd_element.type.content, "iter_elements"):
            for child_elem in xsd_element.type.content.iter_elements():
                # Preserve multiplicity info to allow generating lists later
                min_occurs = getattr(child_elem, "min_occurs", 1)
                max_occurs = getattr(child_elem, "max_occurs", 1)

                if child_elem.ref:
                    definition["sub_components"].append({
                        "prop_name": to_snake_case(child_elem.name),
                        "class_name": to_class_name(child_elem.name),
                        "tag_name": child_elem.name,
                        "min_occurs": min_occurs,
                        "max_occurs": max_occurs,
                    })
                else:
                    definition["simple_members"].append({
                        "prop_name": to_snake_case(child_elem.name),
                        "py_type": map_xsd_to_python_type(child_elem.type.prefixed_name),
                        "matlab_caster": map_xsd_to_matlab_caster(child_elem.type.prefixed_name),
                        "tag_name": child_elem.name,
                        "min_occurs": min_occurs,
                        "max_occurs": max_occurs,
                    })

        data_definitions.append(definition)
    print(f"Found {len(data_definitions)} data definitions.")

    # --- Component variants (the <component> element uses alternatives)
    print("Processing component definitions...")
    for name, xsd_element in schema.elements.items():
        if name != "component":
            continue
        component_element = xsd_element
        for alt in component_element.alternatives:
            comp_type = alt.type.name
            # Extract the variant name from the test string like "@type = 'comp1'"
            variant_name = comp_type.split("_")[1]  # crude extraction, may not work forever. Should be able to get it from the `test`

            definition = {
                "class_name": to_class_name(f"component_{variant_name}"),
                "variant": variant_name,
                # Component payload uses data element refs or simple children
                "simple_members": [],
                "sub_components": [],
            }

            if hasattr(comp_type, "content") and hasattr(comp_type.content, "iter_elements"):
                for child_elem in comp_type.content.iter_elements():
                    min_occurs = getattr(child_elem, "min_occurs", 1)
                    max_occurs = getattr(child_elem, "max_occurs", 1)

                    if child_elem.ref:
                        definition["sub_components"].append({
                            "prop_name": to_snake_case(child_elem.name),
                            "class_name": to_class_name(child_elem.name),
                            "tag_name": child_elem.name,
                            "min_occurs": min_occurs,
                            "max_occurs": max_occurs,
                        })
                    else:
                        definition["simple_members"].append({
                            "prop_name": to_snake_case(child_elem.name),
                            "py_type": map_xsd_to_python_type(child_elem.type.prefixed_name),
                            "matlab_caster": map_xsd_to_matlab_caster(child_elem.type.prefixed_name),
                            "tag_name": child_elem.name,
                            "min_occurs": min_occurs,
                            "max_occurs": max_occurs,
                        })

            component_definitions.append(definition)
    print(f"Found {len(component_definitions)} component definitions.")

    # --- Entity metadata (for <entitytag> special handling)
    entity_info = None
    entity_element = schema.elements.get("entitytag")
    if entity_element and getattr(entity_element, "alternatives", None):
        simple_children = set()
        component_max_unbounded = False

        for alt in entity_element.alternatives:
            alt_type = alt.type
            if hasattr(alt_type, "content") and hasattr(alt_type.content, "iter_elements"):
                for child_elem in alt_type.content.iter_elements():
                    # If the child is a reference to "component", treat specially
                    if child_elem.ref and child_elem.name == "component":
                        if getattr(child_elem, "max_occurs", 1) == xmlschema.helpers.UNBOUNDED or getattr(child_elem, "max_occurs", 1) == "unbounded":
                            component_max_unbounded = True
                    else:
                        simple_children.add(child_elem.name)

        entity_info = {
            "class_name": to_class_name("entitytag"),
            "tag_name": "entitytag",
            "simple_children": sorted(simple_children),
            "components_unbounded": component_max_unbounded,
        }

    # Create the simple type map for the template (simple elements -> Python type)
    simple_type_map = {}
    for name, xsd_element in schema.elements.items():
        if not xsd_element.type.is_complex():
            simple_type_map[name] = map_xsd_to_python_type(xsd_element.type.prefixed_name)

    """
    # ------------------------------------------------------------------
    # Fallback: xmlschema may not populate element.alternatives in some
    # versions or with certain schema constructs. If we didn't find any
    # component definitions above, try scanning the declared types for
    # component_*_type entries and build component definitions from those.
    # ------------------------------------------------------------------
    if not component_definitions:
        for type_name, xsd_type in schema.types.items():
            # Look for types named like 'component_comp1_type'
            if isinstance(type_name, str) and type_name.startswith("component_") and type_name.endswith("_type"):
                # Extract variant name between 'component_' and '_type'
                variant = type_name[len("component_"):-len("_type")]
                comp_type = xsd_type
                definition = {
                    "class_name": to_class_name(f"component_{variant}"),
                    "variant": variant,
                    "simple_members": [],
                    "sub_components": [],
                }

                if hasattr(comp_type, "content") and hasattr(comp_type.content, "iter_elements"):
                    for child_elem in comp_type.content.iter_elements():
                        min_occurs = getattr(child_elem, "min_occurs", 1)
                        max_occurs = getattr(child_elem, "max_occurs", 1)
                        if child_elem.ref:
                            definition["sub_components"].append({
                                "prop_name": to_snake_case(child_elem.name),
                                "class_name": to_class_name(child_elem.name),
                                "tag_name": child_elem.name,
                                "min_occurs": min_occurs,
                                "max_occurs": max_occurs,
                            })
                        else:
                            definition["simple_members"].append({
                                "prop_name": to_snake_case(child_elem.name),
                                "py_type": map_xsd_to_python_type(child_elem.type.prefixed_name),
                                "matlab_caster": map_xsd_to_matlab_caster(child_elem.type.prefixed_name),
                                "tag_name": child_elem.name,
                                "min_occurs": min_occurs,
                                "max_occurs": max_occurs,
                            })

                component_definitions.append(definition)

    # If entity_info was not populated from element.alternatives, try a
    # similar fallback: scan types named 'entity_*_type' for simple children
    if entity_info is None:
        simple_children = set()
        component_max_unbounded = False
        for type_name, xsd_type in schema.types.items():
            if isinstance(type_name, str) and type_name.startswith("entity_") and type_name.endswith("_type"):
                if hasattr(xsd_type, "content") and hasattr(xsd_type.content, "iter_elements"):
                    for child_elem in xsd_type.content.iter_elements():
                        if child_elem.ref and child_elem.name == "component":
                            if getattr(child_elem, "max_occurs", 1) == xmlschema.helpers.UNBOUNDED or getattr(child_elem, "max_occurs", 1) == "unbounded":
                                component_max_unbounded = True
                        elif not child_elem.ref:
                            # Only add truly simple (non-referenced) elements
                            simple_children.add(child_elem.name)

        if simple_children or component_max_unbounded:
            entity_info = {
                "class_name": to_class_name("entitytag"),
                "tag_name": "entitytag",
                "simple_children": sorted(simple_children),
                "components_unbounded": component_max_unbounded,
            }
    """
    # Set up Jinja2 environment and render the template
    env = Environment(loader=FileSystemLoader(str(template_dir)), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(template_name)
    generated_code = template.render(
        data_definitions=data_definitions,
        component_definitions=component_definitions,
        entity=entity_info,
        simple_type_map=simple_type_map,
    )

    # Write the generated code to the output file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(generated_code)

    print(f"Code generation complete. Bindings saved to '{output_file}'.")

    # --- MATLAB Binding Generation (left intact for now) ---
    print("\nGenerating MATLAB bindings...")
    matlab_output_file = "bindings.m"
    matlab_template_name = "codegen.m.j2"

    # Reuse component_definitions for the matlab list
    component_names = [f"'{c['variant']}'" for c in component_definitions]

    matlab_template = env.get_template(matlab_template_name)
    matlab_generated_code = matlab_template.render(
        components=component_definitions,
        component_names=f"{{{', '.join(component_names)}}}"
    )

    with open(matlab_output_file, "w", encoding="utf-8") as f:
        f.write(matlab_generated_code)

    print(f"MATLAB code generation complete. Bindings saved to '{matlab_output_file}'.")
