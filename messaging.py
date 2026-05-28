from twilio.rest import Client
from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    MY_PHONE_NUMBER,
)

_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_sms(body: str, to: str = None) -> bool:
    """
    Send an SMS via Twilio.
    Defaults to MY_PHONE_NUMBER if `to` is not specified.
    Returns True on success, False on error.
    """
    recipient = to or MY_PHONE_NUMBER
    try:
        _twilio.messages.create(
            body=body,
            from_=TWILIO_PHONE_NUMBER,
            to=recipient,
        )
        print(f"[messaging] SMS sent to {recipient}: {body[:60]}...")
        return True
    except Exception as exc:
        print(f"[messaging] Failed to send SMS: {exc}")
        return False
