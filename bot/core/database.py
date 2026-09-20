import sqlite3
import json
import os
from typing import List, Optional, Dict, Any
from dataclasses import asdict
from datetime import datetime

class Database:
    """Gestor de base de datos SQLite para Jarvis León."""

    def __init__(self, db_path: str = "~/.jarvis/jarvis.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        """Obtener conexión a la BD."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Inicializar tablas."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Tabla de notificaciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                proyecto TEXT,
                proceso TEXT,
                timestamp TEXT,
                estado TEXT,
                resultado TEXT,
                approved_at TEXT,
                approved_by TEXT
            )
        """)

        # Tabla de workflows
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT,
                proyecto TEXT,
                status TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                steps_json TEXT
            )
        """)

        # Tabla de scheduled tasks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                name TEXT,
                proyecto TEXT,
                comando TEXT,
                cron_expression TEXT,
                status TEXT,
                created_at TEXT,
                last_run TEXT,
                run_count INTEGER
            )
        """)

        # Tabla de webhooks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhooks (
                id TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                event_type TEXT,
                proyecto TEXT,
                active INTEGER,
                created_at TEXT
            )
        """)

        # Tabla de metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proyecto TEXT,
                proceso TEXT,
                resultado TEXT,
                timestamp TEXT,
                duration_ms INTEGER
            )
        """)

        conn.commit()
        conn.close()

    def save_notification(self, notif_dict: Dict) -> bool:
        """Guardar notificación."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO notifications
                (id, proyecto, proceso, timestamp, estado, resultado, approved_at, approved_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notif_dict.get('id'),
                notif_dict.get('proyecto'),
                notif_dict.get('proceso'),
                notif_dict.get('timestamp'),
                notif_dict.get('estado'),
                notif_dict.get('resultado'),
                notif_dict.get('approved_at'),
                notif_dict.get('approved_by'),
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving notification: {e}")
            return False

    def save_workflow(self, workflow_dict: Dict) -> bool:
        """Guardar workflow."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO workflows
                (id, name, proyecto, status, created_at, started_at, completed_at, steps_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workflow_dict.get('id'),
                workflow_dict.get('name'),
                workflow_dict.get('proyecto'),
                workflow_dict.get('status'),
                workflow_dict.get('created_at'),
                workflow_dict.get('started_at'),
                workflow_dict.get('completed_at'),
                json.dumps(workflow_dict.get('steps', [])),
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving workflow: {e}")
            return False

    def save_scheduled_task(self, task_dict: Dict) -> bool:
        """Guardar tarea programada."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO scheduled_tasks
                (id, name, proyecto, comando, cron_expression, status, created_at, last_run, run_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_dict.get('id'),
                task_dict.get('name'),
                task_dict.get('proyecto'),
                task_dict.get('comando'),
                task_dict.get('cron_expression'),
                task_dict.get('status'),
                task_dict.get('created_at'),
                task_dict.get('last_run'),
                task_dict.get('run_count', 0),
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving scheduled task: {e}")
            return False

    def save_webhook(self, webhook_dict: Dict) -> bool:
        """Guardar webhook."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO webhooks
                (id, name, url, event_type, proyecto, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                webhook_dict.get('id'),
                webhook_dict.get('name'),
                webhook_dict.get('url'),
                webhook_dict.get('event_type'),
                webhook_dict.get('proyecto'),
                1 if webhook_dict.get('active', True) else 0,
                webhook_dict.get('created_at'),
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving webhook: {e}")
            return False

    def record_metric(self, proyecto: str, proceso: str, resultado: str, duration_ms: int = 0) -> bool:
        """Registrar métrica de ejecución."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO metrics (proyecto, proceso, resultado, timestamp, duration_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (
                proyecto,
                proceso,
                resultado,
                datetime.utcnow().isoformat() + "Z",
                duration_ms,
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error recording metric: {e}")
            return False

    def get_notifications(self, proyecto: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Obtener notificaciones."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if proyecto:
                cursor.execute(
                    "SELECT * FROM notifications WHERE proyecto = ? ORDER BY timestamp DESC LIMIT ?",
                    (proyecto, limit)
                )
            else:
                cursor.execute("SELECT * FROM notifications ORDER BY timestamp DESC LIMIT ?", (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            print(f"Error getting notifications: {e}")
            return []

    def get_workflows(self, proyecto: Optional[str] = None) -> List[Dict]:
        """Obtener workflows."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if proyecto:
                cursor.execute("SELECT * FROM workflows WHERE proyecto = ? ORDER BY created_at DESC", (proyecto,))
            else:
                cursor.execute("SELECT * FROM workflows ORDER BY created_at DESC")

            rows = cursor.fetchall()
            conn.close()

            result = []
            for row in rows:
                d = dict(row)
                d['steps'] = json.loads(d.get('steps_json', '[]'))
                result.append(d)

            return result
        except Exception as e:
            print(f"Error getting workflows: {e}")
            return []

    def delete_notification(self, notif_id: str) -> bool:
        """Eliminar notificación."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting notification: {e}")
            return False
