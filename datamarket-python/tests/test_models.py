"""Every recorded production response parses into its model and serialises back unchanged.

A successful round trip proves three things at once: no field is lost, every
declared type accepts what the API sends, and fields the API adds beyond the
model are kept as extras.
"""

from __future__ import annotations

import pytest
from conftest import load_fixture

from cnovatech.datamarket import models

FIXTURE_MODELS: list[tuple[str, type[models.APIResponse]]] = [
    ("healthCheck", models.Health),
    ("getCatalog", models.CatalogPage),
    ("getCatalog", models.AsyncCatalogPage),
    ("listDepartments", models.DepartmentsResponse),
    ("listBrands", models.BrandsPage),
    ("listBrands", models.AsyncBrandsPage),
    ("getProductsByBrand", models.ProductsByBrandPage),
    ("getProductsByBrand", models.AsyncProductsByBrandPage),
    ("getProductByEan", models.Product),
    ("getProductPriceHistory", models.PriceHistory),
    ("checkCatalogCoverage", models.CoverageResponse),
    ("listStores", models.StoresPage),
    ("listStores", models.AsyncStoresPage),
    ("getStoreAssortment", models.AssortmentPage),
    ("getStoreAssortment", models.AsyncAssortmentPage),
    ("getStoreCompetitors", models.CompetitorsResponse),
    ("getStoreCompetitiveness", models.CompetitivenessResponse),
    ("getCompetitorProducts", models.ComparisonPage),
    ("getCompetitorProducts", models.AsyncComparisonPage),
    ("getStoreMarketPosition", models.MarketPositionPage),
    ("getStoreMarketPosition", models.AsyncMarketPositionPage),
    ("getStoreOpportunities", models.OpportunitiesPage),
    ("getStoreOpportunities", models.AsyncOpportunitiesPage),
    ("getStoresByBrand", models.StoresByBrandResponse),
    ("getProfile", models.Profile),
    ("getUsage", models.UsageHistory),
    ("getUserLogs", models.LogsPage),
    ("getUserLogs", models.AsyncLogsPage),
    ("listApiKeys", models.ApiKeys),
]


@pytest.mark.parametrize(
    ("name", "model"),
    FIXTURE_MODELS,
    ids=[f"{name}:{model.__name__}" for name, model in FIXTURE_MODELS],
)
def test_fixture_round_trips_through_its_model(name: str, model: type[models.APIResponse]) -> None:
    payload = load_fixture(f"{name}.json")

    instance = model.model_validate(payload)

    # Only fields the API sent are compared; a default the API omits, such as
    # the usage block of the free account endpoints, is not part of the contract.
    assert instance.model_dump(mode="json", exclude_unset=True) == payload


def test_unknown_fields_are_kept_as_extras() -> None:
    payload = load_fixture("getUserLogs.json")

    page = models.LogsPage.model_validate(payload)

    entry = page.data[0]
    declared = set(models.LogEntry.model_fields)
    extras = {key for key in payload["data"][0] if key not in declared}
    assert entry.model_extra is not None
    assert set(entry.model_extra) == extras


def test_models_are_immutable() -> None:
    health = models.Health.model_validate(load_fixture("healthCheck.json"))

    with pytest.raises(Exception, match="frozen"):
        health.status = "down"  # type: ignore[misc]
