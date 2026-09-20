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


def test_single_listing_order_for_non_poolable(client):
    chairs = client.get("/api/listings?q=chairs").json()[0]
    buyer = org_id(client, "Anita K.")
    q = client.post("/api/pools/quote", json=dict(buyer_id=buyer, listing_id=chairs["id"], quantity=5)).json()
    assert q["status"] == "ok" and not q["pooled"] and q["subtotal"] == 4500
    kids = client.get("/api/listings?q=kids").json()[0]
    assert client.post("/api/pools/quote", json=dict(buyer_id=buyer, listing_id=kids["id"], quantity=1)).status_code == 400


def test_signup_and_seller_dashboard(client):
    r = client.post("/api/orgs", json=dict(name="Green Leaf Cafe", role="business", phone="+91 98765 43210",
                                           lat=12.97, lng=77.64, accepts_categories=["packaging"]))
    assert r.status_code == 201 and r.json()["verified"] is False
    me = r.json()["id"]
    assert client.post("/api/orgs", json=dict(name="Green Leaf Cafe", role="business", lat=1, lng=1)).status_code == 409
    assert client.post("/api/orgs", json=dict(name="X Co", role="business", lat=1, lng=1,
                                              accepts_categories=["rockets"])).status_code == 422

    draft = client.post("/api/listings", json=dict(
        seller_id=me, category="packaging", title="Clean cardboard boxes", quantity=40, unit="pieces",
        condition="good", reason_code="inbound_packaging", reason_detail="Boxes from this week's supplier deliveries.",
        asking_price_per_unit=10, attributes=dict(material="cardboard", clean_dry=True))).json()["listing"]
    dash = client.get(f"/api/orgs/{me}/dashboard").json()
    assert dash["totals"]["drafts"] == 1 and dash["listings"][0]["id"] == draft["id"]
    assert dash["listings"][0]["readiness"]["missing_shots"]

    # a seed seller sees the order the seed placed on their chairs
    nimbus = org_id(client, "Nimbus Tech Park Facilities")
    sales = client.get(f"/api/orgs/{nimbus}/dashboard").json()["sales"]
    assert any(s["title"] == "Mesh-back office chairs" and s["status"] == "confirmed" for s in sales)
    ravi = org_id(client, "Ravi Renovations")
    assert client.get(f"/api/orgs/{ravi}/dashboard").json()["purchases"]


def test_order_tracking_route_and_progress(client):
    buyer = org_id(client, "Ravi Renovations")
    pool = client.post("/api/pools", json=dict(buyer_id=buyer, listing_id=1, quantity=200)).json()
    client.post(f"/api/pools/{pool['id']}/confirm")

    t = client.get(f"/api/pools/{pool['id']}/tracking").json()
    assert t["stage"] == "confirmed" and t["total_stops"] == 3 and t["collected"] == 0
    assert [s["stop_no"] for s in t["stops"]] == [1, 2, 3]
    assert t["stops"][0]["distance_km"] >= t["stops"][-1]["distance_km"]   # furthest first, ends near the buyer
    assert t["route_km"] > 0 and t["eta_minutes"] > 0
    assert t["buyer"]["lat"] and all(s["lat"] for s in t["stops"])

    first = t["stops"][0]["listing_id"]
    t = client.post(f"/api/pools/{pool['id']}/stops/{first}/collected").json()
    assert t["collected"] == 1 and t["stage"] == "out_for_pickup" and t["progress_pct"] == 33
    assert next(s for s in t["stops"] if s["listing_id"] == first)["picked_up_at"]

    t = client.post(f"/api/pools/{pool['id']}/delivered").json()
    assert t["status"] == "delivered" and t["collected"] == 3 and t["progress_pct"] == 100
    assert t["timeline"][-1]["done"]
    assert client.post(f"/api/pools/{pool['id']}/delivered").status_code == 409   # already done


def test_damage_scan_marks_regions_on_a_photo(client, monkeypatch):
    from app.services import vision

    async def fake_inspect(image, label="item"):
        assert isinstance(image, bytes) and label
        return vision.clean_defects({
            "summary": "Mesh seat is torn; frame and wheels look sound.",
            "condition": "fair",
            "regions": [
                {"label": "Torn mesh", "severity": "high", "note": "seat back, 10 cm tear", "x": .3, "y": .2, "w": .3, "h": .25},
                {"label": "Surface scratches", "severity": "medium", "x": .1, "y": .6, "w": .2, "h": .1},
                {"label": "Frame intact", "severity": "ok", "x": .05, "y": .05, "w": 2, "h": .2},   # oversized: clamped
            ]}, "groq")

    monkeypatch.setattr(vision, "inspect", fake_inspect)
    chairs = client.get("/api/listings?q=chairs").json()[0]
    image_id = chairs["images"][0]["id"]

    r = client.post(f"/api/listings/{chairs['id']}/images/{image_id}/inspect")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["severity"] for x in body["regions"]] == ["high", "medium", "ok"]   # worst first
    assert body["regions"][2]["x"] + body["regions"][2]["w"] <= 1                 # kept inside the photo
    assert body["condition"] == "fair"

    # buyers see it on the listing afterwards
    again = client.get(f"/api/listings/{chairs['id']}").json()
    saved = next(i for i in again["images"] if i["id"] == image_id)["defect_map"]
    assert saved["regions"][0]["label"] == "Torn mesh" and "torn" in saved["summary"].lower()
    assert client.post(f"/api/listings/{chairs['id']}/images/999999/inspect").status_code == 404


def test_voice_pickup_deadline_is_not_a_cooking_time():
    from datetime import timezone
    from app.services.voice import parse_food_text
    d = parse_food_text("40 plates of veg biryani are ready for pickup before 7 PM")
    assert d["attributes"]["dish_name"] == "Biryani"   # "veg" becomes the diet, "ready for pickup before 7 PM" is dropped
    cooked = d["attributes"]["cooked_at"]
    from datetime import datetime
    assert (datetime.now(timezone.utc) - datetime.fromisoformat(cooked)).total_seconds() < 120  # "just now", not 7pm
    assert parse_food_text("30 plates dal rice cooked at 6 pm")["attributes"]["cooked_at"].endswith("+00:00")
