"""Log in to Gmail and show which inbox we are connected to.

Run this once to sign in. Run it again any time to check the connection.
"""

from app.gmail import get_service

service = get_service()
profile = service.users().getProfile(userId="me").execute()

print("Connected to:", profile["emailAddress"])
print("Total messages in this mailbox:", profile["messagesTotal"])
