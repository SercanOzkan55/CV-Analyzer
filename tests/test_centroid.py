from unittest.mock import MagicMock
import pytest

from utils.centroid import update_centroid


def test_update_centroid_success():
    cur = MagicMock()

    # Mock database fetch result (json format centroid)
    cur.fetchone.return_value = ("[0.1, 0.2, 0.3]", 2)

    update_centroid(cur, "domains", 1, [0.4, 0.5, 0.6])

    # Verify SELECT was executed
    cur.execute.assert_any_call("SELECT centroid, sample_count FROM domains WHERE id = %s;", (1,))

    # Verify UPDATE was executed with correct updated centroid
    # (0.1 * 2 + 0.4) / 3 = 0.2
    # (0.2 * 2 + 0.5) / 3 = 0.3
    # (0.3 * 2 + 0.6) / 3 = 0.4
    expected_updated = [0.2, 0.3, 0.4]

    called_args = cur.execute.call_args_list
    assert len(called_args) == 2
    update_query, update_params = called_args[1][0]
    assert "UPDATE domains" in update_query

    assert update_params[0] == pytest.approx(expected_updated)
    assert update_params[1] == 1


def test_update_centroid_no_row():
    cur = MagicMock()
    cur.fetchone.return_value = None

    update_centroid(cur, "domains", 1, [0.1, 0.2])

    assert cur.execute.call_count == 1


def test_update_centroid_non_string_centroid():
    cur = MagicMock()
    cur.fetchone.return_value = ([0.1, 0.2], 1)

    update_centroid(cur, "domains", 1, [0.3, 0.4])

    called_args = cur.execute.call_args_list

    assert called_args[1][0][1][0] == pytest.approx([0.2, 0.3])


def test_update_centroid_rejects_unknown_table():
    cur = MagicMock()

    with pytest.raises(ValueError, match="Unsupported centroid table"):
        update_centroid(cur, "test_table", 1, [0.1, 0.2])

    cur.execute.assert_not_called()
