"""Re-ID prototype updates must not treat an unknown sample count as 1."""
import numpy as np

from backend.app.services.reid_gallery_update import apply_counted_prototype_update


def _unit(x: float, y: float) -> np.ndarray:
    v = np.array([x, y], dtype=np.float64)
    return v / np.linalg.norm(v)


def test_missing_counts_do_not_rewrite_existing_prototype():
    names = ["02Q1"]
    proto = _unit(1.0, 0.0).reshape(1, 2)
    embedding = _unit(0.0, 1.0)

    assert apply_counted_prototype_update(names, proto, None, "02Q1", embedding) is None
    assert apply_counted_prototype_update(names, proto, [1, 1], "02Q1", embedding) is None

    # The old fallback (n=1) would have pulled the mean halfway toward the new crop.
    warped = _unit(1.0, 1.0)
    assert float(np.dot(proto[0], warped)) < 0.8
    assert np.allclose(proto[0], _unit(1.0, 0.0))


def test_known_count_weights_history_heavier_than_one_crop():
    names = ["02Q1"]
    proto = _unit(1.0, 0.0).reshape(1, 2)
    embedding = _unit(0.0, 1.0)

    one = apply_counted_prototype_update(names, proto, [1], "02Q1", embedding)
    many = apply_counted_prototype_update(names, proto, [20], "02Q1", embedding)
    assert one is not None and many is not None

    _, one_protos, one_counts = one
    _, many_protos, many_counts = many
    original = proto[0]
    one_sim = float(np.dot(one_protos[0], original))
    many_sim = float(np.dot(many_protos[0], original))

    assert one_counts == [2]
    assert many_counts == [21]
    assert many_sim > 0.99
    assert one_sim < many_sim
    assert abs(one_sim - (1 / np.sqrt(2))) < 1e-6


def test_new_identity_is_appended_only_when_counts_are_known():
    names = ["02Q1"]
    proto = _unit(1.0, 0.0).reshape(1, 2)
    embedding = _unit(0.0, 1.0)

    assert apply_counted_prototype_update(names, proto, None, "02Q2", embedding) is None

    added = apply_counted_prototype_update(names, proto, [4], "02Q2", embedding)
    assert added is not None
    new_names, new_protos, new_counts = added
    assert new_names == ["02Q1", "02Q2"]
    assert new_counts == [4, 1]
    assert new_protos.shape == (2, 2)
    assert np.allclose(new_protos[0], proto[0])
    assert np.allclose(new_protos[1], embedding)
