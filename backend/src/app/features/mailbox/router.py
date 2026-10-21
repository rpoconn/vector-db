"""Test-only inbox: lets end-to-end tests read the links the app e-mails.

Mounted only when `APP_ENV=test`, where every message is kept in memory by
`RecordingEmailSender`; it is left out of the OpenAPI spec.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr

from app.shared.email import EmailSender, OutgoingEmail, RecordingEmailSender, get_email_sender

MAILBOX_PATH = "/_test/mailbox"

router = APIRouter(tags=["mailbox"], include_in_schema=False)


def get_mailbox(sender: Annotated[EmailSender, Depends(get_email_sender)]) -> RecordingEmailSender:
    if not isinstance(sender, RecordingEmailSender):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Mailbox is not recording")
    return sender


MailboxDep = Annotated[RecordingEmailSender, Depends(get_mailbox)]


@router.get(MAILBOX_PATH, response_model=list[OutgoingEmail])
async def list_messages(
    mailbox: MailboxDep, to: Annotated[EmailStr | None, Query()] = None
) -> list[OutgoingEmail]:
    """Recorded messages, oldest first, optionally only those addressed to `to`."""
    return mailbox.messages_to(to) if to else list(mailbox.messages)


@router.delete(MAILBOX_PATH, status_code=status.HTTP_204_NO_CONTENT)
async def clear_messages(mailbox: MailboxDep) -> None:
    mailbox.clear()
