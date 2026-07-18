import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.message import Message, MessageThread
from app.models.user import User
from app.schemas.message import MessageCreate, MessageOut, ThreadCreate, ThreadSummaryOut
from app.services.notifications import notify_from_template

router = APIRouter(prefix="/messages", tags=["messages"])

# Simple heuristic flags for off-platform contact attempts pre-contract —
# protects students from being pulled off-platform before safeguards apply,
# and protects platform fee integrity. A production system would use a
# smarter classifier; this regex layer is the first line of defence.
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@(?!.*\.(ac\.uk|caplink\.io))[\w-]+\.[\w.-]+")
_SUSPICIOUS_PHRASES = ["pay you directly", "off the platform", "outside the app", "whatsapp me", "cash in hand"]


def _flag_reason(content: str) -> str | None:
    if _PHONE_RE.search(content):
        return "possible phone number shared"
    if _EMAIL_RE.search(content):
        return "possible external email shared"
    lowered = content.lower()
    for phrase in _SUSPICIOUS_PHRASES:
        if phrase in lowered:
            return f"suspicious phrase: '{phrase}'"
    return None


@router.post("/threads", status_code=status.HTTP_201_CREATED)
def create_thread(payload: ThreadCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    thread = MessageThread(
        project_id=payload.project_id,
        student_user_id=user.id if user.role.value == "student" else payload.other_user_id,
        business_user_id=payload.other_user_id if user.role.value == "student" else user.id,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return {"thread_id": thread.id}


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(payload: MessageCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    thread = db.query(MessageThread).filter(MessageThread.id == payload.thread_id).first()
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    if user.id not in (thread.student_user_id, thread.business_user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not part of this conversation")

    reason = _flag_reason(payload.content)
    message = Message(
        thread_id=thread.id,
        sender_user_id=user.id,
        content=payload.content,
        is_flagged=reason is not None,
        flagged_reason=reason,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    recipient_id = thread.business_user_id if user.id == thread.student_user_id else thread.student_user_id
    notify_from_template(db, recipient_id, "new_message", sender_name=user.full_name)
    return message


@router.get("/threads", response_model=list[ThreadSummaryOut])
def get_my_threads(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every thread this user is part of, newest activity first — there's no
    other way to discover a thread id otherwise."""
    threads = (
        db.query(MessageThread)
        .filter((MessageThread.student_user_id == user.id) | (MessageThread.business_user_id == user.id))
        .all()
    )

    results = []
    for thread in threads:
        counterpart_id = thread.business_user_id if user.id == thread.student_user_id else thread.student_user_id
        counterpart = db.query(User).filter(User.id == counterpart_id).first()
        last_message = (
            db.query(Message)
            .filter(Message.thread_id == thread.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        unread_count = (
            db.query(Message)
            .filter(Message.thread_id == thread.id, Message.sender_user_id != user.id, Message.is_read == False)  # noqa: E712
            .count()
        )
        results.append(
            ThreadSummaryOut(
                thread_id=thread.id,
                project_id=thread.project_id,
                counterpart_user_id=counterpart_id,
                counterpart_name=counterpart.full_name if counterpart else "Unknown",
                last_message_preview=(last_message.content[:140] if last_message else None),
                last_message_at=last_message.created_at if last_message else None,
                unread_count=unread_count,
            )
        )
    results.sort(key=lambda r: r.last_message_at or datetime.min, reverse=True)
    return results


@router.get("/threads/{thread_id}", response_model=list[MessageOut])
def get_thread_messages(thread_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    thread = db.query(MessageThread).filter(MessageThread.id == thread_id).first()
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    if user.id not in (thread.student_user_id, thread.business_user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not part of this conversation")
    return db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at).all()
