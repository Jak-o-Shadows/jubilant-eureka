"""
Example of loading an XML file into a tcod-ecs world
using the generated component classes.
"""
import typing

import lxml.etree
import tcod.ecs

import ecs_components


def load_world_from_xml(filepath: str) -> tcod.ecs.Registry:
    """
    Parses an XML file and populates a tcod-ecs Registry.

    :param filepath: Path to the XML file.
    :return: A populated tcod-ecs Registry instance.
    """
    try:
        root = lxml.etree.parse(filepath).getroot()
    except (FileNotFoundError, lxml.etree.XMLSyntaxError) as e:
        print(f"Error reading or parsing XML file: {e}")
        return tcod.ecs.Registry()

    registry = tcod.ecs.Registry()

    # Find all <entitytag> elements and create entities from them
    for entity_elem in root.findall("entitytag"):
        entity = registry.new_entity()
        print(f"Created new entity: {entity}")

        # Iterate over the child elements of the entity, which are its components
        for component_elem in entity_elem:
            tag = component_elem.tag
            if tag not in ecs_components.COMPONENT_MAP:
                print(f"Warning: Unknown component tag '{tag}' found in entity. Skipping.")
                continue

            component_class = ecs_components.COMPONENT_MAP[tag]
            
            # Resolve stringified annotations into actual types
            type_hints = typing.get_type_hints(component_class)

            # Prepare constructor arguments from the component's child elements
            kwargs = {}
            if component_class.__match_args__ == ("value",): # Simple component like <blah>
                kwargs["value"] = type_hints["value"](component_elem.text)
            else: # Complex component like <btag>
                for field in component_class.__dataclass_fields__:
                    field_elem = component_elem.find(field)
                    if field_elem is not None and field_elem.text is not None:
                        field_type = type_hints[field]
                        kwargs[field] = field_type(field_elem.text)

            # Add the component instance to the entity
            entity.components[component_class] = component_class(**kwargs)
            print(f"  - Added component: {entity.components[component_class]}")

    return registry

if __name__ == "__main__":
    print("Loading world from file.xml...")
    world_registry = load_world_from_xml("file.xml")
    print("\nWorld loading complete.")

    # Example: Query for all entities that have a Btag component
    print("\nQuerying for entities with Btag component:")
    query = world_registry.Q.all_of(components=[ecs_components.Btag])
    for entity in query:
        print(f"Entity {entity} has Btag: {entity.components[ecs_components.Btag]}")