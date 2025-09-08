"""
Database handling for privacy settings.

This module provides the database interface for storing and retrieving privacy settings.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (Boolean, Column, DateTime, Integer, String, Text,
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
    disallow_photo = Column(Boolean, default=False)
    disallow_gender = Column(Boolean, default=False)
    disallow_birthday = Column(Boolean, default=False)
    disallow_address = Column(Boolean, default=False)
    disallow_company = Column(Boolean, default=False)
    disallow_title = Column(Boolean, default=False)


class PrivacyLog(Base):
    """Privacy logging model for statistics and audit trail."""

    __tablename__ = "privacy_logs"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    user_identifier = Column(String(255), nullable=True)  # NULL for system logs
    action_type = Column(String(50), nullable=False)  # e.g., 'settings_retrieved', 'settings_created', 'vcard_processed'
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # JSON string for additional structured data
    log_level = Column(String(10), default='INFO')  # INFO, DEBUG, WARNING, ERROR


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
                    "disallow_photo": self._configuration.get("privacy", "default_disallow_photo"),
                    "disallow_gender": self._configuration.get("privacy", "default_disallow_gender"),
                    "disallow_birthday": self._configuration.get("privacy", "default_disallow_birthday"),
                    "disallow_address": self._configuration.get("privacy", "default_disallow_address"),
                    "disallow_company": self._configuration.get("privacy", "default_disallow_company"),
                    "disallow_title": self._configuration.get("privacy", "default_disallow_title"),
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

    def log_action(self, action_type: str, message: str, user_identifier: Optional[str] = None,
                   details: Optional[Dict[str, Any]] = None, log_level: str = 'INFO') -> None:
        """Log a privacy-related action to the database.

        Args:
            action_type: Type of action (e.g., 'settings_retrieved', 'vcard_processed')
            message: Human-readable log message
            user_identifier: User identifier (email/phone) if applicable
            details: Additional structured data as dictionary
            log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        """
        # Check if database logging is disabled
        if not self._configuration.get("privacy", "database_logging"):
            return

        session = self.Session()
        try:
            details_json = json.dumps(details) if details else None

            log_entry = PrivacyLog(
                timestamp=datetime.now(timezone.utc),
                user_identifier=user_identifier,
                action_type=action_type,
                message=message,
                details=details_json,
                log_level=log_level
            )

            session.add(log_entry)
            session.commit()
        except Exception:
            # Don't let logging failures break the main functionality
            session.rollback()
            # Could add a fallback logger here if needed
        finally:
            session.close()

    def log_settings_action(self, action: str, user_identifier: str, settings: Optional[Dict[str, bool]] = None) -> None:
        """Log a privacy settings action.

        Args:
            action: Action type ('retrieved', 'created', 'updated', 'deleted')
            user_identifier: User identifier
            settings: Settings dictionary if applicable
        """
        action_type = f"settings_{action}"
        message = f"Privacy settings {action} for {user_identifier}"
        details = {"settings": settings} if settings else None

        self.log_action(action_type, message, user_identifier, details)

    def log_vcard_action(self, action: str, user_identifier: str, vcard_uid: Optional[str] = None,
                         collection_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """Log a vCard processing action.

        Args:
            action: Action type ('processed', 'reprocessed', 'found')
            user_identifier: User identifier
            vcard_uid: vCard UID if applicable
            collection_path: Collection path if applicable
            details: Additional details
        """
        action_type = f"vcard_{action}"
        message = f"vCard {action} for {user_identifier}"
        if vcard_uid:
            message += f" (UID: {vcard_uid})"
        if collection_path:
            message += f" in {collection_path}"

        log_details = details or {}
        if vcard_uid:
            log_details["vcard_uid"] = vcard_uid
        if collection_path:
            log_details["collection_path"] = collection_path

        self.log_action(action_type, message, user_identifier, log_details)

    def log_auth_action(self, action: str, user_identifier: str, auth_method: str = "token",
                        details: Optional[Dict[str, Any]] = None) -> None:
        """Log an authentication action.

        Args:
            action: Action type ('success', 'failure', 'jwt_validated')
            user_identifier: User identifier
            auth_method: Authentication method used
            details: Additional details
        """
        action_type = f"auth_{action}"
        message = f"Authentication {action} for {user_identifier} via {auth_method}"

        log_details = details or {}
        log_details["auth_method"] = auth_method

        self.log_action(action_type, message, user_identifier, log_details)

    def get_user_activity_stats(self, user_identifier: str, days: int = 30) -> Dict[str, Any]:
        """Get activity statistics for a specific user.

        Args:
            user_identifier: User identifier
            days: Number of days to look back

        Returns:
            Dictionary with activity statistics
        """
        session = self.Session()
        try:
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get all logs for this user in the time period
            logs = session.query(PrivacyLog).filter(
                PrivacyLog.user_identifier == user_identifier,
                PrivacyLog.timestamp >= cutoff_date
            ).all()

            # Count by action type
            action_counts: Dict[str, int] = {}
            for log in logs:
                action_counts[log.action_type] = action_counts.get(log.action_type, 0) + 1

            # Get recent activity
            recent_logs = session.query(PrivacyLog).filter(
                PrivacyLog.user_identifier == user_identifier,
                PrivacyLog.timestamp >= cutoff_date
            ).order_by(PrivacyLog.timestamp.desc()).limit(10).all()

            return {
                "user_identifier": user_identifier,
                "period_days": days,
                "total_actions": len(logs),
                "action_counts": action_counts,
                "recent_activity": [
                    {
                        "timestamp": log.timestamp.isoformat(),
                        "action_type": log.action_type,
                        "message": log.message
                    }
                    for log in recent_logs
                ]
            }
        finally:
            session.close()

    def get_system_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get system-wide privacy statistics.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with system statistics
        """
        session = self.Session()
        try:
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get all logs in the time period
            logs = session.query(PrivacyLog).filter(
                PrivacyLog.timestamp >= cutoff_date
            ).all()

            # Count by action type
            action_counts: Dict[str, int] = {}
            user_counts: Dict[str, int] = {}
            for log in logs:
                action_counts[log.action_type] = action_counts.get(log.action_type, 0) + 1
                if log.user_identifier:
                    user_counts[log.user_identifier] = user_counts.get(log.user_identifier, 0) + 1

            # Get most active users
            most_active_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            return {
                "period_days": days,
                "total_actions": len(logs),
                "unique_users": len(user_counts),
                "action_counts": action_counts,
                "most_active_users": [
                    {"user": user, "actions": count}
                    for user, count in most_active_users
                ]
            }
        finally:
            session.close()

    def cleanup_old_logs(self, days: int = 90) -> int:
        """Clean up old log entries to prevent database bloat.

        Args:
            days: Keep logs newer than this many days

        Returns:
            Number of deleted log entries
        """
        session = self.Session()
        try:
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Count logs to be deleted
            count = session.query(PrivacyLog).filter(
                PrivacyLog.timestamp < cutoff_date
            ).count()

            # Delete old logs
            session.query(PrivacyLog).filter(
                PrivacyLog.timestamp < cutoff_date
            ).delete()

            session.commit()
            return count
        finally:
            session.close()
