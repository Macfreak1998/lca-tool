from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.constants import CLIMATE_CHANGE, METHOD_ID, ROLE_ADMIN, ROLE_USER, SOURCE_ECOINVENT
from app.db import Base, get_db
from app.main import app
from app.models import (
    Chain,
    ChainCombination,
    ChainCombinationAxis,
    ChainNode,
    Configuration,
    ConfigurationSelection,
    Dataset,
    DatasetFactor,
    DatasetRole,
    EndProduct,
    User,
)
from app.services.auth import hash_password


def _client() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        User(
            email="admin@localhost",
            password_hash=hash_password("admin"),
            role=ROLE_ADMIN,
            email_verified_at=datetime.utcnow(),
        )
    )
    session.add(
        User(
            email="user@localhost",
            password_hash=hash_password("secret12"),
            role=ROLE_USER,
            email_verified_at=datetime.utcnow(),
        )
    )
    session.commit()

    def override() -> object:
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override
    return TestClient(app), session


def _login(client: TestClient, email: str = "admin@localhost", password: str = "admin") -> None:
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200


def test_login_and_roles():
    client, _db = _client()
    denied = client.get("/api/roles")
    assert denied.status_code == 401
    _login(client)
    created = client.post("/api/roles", json={"label": "Stärke"})
    assert created.status_code == 200
    assert created.json()["slug"] == "starke"
    assert created.json()["dataset_count"] == 0
    listed = client.get("/api/roles")
    assert listed.status_code == 200
    assert listed.json()[0]["label"] == "Stärke"


def test_role_rename_and_delete_rules():
    client, db = _client()
    _login(client)
    starch = client.post("/api/roles", json={"label": "Stärke"}).json()
    unused = client.post("/api/roles", json={"label": "Leer"}).json()

    renamed = client.patch(f"/api/roles/{starch['id']}", json={"label": "Maisstärke"})
    assert renamed.status_code == 200
    assert renamed.json()["label"] == "Maisstärke"
    assert renamed.json()["slug"] == "starke"

    assert client.delete(f"/api/roles/{unused['id']}").status_code == 200

    dataset = Dataset(name="Maisstärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    dataset.roles.append(DatasetRole(role_id=starch["id"]))
    db.add(dataset)
    db.commit()

    listed = client.get("/api/roles").json()
    assert next(row for row in listed if row["id"] == starch["id"])["dataset_count"] == 1
    assert client.delete(f"/api/roles/{starch['id']}").status_code == 409

    slot_role = client.post("/api/roles", json={"label": "Nur Slot"}).json()
    end = EndProduct(name="Folie", unit="kg")
    db.add(end)
    db.flush()
    chain = Chain(name="HOF", status="draft", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    db.add(
        ChainNode(
            chain=chain,
            type="category",
            name="Kategorie",
            role_id=slot_role["id"],
            unit="kg",
        )
    )
    db.commit()
    assert client.delete(f"/api/roles/{slot_role['id']}").status_code == 409


def test_catalog_assign_and_delete():
    client, db = _client()
    _login(client)
    starch = client.post("/api/roles", json={"label": "Stärke"}).json()
    energy = client.post("/api/roles", json={"label": "Energie"}).json()

    dataset = Dataset(name="Maisstärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    dataset.roles.append(DatasetRole(role_id=starch["id"]))
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    empty = client.patch(f"/api/catalog/datasets/{dataset.id}", json={"role_ids": []})
    assert empty.status_code == 400
    unknown = client.patch(f"/api/catalog/datasets/{dataset.id}", json={"role_ids": [99999]})
    assert unknown.status_code == 400

    updated = client.patch(
        f"/api/catalog/datasets/{dataset.id}",
        json={"role_ids": [energy["id"], starch["id"]]},
    )
    assert updated.status_code == 200
    assert set(updated.json()["role_ids"]) == {energy["id"], starch["id"]}

    admin = db.query(User).filter(User.email == "admin@localhost").one()
    end = EndProduct(name="Folie", unit="kg")
    db.add(end)
    db.flush()
    chain = Chain(name="HOF", status="draft", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    product = ChainNode(chain=chain, type="product", name="Granulat", unit="kg", is_functional=True)
    category = ChainNode(chain=chain, type="category", name="Stärke", role_id=starch["id"], unit="kg")
    db.add_all([product, category])
    db.flush()
    combo = ChainCombination(chain=chain, process_node_id=product.id)
    db.add(combo)
    db.flush()
    axis = ChainCombinationAxis(combination=combo, category_node_id=category.id, dataset_id=dataset.id)
    db.add(axis)
    db.flush()
    config = Configuration(user_id=admin.id, chain_id=chain.id, name="Test", end_amount=1)
    db.add(config)
    db.flush()
    db.add(ConfigurationSelection(configuration_id=config.id, node_id=category.id, dataset_id=dataset.id))
    db.commit()

    removed = client.delete(f"/api/catalog/datasets/{dataset.id}")
    assert removed.status_code == 200
    db.expire_all()
    assert db.get(Dataset, dataset.id) is None
    assert db.get(ChainCombinationAxis, axis.id).dataset_id is None
    saved = db.get(Configuration, config.id)
    assert saved is not None
    assert saved.invalid is True


def test_save_sets_category_unit_from_dataset():
    client, db = _client()
    _login(client)
    role = client.post("/api/roles", json={"label": "Energie"}).json()
    end = client.post("/api/end-products", json={"name": "Folie", "unit": "kg"}).json()
    created = client.post("/api/chains", json={"name": "Strom", "end_product_id": end["id"]})
    assert created.status_code == 200
    chain = created.json()
    functional = chain["nodes"][0]
    dataset = Dataset(name="Strom DE", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    dataset.roles.append(DatasetRole(role_id=role["id"]))
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    saved = client.patch(
        f"/api/chains/{chain['id']}",
        json={
            "nodes": [
                {
                    "id": functional["id"],
                    "client_key": f"n-{functional['id']}",
                    "type": "product",
                    "name": "Folie",
                    "unit": "kg",
                    "is_functional": True,
                },
                {
                    "client_key": "process",
                    "type": "process",
                    "name": "Folieren",
                    "unit": "kg",
                },
                {
                    "client_key": "energy",
                    "type": "category",
                    "name": "Energie",
                    "role_id": role["id"],
                    "unit": "kg",
                },
                {
                    "client_key": "empty",
                    "type": "category",
                    "name": "Ohne Datensatz",
                    "unit": "kg",
                },
            ],
            "edges": [
                {"source_key": "energy", "target_key": "process", "kind": "energy"},
                {"source_key": "empty", "target_key": "process", "kind": "energy"},
                {"source_key": "process", "target_key": f"n-{functional['id']}", "kind": "material"},
            ],
            "combinations": [
                {
                    "process_key": "process",
                    "axes": [],
                    "amounts": [
                        {"category_key": "energy", "input_amount": 0.9},
                        {"category_key": "empty", "input_amount": 0.1},
                    ],
                }
            ],
            "dataset_shares": [
                {"category_key": "energy", "dataset_id": dataset.id, "default_share": 1}
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    units = {node["name"]: node["unit"] for node in saved.json()["nodes"]}
    assert units["Energie"] == "kWh"
    assert units["Ohne Datensatz"] == "kWh"


def test_catalog_and_roles_forbidden_for_user():
    client, db = _client()
    _login(client)
    starch = client.post("/api/roles", json={"label": "Stärke"}).json()
    dataset = Dataset(name="Maisstärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    dataset.roles.append(DatasetRole(role_id=starch["id"]))
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    client.post("/api/auth/logout")
    _login(client, "user@localhost", "secret12")
    assert client.patch(f"/api/roles/{starch['id']}", json={"label": "X"}).status_code == 403
    assert client.delete(f"/api/roles/{starch['id']}").status_code == 403
    assert client.patch(f"/api/catalog/datasets/{dataset.id}", json={"role_ids": [starch["id"]]}).status_code == 403
    assert client.delete(f"/api/catalog/datasets/{dataset.id}").status_code == 403


def test_chain_graph_roundtrip():
    client, db = _client()
    _login(client)
    role = client.post("/api/roles", json={"label": "Stärke"}).json()
    end = client.post("/api/end-products", json={"name": "Folie", "unit": "kg"}).json()
    created = client.post("/api/chains", json={"name": "Graph", "end_product_id": end["id"]})
    assert created.status_code == 200
    chain = created.json()
    functional = chain["nodes"][0]
    assert functional["is_functional"] is True
    dataset = Dataset(name="Maisstärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    dataset.roles.append(DatasetRole(role_id=role["id"]))
    dataset.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.5))
    recovery_ds = Dataset(name="Verbrennung", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    recovery_ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=2.0))
    db.add_all([dataset, recovery_ds])
    db.commit()
    db.refresh(dataset)
    db.refresh(recovery_ds)
    saved = client.patch(
        f"/api/chains/{chain['id']}",
        json={
            "nodes": [
                {
                    "id": functional["id"],
                    "client_key": f"n-{functional['id']}",
                    "type": "product",
                    "name": "Folie",
                    "position_x": 400,
                    "position_y": 80,
                    "unit": "kg",
                    "is_functional": True,
                },
                {
                    "client_key": "process",
                    "type": "process",
                    "name": "Herstellung",
                    "position_x": 220,
                    "position_y": 80,
                    "unit": "kg",
                },
                {
                    "client_key": "starch",
                    "type": "category",
                    "name": "Stärke",
                    "position_x": 40,
                    "position_y": 80,
                    "role_id": role["id"],
                    "unit": "kg",
                    "datasets_differ": True,
                },
                {
                    "client_key": "waste",
                    "type": "recovery",
                    "name": "Verwertung",
                    "position_x": 200,
                    "position_y": 240,
                    "dataset_id": recovery_ds.id,
                    "unit": "kg",
                },
            ],
            "edges": [
                {
                    "source_key": "starch",
                    "target_key": "process",
                    "kind": "material",
                },
                {
                    "source_key": "process",
                    "target_key": f"n-{functional['id']}",
                    "kind": "material",
                },
            ],
            "combinations": [
                {
                    "process_key": "process",
                    "axes": [{"category_key": "starch", "dataset_id": dataset.id}],
                    "amounts": [
                        {
                            "category_key": "starch",
                            "input_amount": 1.2,
                            "recovery_key": "waste",
                        }
                    ],
                }
            ],
            "dataset_shares": [
                {"category_key": "starch", "dataset_id": dataset.id, "default_share": 1}
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert len(body["nodes"]) == 4
    assert body["combinations"][0]["amounts"][0]["input_amount"] == 1.2
    published = client.post(f"/api/chains/{chain['id']}/publish")
    assert published.status_code == 200, published.text
    result = client.post(
        "/api/calculate",
        json={"chain_id": chain["id"], "end_amount": 1, "selections": {}, "shares": {}, "optional_on": []},
    )
    assert result.status_code == 200, result.text
    # 1,2 kg Stärke × 1,5 und Abfall (1,2 − 1) × 2
    assert result.json()["totals"]["climate_change"] == 1.2 * 1.5 + (1.2 - 1) * 2
