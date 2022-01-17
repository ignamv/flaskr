from io import BytesIO


def generate_no_file_selected():
    return (BytesIO(b""), "")


def generate_file_tuple(contents):
    return BytesIO(contents), "filename.jpg"
