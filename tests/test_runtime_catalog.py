from miaos.runtime import RuntimeCatalog


def test_runtime_catalog_loads_expected_profiles() -> None:
    catalog = RuntimeCatalog.from_directory()

    assert catalog.list_profile_names() == (
        "macbook_air_m4_32gb",
        "macbook_pro_m4pro_48gb",
    )


def test_selects_macbook_air_profile_from_hardware() -> None:
    catalog = RuntimeCatalog.from_directory()

    selected = catalog.select_for_hardware(
        machine_family="macbook_air",
        chip="m4",
        unified_memory_gb=32,
    )

    assert selected.name == "macbook_air_m4_32gb"
    assert selected.hardware.runtime_memory_budget_gb == 24


def test_selects_macbook_pro_profile_from_hardware() -> None:
    catalog = RuntimeCatalog.from_directory()

    selected = catalog.select_for_hardware(
        machine_family="macbook_pro",
        chip="m4pro",
        unified_memory_gb=48,
    )

    assert selected.name == "macbook_pro_m4pro_48gb"
    assert selected.default_model_id == "qwen3.6-27b-8bit"
