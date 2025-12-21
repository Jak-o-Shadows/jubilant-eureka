import pytest
import lxml
import lxml.etree

import binding_util
import bindings as gb


@pytest.fixture(scope="module")
def xml_root():
    """A pytest fixture that parses the XML file once for all tests."""
    try:
        return lxml.etree.parse("file.xml").getroot()
    except FileNotFoundError:
        pytest.fail("file.xml not found. Please ensure it is in the correct directory.")
    except lxml.etree.XMLSyntaxError as e:
        pytest.fail(f"XML syntax error in file.xml: {e}")


class TestCachedPropertyDecorator:
    """
    Unit tests for the `cached_property` decorator in isolation.
    """

    def test_setting_before_getting(self):
        """Tests that setting a value before the first get works correctly."""
        class MyClass:
            def __init__(self):
                self._value = 10

            @binding_util.cached_property
            def prop(self):
                return self._value

            @prop.setter
            def prop(self, value):
                self._value = value

        instance = MyClass()
        instance.prop = 20  # Set before any get
        assert instance.prop == 20

    def test_caching_none_value(self):
        """Tests that a return value of None is correctly cached."""
        class CallCounter:
            def __init__(self):
                self.calls = 0
                self._value = None

            @binding_util.cached_property
            def prop(self):
                self.calls += 1
                return self._value

        instance = CallCounter()
        assert instance.prop is None  # First call, should compute
        assert instance.calls == 1
        assert instance.prop is None  # Second call, should be cached
        assert instance.calls == 1, "Getter was called again for a cached None value."

    def test_read_only_property(self):
        """Tests that setting a property without a setter raises AttributeError."""
        class MyClass:
            @binding_util.cached_property
            def read_only_prop(self):
                return "you can't change me"

        instance = MyClass()
        with pytest.raises(AttributeError, match="can't set attribute 'read_only_prop'"):
            instance.read_only_prop = "new value"

    def test_instance_isolation(self):
        """Tests that caches are isolated between different instances."""
        class MyClass:
            def __init__(self, initial_value):
                self._value = initial_value

            @binding_util.cached_property
            def prop(self):
                return self._value

        instance1 = MyClass(1)
        instance2 = MyClass(2)
        assert instance1.prop == 1
        assert instance2.prop == 2

    def test_set_invalidates_and_recaches(self):
        """Tests that setting a value invalidates the cache, and the next get re-caches."""
        class CallCounter:
            def __init__(self):
                self.calls = 0
                self._value = 100

            @binding_util.cached_property
            def prop(self):
                self.calls += 1
                return self._value

            @prop.setter
            def prop(self, value):
                self._value = value

        instance = CallCounter()

        # First get: should compute and cache
        assert instance.prop == 100
        assert instance.calls == 1

        # Set: should invalidate the cache
        instance.prop = 200

        # Second get: should re-compute and re-cache the new value
        assert instance.prop == 200
        assert instance.calls == 2, "Getter was not called again after setting the value."

        # Third get: should use the new cache
        assert instance.prop == 200
        assert instance.calls == 2, "Getter was called again on a re-cached value."


class TestDatadefBindings:
    """
    A test suite for the generated lxml-backed data binding classes. This is for the datadefs
    """

    def test_simple_getters(self, xml_root):
        """
        Tests that getters correctly read and parse values from the XML.
        """
        # Find the first <btag> element in the document
        btag_element = xml_root.find(".//btag[@type='b']")
        assert btag_element is not None, "Could not find the first <btag> element."

        # Wrap the lxml element with our generated class
        btag_instance = gb.Btag(btag_element)

        # Assert that the properties return the correct, parsed values
        assert btag_instance.value1 == 3.2
        assert btag_instance.value2 == 'text'
        assert btag_instance.value3 == 3

    def test_simple_setters(self, xml_root):
        """
        Tests that setters correctly update the text of the underlying XML element.
        """
        # Find the first <ctag> element
        ctag_element = xml_root.find(".//ctag[@type='c']")
        assert ctag_element is not None, "Could not find the first <ctag> element."

        # Wrap it and test the setter
        ctag_instance = gb.Ctag(ctag_element)

        # Set a new value using the property setter
        new_value = 999
        ctag_instance.value1 = new_value

        # Verify that the underlying XML element's text was changed
        assert ctag_element.find("value1").text == str(new_value)

    def test_sub_component_accessor(self, xml_root):
        """
        Tests that properties for sub-data-defs return a correctly wrapped instance.
        """
        # Find the <dtag> which contains a sub-component
        dtag_element = xml_root.find(".//dtag[@type='d']")
        assert dtag_element is not None, "Could not find the <dtag> element."

        dtag_instance = gb.Dtag(dtag_element)

        # Access the sub-component property
        etag_instance = dtag_instance.etag

        # Assert that we got an instance of the correct binding class
        assert etag_instance is not None
        assert etag_instance.__class__.__name__ == 'Etag'

        # Assert that we can read a value from the sub-component
        assert etag_instance.value1 == 'asdf'
        assert etag_instance.value2 == 5.5

    def test_cached_property_behavior(self, xml_root):
        """
        Verifies that the @cached_property decorator works as expected:
        1. The value is cached after the first read.
        2. The cache is invalidated upon setting a new value.
        """
        btag_element = xml_root.find(".//btag[@type='b']")
        btag_instance = gb.Btag(btag_element)

        # 1. Test that the value is cached
        original_value = btag_instance.value1
        assert original_value == 3.2

        # Manually change the XML text *without* using the setter
        btag_element.find("value1").text = "99.9"

        # Access the property again. It should return the *cached* original value.
        assert btag_instance.value1 == original_value, "Getter did not return cached value."

        # 2. Test that the setter invalidates the cache
        new_value = 123.45
        btag_instance.value1 = new_value

        # Access the property again. It should now return the new value.
        assert btag_instance.value1 == new_value, "Setter did not invalidate the cache."


class TestFileLoader:
    """
    Tests for the top-level File class that loads and provides access to the XML content.
    """

    def test_load_entities_and_components(self):
        """
        Tests that the File class correctly loads entities and root-level components.
        """
        # Use the File class as the main entry point
        file_loader = gb.File("file.xml")

        # 1. Test entity loading
        entities = file_loader.entities
        assert len(entities) == 3, "Should find 3 entitytag elements"
        assert all(isinstance(e, gb.Entity) for e in entities)

        # 2. Test dynamic access to a component within an entity
        first_entity = entities[0]
        # The first entity has a `comp1` component, which has btag and ctag datadefs
        comp1_component = first_entity.comp1 # Dynamic access via __getattr__
        assert isinstance(comp1_component, gb.ComponentComp1)
        btag_datadef = comp1_component.btag
        assert isinstance(btag_datadef, gb.Btag)
        assert btag_datadef.value1 == 3.2
        assert btag_datadef.value2 == "text"
        assert btag_datadef.value3 == 3

        # 3. Test dynamic access to a simple value within an entity
        assert first_entity.prefab == "asdfaf"
        assert first_entity.blah == 3.0

        # 3. Test root component loading
        root_datadefs = file_loader.root_datadefs
        assert len(root_datadefs) == 1
        assert isinstance(root_datadefs[0], gb.Ztag)
        assert root_datadefs[0].vv33 == 33
