import functools
import typing

import lxml.etree

# A unique object to act as a sentinel for uncached values.
# This is more robust than using `None` as a sentinel, as `None` could be a valid cached value.
_sentinel = object()

class cached_property:
    """
    A decorator that converts a method into a cached property.
    
    The property's value is computed by the decorated getter method on first access.
    Subsequent accesses return the cached value. The cache is automatically
    invalidated when the property's setter is called.
    
    Usage:
        class MyClass:
            @cached_property
            def my_prop(self):
                # Expensive computation
                return 42
    
            @my_prop.setter
            def my_prop(self, value):
                # Set some internal state
                self._my_prop = value
    """
    
    def __init__(self, fget):
        self.fget = fget
        self.fset = None
        self.cache_attr_name = f'_cached_{fget.__name__}'
        functools.update_wrapper(self, fget)
        
    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        cached_value = getattr(instance, self.cache_attr_name, _sentinel)
        if cached_value is not _sentinel:
            return cached_value
        
        value = self.fget(instance)
        setattr(instance, self.cache_attr_name, value)
        return value
    
    def __set__(self, instance, value):
        if self.fset is None:
            raise AttributeError(f"can't set attribute '{self.fget.__name__}'")
        
        self.fset(instance, value)
        # Invalidate the cache by deleting the cached attribute if it exists.
        if hasattr(instance, self.cache_attr_name):
            delattr(instance, self.cache_attr_name)
            
    def setter(self, fset):
        """Decorator to define the property's setter."""
        self.fset = fset
        return self


import generated_bindings as gb


class Entity:
    def __init__(self, element: lxml.etree._Element):
        self._element = element
        # Dynamically create a new class that inherits from this one.
        # This gives us a unique class for each instance to attach properties to,
        # preventing conflicts while still allowing the property mechanism to work.
        self.__class__ = type(self.__class__.__name__, (self.__class__,), {})
        self._create_dynamic_properties_on_class()

    def _create_dynamic_properties_on_class(self):
        """
        Inspects the entity's children and creates cached_property accessors
        on the instance's unique class for each unique tag.
        """
        # Process unique tags to avoid creating multiple properties for the same tag name
        for child in self._element:
            tag_name = child.tag
            if tag_name in gb.TAG_TO_CLASS_MAP:               
                # Attach the property directly to the instance's __dict__
                setattr(self, tag_name, gb.TAG_TO_CLASS_MAP[tag_name](child))

            elif tag_name in gb.SIMPLE_TYPE_MAP:
                py_type = gb.SIMPLE_TYPE_MAP[tag_name]

                # Use default arguments to capture loop variables for the closures
                def getter(instance, _tag=tag_name, _type=py_type, elem=child):
                    print(elem, _tag, _type)
                    return _type(elem.text) if elem is not None and elem.text is not None else None

                def setter(instance, value, _tag=tag_name, elem=child):
                    print(elem, _tag, value)
                    if elem is not None:
                        elem.text = str(value)

                # Create the cached_property and attach it to the instance's class
                prop = cached_property(getter)
                prop = prop.setter(setter)
                setattr(self.__class__, tag_name, prop)


class File:
    """
    Represents a parsed XML file, providing access to its root-level components and entities.
    """
    def __init__(self, filepath: str):
        self._element = lxml.etree.parse(filepath).getroot()

        entity_tag_name = "entitytag"
        self.entities = [Entity(elem) for elem in self._element.findall(entity_tag_name)]
        self.root_components = [elem for elem in self._element.iterchildren() if elem.tag != entity_tag_name]
