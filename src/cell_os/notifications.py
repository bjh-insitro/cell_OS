"""
Notification System

Manages alerts and notifications across different channels.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import sqlite3
import uuid
from pathlib import Path

@dataclass
class Notification:
    """Represents a notification event."""
    notification_id: str
    title: str
    message: str
    level: str = "info"  # info, warning, error, success
    created_at: datetime = field(default_factory=datetime.now)
    read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

class NotificationChannel(ABC):
    """Abstract base class for notification channels."""
    
    @abstractmethod
    def send(self, notification: Notification):
        """Send a notification."""
        pass

class ConsoleChannel(NotificationChannel):
    """Sends notifications to the console/logs."""
    
    def send(self, notification: Notification):
        print(f"[{notification.level.upper()}] {notification.title}: {notification.message}")

class DatabaseChannel(NotificationChannel):
    """Stores notifications in a SQLite database for in-app display."""
    
    def __init__(self, db_path: str = "data/notifications.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                level TEXT NOT NULL,
                created_at TEXT NOT NULL,
                read INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()
        
    def send(self, notification: Notification):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (notification_id, title, message, level, created_at, read, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            notification.notification_id,
            notification.title,
            notification.message,
            notification.level,
            notification.created_at.isoformat(),
            1 if notification.read else 0,
            str(notification.metadata)
        ))
        conn.commit()
        conn.close()
        
    def get_unread(self) -> List[Notification]:
        """Get all unread notifications."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE read = 0 ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_notification(r) for r in rows]
        
    def mark_all_read(self):
        """Mark all notifications as read."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET read = 1 WHERE read = 0")
        conn.commit()
        conn.close()
        
    def _row_to_notification(self, row) -> Notification:
        return Notification(
            notification_id=row[0],
            title=row[1],
            message=row[2],
            level=row[3],
            created_at=datetime.fromisoformat(row[4]),
            read=bool(row[5]),
            metadata={} # Parsing metadata string skipped for simplicity
        )

class NotificationManager:
    """
    Central manager for sending notifications.
    """
    
    def __init__(self):
        self.channels: List[NotificationChannel] = []
        self.channels.append(ConsoleChannel())
        self.db_channel = DatabaseChannel()
        self.channels.append(self.db_channel)
        
    def send(self, title: str, message: str, level: str = "info", metadata: Optional[Dict] = None):
        """Send a notification to all registered channels."""
        notification = Notification(
            notification_id=str(uuid.uuid4()),
            title=title,
            message=message,
            level=level,
            metadata=metadata or {}
        )
        
        for channel in self.channels:
            try:
                channel.send(notification)
            except Exception as e:
                print(f"Failed to send notification to channel {type(channel).__name__}: {e}")
                
    def get_in_app_notifications(self) -> List[Notification]:
        """Get notifications for display in the app."""
        return self.db_channel.get_unread()
        
    def clear_in_app_notifications(self):
        """Clear (mark read) in-app notifications."""
        self.db_channel.mark_all_read()
