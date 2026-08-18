from pyscattviz.app.state import (
    prepare_persistent_widget,
    set_persistent_value,
    store_persistent_widget,
    widget_key,
)


def test_widget_value_restores_after_streamlit_page_cleanup():
    state = {}
    disposable = prepare_persistent_widget(state, "remote_products", ["cir_avg"])
    state[disposable] = ["cir_avg", "q_image"]
    store_persistent_widget(state, "remote_products")

    del state[disposable]
    restored = prepare_persistent_widget(state, "remote_products", [])

    assert restored == widget_key("remote_products")
    assert state[restored] == ["cir_avg", "q_image"]
    assert state["remote_products"] == ["cir_avg", "q_image"]


def test_programmatic_update_replaces_old_widget_value_on_next_page_run():
    state = {}
    disposable = prepare_persistent_widget(state, "remote_path", "/old")
    assert state[disposable] == "/old"

    set_persistent_value(state, "remote_path", "/new")
    prepare_persistent_widget(state, "remote_path", "/ignored")

    assert state[disposable] == "/new"
