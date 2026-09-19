from scripts.synth import WARM_BULB, photo


def org_id(client, name):
    return next(o["id"] for o in client.get("/api/orgs").json() if o["name"] == name)


def test_category_form_spec(client):
    spec = client.get("/api/categories/tiles").json()
    assert spec["min_images"] == 4
    assert "color_reference" in [s["key"] for s in spec["shots"]]
    assert {p["key"] for p in spec["provenance_required"]} >= {"brand", "manufacturer_color"}
    assert spec["reasons"] and spec["brand_second_extras"]["requires"]


def test_listing_draft_photos_publish(client):
    seller = org_id(client, "Sharma Interiors")
    body = dict(seller_id=seller, category="tiles", title="Leftover matte white tiles", quantity=30, unit="pieces",
                condition="good", reason_code="over_ordered", reason_detail="Ordered two extra boxes by mistake.",
                brand="Terrano Tiles", model_sku="TR-6060-MW", manufacturer_color="Arctic Matte White",
                purchased_from="Kavya Tiles", asking_price_per_unit=80,
                attributes=dict(material="vitrified", size_mm="600x600", finish="matte", usage="floor", boxed=True))
    r = client.post("/api/listings", json=body)
    assert r.status_code == 201, r.text
    lid = r.json()["listing"]["id"]
    assert r.json()["listing"]["route"] == "resell"
    assert len(r.json()["readiness"]["missing_shots"]) == 4

    assert client.post(f"/api/listings/{lid}/publish").status_code == 409

    up = lambda shot, data: client.post(f"/api/listings/{lid}/images", data={"shot_type": shot},  # noqa: E731
                                        files={"file": (f"{shot}.jpg", data, "image/jpeg")})
    r = up("full_lot", photo((232, 228, 220), blur=True))
    assert r.json()["image"]["problems"] and r.json()["readiness"]["retake_shots"]
    for i, shot in enumerate(["full_lot", "surface_closeup", "label", "color_reference"]):
        assert up(shot, photo((232, 228, 220), tint=WARM_BULB, seed=i)).status_code == 201

    r = client.post(f"/api/listings/{lid}/publish")
    assert r.status_code == 200, r.text
    assert r.json()["listing"]["measured_color_hex"]


def test_bad_listing_returns_field_errors(client):
    r = client.post("/api/listings", json=dict(
        seller_id=1, category="tiles", title="Some tiles", quantity=5, unit="pieces", condition="good",
        reason_code="project_surplus", reason_detail="short", attributes={}))
    assert r.status_code == 422
    assert {"reason_detail", "brand", "attributes.size_mm"} <= {e["field"] for e in r.json()["detail"]}


def test_pooled_lot_excludes_other_batch_and_reserves_all_or_nothing(client):
    buyer = org_id(client, "Ravi Renovations")
    q = client.post("/api/pools/quote", json=dict(buyer_id=buyer, listing_id=1, quantity=200)).json()
    assert q["status"] == "ok", q
    assert {i["listing_id"] for i in q["items"]} == {1, 2, 3}
    assert any(e["listing_id"] == 4 and "shade" in e["reason"] for e in q["excluded"])
    assert q["total"] < q["new_price_total"] and q["savings_pct"] > 25
    assert q["shade_match_pct"] > 85

    pool = client.post("/api/pools", json=dict(buyer_id=buyer, listing_id=1, quantity=200)).json()
    assert pool["status"] == "reserved"
    again = client.post("/api/pools", json=dict(buyer_id=buyer, listing_id=1, quantity=200))
    assert again.status_code == 409

    client.post(f"/api/pools/{pool['id']}/cancel")
    assert client.post("/api/pools/quote", json=dict(buyer_id=buyer, listing_id=1, quantity=200)).json()["status"] == "ok"

    pool = client.post("/api/pools", json=dict(buyer_id=buyer, listing_id=1, quantity=200)).json()
    done = client.post(f"/api/pools/{pool['id']}/confirm").json()
    assert done["status"] == "confirmed"
    assert client.get("/api/listings/1").json()["status"] == "sold_out"
    assert client.get("/api/impact/summary").json()["value_recovered_inr"] > 0


def test_demand_first_pool_and_insufficient_stock(client):
    buyer = org_id(client, "Anita K.")
    match = {"brand": "terrano tiles", "model_sku": "TR 6060 MW", "manufacturer_color": "Arctic Matte White",
             "size_mm": "600x600", "finish": "Matte"}
    q = client.post("/api/pools/quote", json=dict(buyer_id=buyer, category="tiles", match=match, quantity=150)).json()
    assert q["status"] == "ok" and q["allocated"] == 150
    q = client.post("/api/pools/quote", json=dict(buyer_id=buyer, category="tiles", match=match, quantity=500)).json()
    assert q["status"] == "insufficient_stock"


def test_food_claims(client):
    food = next(li for li in client.get("/api/listings?category=food_cooked").json() if li["status"] == "published")
    assert client.get(f"/api/listings/{food['id']}/dispatch").json()
    unverified = org_id(client, "Hope Kitchen Collective")
    assert client.post(f"/api/listings/{food['id']}/claim", json={"org_id": unverified}).status_code == 403
    ngo = org_id(client, "Second Serving Trust")
    r = client.post(f"/api/listings/{food['id']}/claim", json={"org_id": ngo, "quantity": 30})
    assert r.status_code == 201 and r.json()["remaining"] == 10
    assert client.post(f"/api/listings/{food['id']}/claim", json={"org_id": ngo, "quantity": 20}).status_code == 409
    cert = client.get(f"/api/impact/orgs/{food['seller']['id']}/certificate").json()
    assert cert["meals_rescued"] >= 55 and "Second Serving Trust" in cert["recipients"]


def test_voice_text_draft():
    from app.services.voice import parse_food_text
    d = parse_food_text("We have forty plates of veg biryani, cooked at 9 pm, packed in containers")
    assert d["quantity"] == 40 and d["unit"] == "plates"
    assert d["attributes"]["diet"] == "veg" and d["attributes"]["packaging"] == "sealed_containers"
    assert d["attributes"]["dish_name"] == "Biryani"
    assert parse_food_text("5 kg chicken curry in the fridge")["attributes"]["diet"] == "non_veg"
    h = parse_food_text("Bees plates paneer biryani bache hain, packed in containers")
    assert h["quantity"] == 20 and h["attributes"]["dish_name"] == "Paneer Biryani" and h["attributes"]["diet"] == "veg"


def test_matches_route_to_right_partners(client):
    monitors = client.get("/api/listings?q=monitors").json()[0]
    names = [m["name"] for m in client.get(f"/api/listings/{monitors['id']}/matches").json()["matches"]]
    assert names == ["CircuitCycle E-Waste Recyclers"]


def test_ai_analyze_mock_prefills(client):
    r = client.post("/api/ai/analyze", files=[("files", ("old_tiles.jpg", photo((230, 230, 225)), "image/jpeg"))])
    body = r.json()
    assert body["form_prefill"]["category"] == "tiles" and body["analysis"]["reuse_ideas"]
