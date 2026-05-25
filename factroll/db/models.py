import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    oauth_subject = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    profiles = relationship("Profile", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String, nullable=False)
    el = Column(Float, default=0.0, nullable=False)
    last_seen = Column(DateTime)
    contribute_to_corpus = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="profiles")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    default_el = Column(Float, default=0.0, nullable=False)
    is_public = Column(Boolean, default=True, nullable=False)

    facts = relationship("Fact", back_populates="topic", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="topic")


class FactCategory(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class FactSource(str, enum.Enum):
    official = "official"
    community = "community"


class Fact(Base):
    __tablename__ = "facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    category = Column(Enum(FactCategory), nullable=False)
    content = Column(Text, nullable=False)
    why_it_matters = Column(Text)
    reviewed = Column(Boolean, default=False, nullable=False)
    accuracy_score = Column(Float)
    source = Column(Enum(FactSource), default=FactSource.official, nullable=False)
    contributed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    topic = relationship("Topic", back_populates="facts")


class SessionStatus(str, enum.Enum):
    active = "active"
    ended = "ended"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    surface_id = Column(String, nullable=False)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime)
    status = Column(Enum(SessionStatus), default=SessionStatus.active, nullable=False)

    user = relationship("User", back_populates="sessions")
    topic = relationship("Topic", back_populates="sessions")
    fact_events = relationship("FactEvent", back_populates="session", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="session", cascade="all, delete-orphan")


class FactEvent(Base):
    __tablename__ = "fact_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    fact_id = Column(UUID(as_uuid=True), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False)
    shown_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    was_repeat = Column(Boolean, default=False, nullable=False)

    session = relationship("Session", back_populates="fact_events")
    fact = relationship("Fact")


class QuizVerdict(str, enum.Enum):
    correct = "correct"
    incorrect = "incorrect"
    pending = "pending"


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    fact_id = Column(UUID(as_uuid=True), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False)
    locked_answer = Column(Text, nullable=False)
    user_answer = Column(Text)
    verdict = Column(Enum(QuizVerdict), default=QuizVerdict.pending, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("Session", back_populates="quiz_attempts")
    fact = relationship("Fact")
