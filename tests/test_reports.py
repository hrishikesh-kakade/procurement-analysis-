import pytest

from app.models.enums import UserRole as R
from tests.factories import API, create_material, create_purchase_order, create_supplier, set_po_status


def _request(client, report_type="supplier_performance", **extra):
    return client.post(f"{API}/reports", json={"report_type": report_type, **extra})


def test_report_job_lifecycle_and_csv_download(client):
    supplier = create_supplier(client, name="Report Supplier")
    material = create_material(client, unit_price="20.00")
    order = create_purchase_order(client, supplier["id"], items=[{"material_id": material["id"], "quantity": 3}])
    set_po_status(client, order["id"], "issued")

    created = _request(client)
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    assert client.get(f"{API}/reports/{job_id}").json()["status"] == "finished"

    download = client.get(f"{API}/reports/{job_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/csv")
    lines = download.text.strip().splitlines()
    assert lines[0].startswith("supplier_id,supplier_name,order_count,total_spend")
    assert "Report Supplier" in lines[1] and "60.00" in lines[1]


@pytest.mark.parametrize(
    "report_type", ["supplier_scorecard", "monthly_spend", "department_spend", "purchase_orders"]
)
def test_every_report_type_produces_csv_with_header(client, report_type):
    job_id = _request(client, report_type).json()["job_id"]
    text = client.get(f"{API}/reports/{job_id}/download").text
    assert text.count("\n") >= 1


def test_purchase_order_report_lists_orders(client):
    supplier = create_supplier(client)
    material = create_material(client)
    order = create_purchase_order(client, supplier["id"], items=[{"material_id": material["id"], "quantity": 1}])
    job_id = _request(client, "purchase_orders").json()["job_id"]
    assert order["po_number"] in client.get(f"{API}/reports/{job_id}/download").text


def test_reports_are_private_to_their_owner(client, make_client):
    job_id = _request(client).json()["job_id"]  # created by the admin fixture user
    viewer = make_client(R.VIEWER)
    assert viewer.get(f"{API}/reports/{job_id}").status_code == 404
    assert viewer.get(f"{API}/reports/{job_id}/download").status_code == 404
    own = _request(viewer).json()["job_id"]
    assert viewer.get(f"{API}/reports/{own}").status_code == 200
    assert client.get(f"{API}/reports/{own}").status_code == 200  # admins can see all


def test_report_validation_and_permissions(client, make_client):
    assert _request(client, "nonsense").status_code == 422
    assert _request(client, date_from="2026-03-01", date_to="2026-01-01").status_code == 422
    assert _request(make_client(R.REQUESTER)).status_code == 403
    assert client.get(f"{API}/reports/does-not-exist").status_code == 404
