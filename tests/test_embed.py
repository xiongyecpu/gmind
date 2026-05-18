from gmind.embed import _vector_literal


def test_vector_literal_formats_pgvector_value() -> None:
    assert _vector_literal([0.1, -0.2, 0.0]) == "[0.1,-0.2,0.0]"
