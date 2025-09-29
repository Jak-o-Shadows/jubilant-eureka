import pytest
import lxml
import lxml.etree

import binding_util
import generated_bindings as gb


@pytest.fixture(scope="module")
def xml_root():
    """A pytest fixture that parses the XML file once for all tests."""
    try:
        return lxml.etree.parse("file.xml").getroot()
    except FileNotFoundError:
        pytest.fail("file.xml not found. Please ensure it is in the correct directory.")
    except lxml.etree.XMLSyntaxError as e:
        pytest.fail(f"XML syntax error in file.xml: {e}")


class TestComponentBindings:
    """
    A test suite for the generated lxml-backed data binding classes.
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
        Tests that properties for sub-components return a correctly wrapped instance.
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
        file_loader = binding_util.File("file.xml")

        # 1. Test entity loading
        entities = file_loader.entities
        assert len(entities) == 3, "Should find 3 entitytag elements"
        assert all(isinstance(e, binding_util.Entity) for e in entities)

        # 2. Test dynamic access to a component within an entity
        first_entity = entities[0]
        btag_component = first_entity.btag # Dynamic access via __getattr__
        assert isinstance(btag_component, gb.Btag)
        assert btag_component.value1 == 3.2

        # 3. Test dynamic access to a simple value within an entity
        assert first_entity.prefab == "asdfaf"
        assert first_entity.blah == 3.0

        # 3. Test root component loading
        root_components = file_loader.root_components
        assert len(root_components) == 1
        assert isinstance(root_components[0], gb.Ztag)
        assert root_components[0].vv33 == 33
