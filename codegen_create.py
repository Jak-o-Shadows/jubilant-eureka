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
            "child_datadefs": [],
        }

        if hasattr(xsd_element.type, "content") and hasattr(xsd_element.type.content, "iter_elements"):
            for child_elem in xsd_element.type.content.iter_elements():
                # Preserve multiplicity info to allow generating lists later
                min_occurs = getattr(child_elem, "min_occurs", 1)
                max_occurs = getattr(child_elem, "max_occurs", 1)

                if child_elem.ref:
                    definition["child_datadefs"].append({
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
        print(component_element)
        for alt in component_element.alternatives:
            component_xml_type = alt.type.name
            if component_xml_type is None:
                continue  # Skip - makes the type chcker happy
            component_type = alt.elem.attrib["test"].split("'")[1]  # crude extraction from test attribute
            print(f"Processing component type: {component_type} ({component_xml_type})")

            definition = {
                "class_name": to_class_name(f"component_{component_type}"),
                "variant": component_type,
                # Component payload uses data element refs - no sinmple children
                "child_datadefs": [],
            }

            # Hence get the XML type definition for this alternative
            component_variant = schema.types.get(component_xml_type)
            #print(component_variant)

            if hasattr(component_variant, "content"):
                if  hasattr(component_variant.content, "iter_elements"):
                    #print("has content")
                    for child_elem in component_variant.content.iter_elements():
                        min_occurs = getattr(child_elem, "min_occurs", 1)
                        max_occurs = getattr(child_elem, "max_occurs", 1)
                        #print(child_elem.name)

                        if child_elem.ref:
                            definition["child_datadefs"].append({
                                "prop_name": to_snake_case(child_elem.name),
                                "class_name": to_class_name(child_elem.name),
                                "tag_name": child_elem.name,
                                "min_occurs": min_occurs,
                                "max_occurs": max_occurs,
                            })
                        else:
                            # This is a simple child? But it shouldn't be
                            # TODO: Add warning message
                            pass

            print(f"Adding component definition for variant '{component_type}'")
            component_definitions.append(definition)

    print(f"Found {len(component_definitions)} component definitions.")

    # --- Entity metadata (for <entitytag> special handling)
    print("########### Processing entity definition... ##########")
    entity_info = None
    for name, xsd_element in schema.elements.items():
        if name != "entitytag":
            continue
        entity_element = xsd_element
        entity_info = {
                "class_name": to_class_name(f"entity_{entity_element.name}"),
                "tag_name": "entitytag",
                "simple_members": {},  # This is a dict, because we have multipel entity variants, could get duplicates
            }
        for alt in entity_element.alternatives:
            print(alt)
            entity_xml_type = alt.type.name
            entity_type = alt.elem.attrib["test"].split("'")[1]  # crude extraction from test attribute
            print(f"Processing entity type: {entity_type} ({entity_xml_type})")



            entity_variant = schema.types.get(entity_xml_type)

            if hasattr(entity_variant, "content"):
                if  hasattr(entity_variant.content, "iter_elements"):
                    for child_elem in entity_variant.content.iter_elements():
                        print(child_elem.name, child_elem.ref)
                        if child_elem.name == "component":
                            # It's a component reference - ignore, as those are handled dynamically
                            print(f"Ignoring 'component' child element in entity definition: {child_elem.ref}")
                            pass
                        else:
                            # Preserve multiplicity info to allow generating lists later
                            min_occurs = getattr(child_elem, "min_occurs", 1)
                            max_occurs = getattr(child_elem, "max_occurs", 1)

                            if child_elem.ref:
                                definition["child_datadefs"].append({
                                    "prop_name": to_snake_case(child_elem.name),
                                    "class_name": to_class_name(child_elem.name),
                                    "tag_name": child_elem.name,
                                    "min_occurs": min_occurs,
                                    "max_occurs": max_occurs,
                                })
                            else:
                                entity_info["simple_members"][child_elem.name] = {
                                    "prop_name": to_snake_case(child_elem.name),
                                    "py_type": map_xsd_to_python_type(child_elem.type.prefixed_name),
                                    "matlab_caster": map_xsd_to_matlab_caster(child_elem.type.prefixed_name),
                                    "tag_name": child_elem.name,
                                    "min_occurs": min_occurs,
                                    "max_occurs": max_occurs,
                                }

    print(f"Found {entity_info} entity type definitions")

    # Create the simple type map for the template (simple elements -> Python type)
    simple_type_map = {}
    for name, xsd_element in schema.elements.items():
        if not xsd_element.type.is_complex():
            simple_type_map[name] = map_xsd_to_python_type(xsd_element.type.prefixed_name)

    
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
