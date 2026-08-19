import io

import numpy as np
import pytest

from pyscattviz.studio import (
    demo_curve_table,
    demo_image,
    read_array_bundle,
    read_numeric_table,
    two_dimensional_arrays,
)


def test_numeric_table_and_demo_data():
    table = read_numeric_table(b"q,I,name\n0.1,10,a\n0.2,5,b\n", "curve.csv")
    assert table.columns.tolist() == ["q", "I"]
    assert demo_curve_table(20).shape == (20, 4)
    assert demo_image(50).ndim == 2


def test_array_bundle_disables_pickle_and_selects_2d_arrays():
    payload = io.BytesIO()
    np.savez(payload, image=np.ones((3, 4)), axis=np.arange(4))
    bundle = read_array_bundle(payload.getvalue(), "products.npz")
    assert list(two_dimensional_arrays(bundle)) == ["image"]


def test_invalid_table_has_clear_error():
    with pytest.raises(ValueError, match="no numeric columns"):
        read_numeric_table(b"name\na\nb\n", "names.csv")
