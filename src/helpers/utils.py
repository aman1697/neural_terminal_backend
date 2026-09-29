def logger():
    import logging
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(__name__)

def read_json_file(file_path):
    try:
        logger().info(f"Reading JSON file: {file_path}")
        import json
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logger().error(f"File not found: {file_path}")
        return None



