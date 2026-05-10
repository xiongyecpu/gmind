from gmind.utils import make_checksum, slugify


def test_make_checksum():
    assert make_checksum("hello") == make_checksum("hello")
    assert make_checksum("hello") != make_checksum("world")


def test_slugify_ascii():
    assert slugify("Hello World") == "hello-world"


def test_slugify_chinese():
    assert slugify("张三") == "zhang-san"


def test_slugify_empty_fallback():
    assert slugify("!!!") == "untitled"
