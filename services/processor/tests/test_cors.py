from fastapi.testclient import TestClient

from nixclip_processor.main import app


def test_private_site_can_preflight_local_processor() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://nixclip.fnxtutors.chatgpt.site",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Private-Network": "true",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://nixclip.fnxtutors.chatgpt.site"
    assert response.headers["access-control-allow-private-network"] == "true"
