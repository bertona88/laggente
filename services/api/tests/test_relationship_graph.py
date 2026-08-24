from __future__ import annotations


def create_public_turn(client, content: str):
    created = client.post("/api/v1/public/mauro/conversations", json={})
    assert created.status_code == 200, created.text
    payload = created.json()
    conversation_id = payload["conversation"]["id"]
    turn = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers={"X-Conversation-Token": payload["continuation_token"]},
        json={"content": content},
    )
    assert turn.status_code == 200, turn.text
    return conversation_id


def test_relationship_graph_is_private_bounded_and_uses_backend_sets(client):
    first_id = create_public_turn(
        client,
        "Ho una casa ereditata con mia sorella e sto pensando di venderla.",
    )
    second_id = create_public_turn(
        client,
        "Vorrei una valutazione prima di mettere in vendita l'appartamento.",
    )

    assert client.get("/api/v1/studio/relationship-graph").status_code == 401
    login = client.post(
        "/api/v1/auth/pilot-login",
        json={"email": "mauro@laggente.com", "password": "password-pilot-molto-sicura"},
    )
    assert login.status_code == 200

    response = client.get("/api/v1/studio/relationship-graph")
    assert response.status_code == 200, response.text
    graph = response.json()
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = graph["edges"]

    assert graph["center_id"] == "professional"
    assert graph["profile"] == {
        "vertical_id": "real_estate_it",
        "vertical_label": "Agenti immobiliari",
        "template_id": "seller_it_v1",
        "source": "backend_positioning",
    }
    assert nodes["professional"]["member_count"] == 2
    assert nodes[f"person:{first_id}"]["conversation_id"] == first_id
    assert nodes[f"person:{second_id}"]["conversation_id"] == second_id
    assert nodes["set:inherited_property"]["origin"] == "derived"
    assert nodes["set:inherited_property"]["weight"] == 95
    assert nodes["set:valuation"]["member_count"] == 1
    assert nodes["set:selling_intent"]["member_count"] == 2
    assert any(
        edge["source"] == f"person:{first_id}"
        and edge["target"] == "set:inherited_property"
        and edge["relation"] == "member_of"
        for edge in edges
    )
    assert len(graph["nodes"]) <= graph["bounds"]["node_limit"]
    assert len(graph["edges"]) <= graph["bounds"]["edge_limit"]
