"""Integration tests for the Event Manager API.

Tests verify:
- All required and optional APIs (events, users, registrations)
- Input validation (422 for malformed payloads, missing fields)
- Error handling (404 for missing resources, 4xx for conflicts)
- Correct behavior (data persisted in DB, cascade deletes, duplicate guards)
- Docstring presence on all route handlers
- Database-backed persistence (SQLite file, not in-memory Python structures)
"""
import importlib
import inspect

import requests


BASE_URL = "http://127.0.0.1:8000"

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

EVENT = {
    "title": "Test Event",
    "description": "A test description",
    "date": "2025-06-01T10:00:00",
    "location": "Test Location",
}

EVENT_UPDATED = {
    "title": "Updated Event",
    "description": "Updated description",
    "date": "2025-07-01T12:00:00",
    "location": "Updated Location",
}

USER = {
    "username": "testuser",
    "name": "Test User",
    "email": "testuser@example.com",
}

USER2 = {
    "username": "testuser2",
    "name": "Test User 2",
    "email": "testuser2@example.com",
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def GET(path):
    return requests.get(BASE_URL + path)


def POST(path, data):
    return requests.post(BASE_URL + path, json=data)


def PUT(path, data):
    return requests.put(BASE_URL + path, json=data)


def DELETE(path):
    return requests.delete(BASE_URL + path)


def clean_db():
    """Remove all data using individual deletes that properly cascade registrations."""
    users_resp = GET("/users")
    if users_resp.status_code == 200:
        users = users_resp.json()
        for user in users:
            username = user["username"] if isinstance(user, dict) else user
            DELETE(f"/users/{username}")

    events_resp = GET("/events")
    if events_resp.status_code == 200:
        events = events_resp.json()
        for event in events:
            event_id = event["id"] if isinstance(event, dict) else event
            DELETE(f"/events/{event_id}")


# ===========================================================================
# 0. STRUCTURAL CHECKS
# ===========================================================================


def test_database_is_used():
    """Verify the implementation uses a file-based SQLite database, not
    in-memory Python structures or an in-memory SQLite engine."""
    from app.data import db as db_module

    url = str(db_module.engine.url)
    assert ":memory:" not in url, (
        "The database engine is using an in-memory SQLite URL – "
        "the implementation may be using in-memory Python structures instead "
        "of a proper file-based database."
    )


def test_all_routes_have_docstrings():
    """Verify that every route handler function has a docstring."""
    router_modules = [
        "app.routers.events",
        "app.routers.users",
        "app.routers.registrations",
    ]
    missing = []
    for mod_name in router_modules:
        mod = importlib.import_module(mod_name)
        for route in mod.router.routes:
            fn = route.endpoint
            if not inspect.getdoc(fn):
                missing.append(f"{mod_name}: {fn.__name__}")
    assert not missing, f"Route handlers missing docstrings: {missing}"


# ===========================================================================
# 1. FRONTEND PAGES
# ===========================================================================


def test_frontend():
    """Verify that all frontend HTML pages render (200) and return HTML.
    Also verifies that a non-integer event-detail id returns 422."""
    clean_db()
    assert POST("/events", EVENT).status_code in (200, 201)
    event_id = GET("/events").json()[0]["id"]

    html_endpoints = ["/", "/events_list", f"/event_detail/{event_id}", "/users_list"]
    for endpoint in html_endpoints:
        response = GET(endpoint)
        assert response.status_code == 200, f"Expected 200 for {endpoint}"
        assert "text/html" in response.headers["Content-Type"], (
            f"Expected HTML for {endpoint}"
        )

    assert GET("/event_detail/not_a_number").status_code == 422


# ===========================================================================
# 2. EVENTS
# ===========================================================================


def test_events_list_returns_list():
    """GET /events must return a JSON list."""
    clean_db()
    response = GET("/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_event_invalid_type():
    """POST /events with an integer for a string field must return 422."""
    bad = dict(EVENT, title=0)
    assert POST("/events", bad).status_code == 422


def test_create_event_missing_field():
    """POST /events with a missing required field must return 422."""
    bad = {k: v for k, v in EVENT.items() if k != "date"}
    assert POST("/events", bad).status_code == 422


def test_create_event_invalid_date():
    """POST /events with a non-datetime date string must return 422."""
    bad = dict(EVENT, date="not-a-date")
    assert POST("/events", bad).status_code == 422


def test_create_event_valid():
    """POST /events with valid data must succeed and the event must appear in
    GET /events."""
    clean_db()
    response = POST("/events", EVENT)
    assert response.status_code in (200, 201)
    events = GET("/events").json()
    assert any(e["title"] == EVENT["title"] for e in events)


def test_get_event_by_id():
    """GET /events/{id} must return the correct event with all required fields."""
    clean_db()
    POST("/events", EVENT)
    events = GET("/events").json()
    event_id = next(e["id"] for e in events if e["title"] == EVENT["title"])

    response = GET(f"/events/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert data["title"] == EVENT["title"]
    assert data["description"] == EVENT["description"]
    assert data["location"] == EVENT["location"]
    assert data["id"] == event_id


def test_get_event_not_found():
    """GET /events/{id} for a non-existent ID must return 404."""
    assert GET("/events/999999").status_code == 404


def test_update_event_valid():
    """PUT /events/{id} with valid data must update the stored event."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]

    response = PUT(f"/events/{event_id}", EVENT_UPDATED)
    assert response.status_code == 200

    updated = GET(f"/events/{event_id}").json()
    assert updated["title"] == EVENT_UPDATED["title"]
    assert updated["description"] == EVENT_UPDATED["description"]
    assert updated["location"] == EVENT_UPDATED["location"]


def test_update_event_invalid_type():
    """PUT /events/{id} with an invalid field type must return 422."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    bad = dict(EVENT_UPDATED, title=0)
    assert PUT(f"/events/{event_id}", bad).status_code == 422


def test_update_event_not_found():
    """PUT /events/{id} for a non-existent ID must return 404."""
    assert PUT("/events/999999", EVENT_UPDATED).status_code == 404


def test_delete_event():
    """DELETE /events/{id} must remove the event; subsequent GET returns 404."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]

    assert DELETE(f"/events/{event_id}").status_code == 200
    assert GET(f"/events/{event_id}").status_code == 404


def test_delete_event_not_found():
    """DELETE /events/{id} for a non-existent ID must return 404."""
    assert DELETE("/events/999999").status_code == 404


def test_delete_event_cascades_registrations():
    """Deleting an event must also remove all registrations for that event."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    POST(f"/events/{event_id}/register", USER)

    assert any(r["event_id"] == event_id for r in GET("/registrations").json())

    DELETE(f"/events/{event_id}")

    assert not any(r["event_id"] == event_id for r in GET("/registrations").json())


def test_delete_all_events():
    """DELETE /events must remove all events; GET /events returns empty list."""
    POST("/events", EVENT)
    assert DELETE("/events").status_code == 200
    response = GET("/events")
    assert response.status_code == 200
    assert response.json() == []


# ===========================================================================
# 3. REGISTER TO EVENT
# ===========================================================================


def test_register_to_event():
    """POST /events/{id}/register must create a registration for the user."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]

    response = POST(f"/events/{event_id}/register", USER)
    assert response.status_code in (200, 201)

    regs = GET("/registrations").json()
    assert any(
        r["username"] == USER["username"] and r["event_id"] == event_id
        for r in regs
    )


def test_register_invalid_type():
    """POST /events/{id}/register with an integer for username must return 422."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    bad = dict(USER, username=0)
    assert POST(f"/events/{event_id}/register", bad).status_code == 422


def test_register_missing_field():
    """POST /events/{id}/register with a missing field must return 422."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    bad = {k: v for k, v in USER.items() if k != "name"}
    assert POST(f"/events/{event_id}/register", bad).status_code == 422


def test_register_event_not_found():
    """POST /events/{id}/register for a non-existent event must return 404."""
    assert POST("/events/999999/register", USER).status_code == 404


def test_register_duplicate():
    """Registering the same user to the same event twice must not cause a 5xx."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    POST(f"/events/{event_id}/register", USER)
    response = POST(f"/events/{event_id}/register", USER)
    assert response.status_code < 500


def test_register_auto_creates_new_user():
    """POST /events/{id}/register with a new username must create that user."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]

    POST(f"/events/{event_id}/register", USER2)

    users = GET("/users").json()
    assert any(u["username"] == USER2["username"] for u in users)


# ===========================================================================
# 4. USERS
# ===========================================================================


def test_users_list_returns_list():
    """GET /users must return a JSON list."""
    clean_db()
    response = GET("/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_user_invalid_type():
    """POST /users with an integer for a string field must return 422."""
    bad = dict(USER, username=0)
    assert POST("/users", bad).status_code == 422


def test_create_user_missing_field():
    """POST /users with a missing required field must return 422."""
    bad = {k: v for k, v in USER.items() if k != "name"}
    assert POST("/users", bad).status_code == 422


def test_create_user_valid():
    """POST /users with valid data must succeed and the user must appear in
    GET /users."""
    clean_db()
    response = POST("/users", USER)
    assert response.status_code in (200, 201)
    users = GET("/users").json()
    assert any(u["username"] == USER["username"] for u in users)


def test_create_user_duplicate():
    """POST /users with a duplicate username must return a 4xx error."""
    clean_db()
    POST("/users", USER)
    response = POST("/users", USER)
    assert 400 <= response.status_code < 500


def test_get_user_by_username():
    """GET /users/{username} must return the correct user."""
    clean_db()
    POST("/users", USER)
    response = GET(f"/users/{USER['username']}")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == USER["username"]
    assert data["name"] == USER["name"]
    assert data["email"] == USER["email"]


def test_get_user_not_found():
    """GET /users/{username} for a non-existent username must return 404."""
    assert GET("/users/nonexistent_user_xyz").status_code == 404


def test_delete_user():
    """DELETE /users/{username} must remove the user; subsequent GET returns 404."""
    clean_db()
    POST("/users", USER)
    assert DELETE(f"/users/{USER['username']}").status_code == 200
    assert GET(f"/users/{USER['username']}").status_code == 404


def test_delete_user_not_found():
    """DELETE /users/{username} for a non-existent username must return 404."""
    assert DELETE("/users/nonexistent_user_xyz").status_code == 404


def test_delete_user_cascades_registrations():
    """Deleting a user must also remove all their registrations."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    POST(f"/events/{event_id}/register", USER)

    assert any(r["username"] == USER["username"] for r in GET("/registrations").json())

    DELETE(f"/users/{USER['username']}")

    assert not any(
        r["username"] == USER["username"] for r in GET("/registrations").json()
    )


def test_delete_all_users():
    """DELETE /users must remove all users; GET /users returns empty list."""
    POST("/users", USER)
    assert DELETE("/users").status_code == 200
    response = GET("/users")
    assert response.status_code == 200
    assert response.json() == []


# ===========================================================================
# 5. REGISTRATIONS
# ===========================================================================


def test_registrations_list_returns_list():
    """GET /registrations must return a JSON list."""
    clean_db()
    response = GET("/registrations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_registration_response_format():
    """Registration objects must contain 'username' and 'event_id' fields."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    POST(f"/events/{event_id}/register", USER)

    regs = GET("/registrations").json()
    reg = next(r for r in regs if r["username"] == USER["username"])
    assert "username" in reg
    assert "event_id" in reg
    assert reg["event_id"] == event_id


def test_delete_registration():
    """DELETE /registrations?username=...&event_id=... must remove the record."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    POST(f"/events/{event_id}/register", USER)

    response = DELETE(
        f"/registrations?username={USER['username']}&event_id={event_id}"
    )
    assert response.status_code == 200

    regs = GET("/registrations").json()
    assert not any(
        r["username"] == USER["username"] and r["event_id"] == event_id
        for r in regs
    )


def test_delete_registration_event_not_found():
    """DELETE /registrations with a non-existent event_id must return 404."""
    response = DELETE(
        f"/registrations?username={USER['username']}&event_id=999999"
    )
    assert response.status_code == 404


def test_delete_registration_user_not_found():
    """DELETE /registrations with a non-existent username must return 404."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    response = DELETE(
        f"/registrations?username=nonexistent_xyz&event_id={event_id}"
    )
    assert response.status_code == 404


def test_delete_registration_not_found():
    """DELETE /registrations when no matching registration exists must return 404."""
    clean_db()
    POST("/events", EVENT)
    event_id = GET("/events").json()[0]["id"]
    POST("/users", USER)
    # User and event exist, but no registration has been created
    response = DELETE(
        f"/registrations?username={USER['username']}&event_id={event_id}"
    )
    assert response.status_code == 404

