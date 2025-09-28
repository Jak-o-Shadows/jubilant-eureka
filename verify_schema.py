import os

import xmlschema

if __name__ == "__main__":
    filepath_schema = "generated_schema.xsd"
    filepath_xml = "file.xml"

    schema = xmlschema.XMLSchema11(filepath_schema)

    print(schema.is_valid(filepath_xml))