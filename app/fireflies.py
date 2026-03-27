import hmac
import hashlib

import requests

FIREFLIES_API_URL = "https://api.fireflies.ai/graphql"


def verify_fireflies_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    if not secret or not signature_header:
        return False

    sig = signature_header
    if sig.startswith("sha256="):
        sig = sig[len("sha256="):]

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def fetch_transcript(meeting_id: str, api_key: str) -> dict:
    query = """
    query Transcript($id: String!) {
        transcript(id: $id) {
            id
            title
            transcript_url
            participants
            summary {
                overview
                action_items
                bullet_gist
            }
        }
    }
    """
    response = requests.post(
        FIREFLIES_API_URL,
        json={"query": query, "variables": {"id": meeting_id}},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("transcript", {})
