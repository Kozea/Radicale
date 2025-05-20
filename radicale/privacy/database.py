"""
Database handling for privacy settings.

This module provides the database interface for storing and retrieving privacy settings.
"""

import os
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import (Boolean, Column, DateTime, Integer, String,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

from radicale import config


class Base(DeclarativeBase):
    pass


class UserSettings(Base):
    """User privacy settings model."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True)  # email or phone
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, onupdate=datetime.now(timezone.utc))

    # Privacy settings fields
    allow_name = Column(Boolean, default=True)
    allow_email = Column(Boolean, default=True)
    allow_phone = Column(Boolean, default=True)
    allow_company = Column(Boolean, default=True)
    allow_title = Column(Boolean, default=True)
    allow_photo = Column(Boolean, default=True)
    allow_birthday = Column(Boolean, default=True)
    allow_address = Column(Boolean, default=True)


class PrivacyDatabase:
    """Class to handle privacy settings database operations."""

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize the database connection.

        Args:
            configuration: The Radicale configuration object
        """
        self._configuration = configuration
        self._database_path = os.path.expanduser(
            configuration.get("privacy", "database_path"))

        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self._database_path)), exist_ok=True)

        # Create engine with SQLite
        self.engine = create_engine(f'sqlite:///{self._database_path}')
        self.Session = scoped_session(sessionmaker(bind=self.engine))

    def close(self):
        """Close all database connections and cleanup resources."""
        self.Session.remove()
        self.engine.dispose()

    def init_db(self):
        """Initialize the database by creating all tables."""
        Base.metadata.create_all(self.engine)

    def get_user_settings(self, identifier: str) -> Optional[UserSettings]:
        """Retrieve user settings by identifier."""
        session = self.Session()
        try:
            return session.query(UserSettings).filter_by(identifier=identifier).first()
        finally:
            session.close()

    def create_user_settings(self, identifier: str, settings: Dict[str, bool]) -> UserSettings:
        """Create new user settings."""
        session = self.Session()
        try:
            # If no settings provided, use configuration defaults
            if not settings:
                settings = {
                    "allow_name": self._configuration.get("privacy", "default_allow_name"),
                    "allow_email": self._configuration.get("privacy", "default_allow_email"),
                    "allow_phone": self._configuration.get("privacy", "default_allow_phone"),
                    "allow_company": self._configuration.get("privacy", "default_allow_company"),
                    "allow_title": self._configuration.get("privacy", "default_allow_title"),
                    "allow_photo": self._configuration.get("privacy", "default_allow_photo"),
                    "allow_birthday": self._configuration.get("privacy", "default_allow_birthday"),
                    "allow_address": self._configuration.get("privacy", "default_allow_address")
                }

            user_settings = UserSettings(
                identifier=identifier,
                **settings
            )
            session.add(user_settings)
            session.commit()
            session.refresh(user_settings)  # Refresh to get all attributes
            return user_settings
        finally:
            session.close()

    def update_user_settings(self, identifier: str, settings: Dict[str, bool]) -> Optional[UserSettings]:
        """Update existing user settings."""
        session = self.Session()
        try:
            user_settings = session.query(UserSettings).filter_by(identifier=identifier).first()
            if user_settings:
                for key, value in settings.items():
                    setattr(user_settings, key, value)
                session.commit()
                session.refresh(user_settings)  # Refresh to get all attributes
                return user_settings
            return None
        finally:
            session.close()

    def delete_user_settings(self, identifier: str) -> bool:
        """Delete user settings by identifier."""
        session = self.Session()
        try:
            user_settings = session.query(UserSettings).filter_by(identifier=identifier).first()
            if user_settings:
                session.delete(user_settings)
                session.commit()
                return True
            return False
        finally:
            session.close()
