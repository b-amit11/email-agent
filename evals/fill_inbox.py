"""Put the test emails from cases.json into the real Gmail inbox.

Run it with:  python -m evals.fill_inbox
Options:      --ids damaged-candle tunneling   (only these cases)

Each test email is placed in the inbox as an unread message, as if a customer
had written it. From there the normal program takes over: it drafts a reply
and shows it on the Reply Desk for a person to approve or reject.

The made-up customers are given addresses that lead back to this same inbox
(name+case@gmail.com), so an approved reply is a real email that arrives
here and never reaches a stranger.

Running it twice puts every email in the inbox twice.
"""

import argparse
import base64
import json
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from app import gmail

CASES = Path(__file__).parent / "cases.json"


def build_message(case: dict, inbox: str) -> dict:
    """Turn one test case into a Gmail message for the inbox."""
    user, domain = inbox.split("@")
    sender = f"{user}+{case['id']}@{domain}"
    email = case["email"]

    message = EmailMessage()
    message["From"] = formataddr((email.get("from_name") or "", sender))
    message["To"] = inbox
    message["Subject"] = email.get("subject") or ""
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(email["body"])

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return {"raw": raw, "labelIds": ["INBOX", "UNREAD"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Put the test emails into the Gmail inbox.")
    parser.add_argument("--ids", nargs="*", help="Only these case ids.")
    args = parser.parse_args()

    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if args.ids:
        cases = [case for case in cases if case["id"] in args.ids]

    service = gmail.get_service()
    inbox = gmail.own_address()
    for case in cases:
        service.users().messages().insert(userId="me", body=build_message(case, inbox)).execute()
        print(f"  in the inbox: {case['id']}")
    print(f"Done: {len(cases)} test email(s) placed in {inbox}.")


if __name__ == "__main__":
    main()
