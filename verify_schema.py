import os
import sys
import xmlschema

if __name__ == "__main__":
    filepath_schema = "generated_schema.xsd"
    filepath_xml = "file.xml"

    try:
        schema = xmlschema.XMLSchema11(filepath_schema)
    except Exception as e:
        print(f"Error loading schema '{filepath_schema}':\n{e}", file=sys.stderr)
        sys.exit(1)


    try:
        schema.validate(filepath_xml)
        print(f"'{filepath_xml}' is valid against '{filepath_schema}'.")
    except xmlschema.XMLSchemaValidationError as e:
        print(f"'{filepath_xml}' is NOT valid against '{filepath_schema}'.", file=sys.stderr)
        print(f"Reason:\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during validation:\n{e}", file=sys.stderr)
        sys.exit(1)