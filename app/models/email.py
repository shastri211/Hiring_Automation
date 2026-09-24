from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base import Base

class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    subject = Column(String(255), nullable=False)
    body_content = Column(Text, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint('resume_id', 'template_id', name='uq_email_resume_template'),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    
    subject = Column(String(255), nullable=False)
    body_content = Column(Text, nullable=False)
    
    status = Column(String(50), default="PENDING", index=True) # PENDING, SENT, FAILED
    provider_message_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    # Set only when the sender explicitly typed a test recipient at send
    # time (see BulkEmailRequest.override_recipient_email) - redirects
    # actual delivery there instead of the candidate's own email, and skips
    # the test-allowlist check in process_send_email_task, since an address
    # someone just typed into the send form is inherently one they control
    # right now, unlike an address scraped off a resume.
    override_recipient_email = Column(String(255), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Internal bookkeeping, not exposed via the API. Set (and committed)
    # right before calling the SMTP provider, so a crash between a
    # successful send and the SENT commit leaves this set with status still
    # PENDING - process_send_email_task treats that combination as
    # ambiguous on the next pickup (crashed mid-send vs. still genuinely in
    # flight are indistinguishable) and fails safe rather than risking a
    # real double-send to the candidate.
    send_attempt_started_at = Column(DateTime(timezone=True), nullable=True)
