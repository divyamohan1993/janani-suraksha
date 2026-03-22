"""SQLite persistence for assessment history."""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger("janani.persistence")

DB_PATH = Path("/tmp/janani_assessments.db")  # /tmp for Cloud Run writability


class AssessmentStore:
    """Thread-safe SQLite store for assessment results."""

    def __init__(self, db_path: str = str(DB_PATH)):
        self._db_path = db_path
        self._lock = Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assessments (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    mother_name TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    hemoglobin REAL,
                    bp_systolic INTEGER,
                    bp_diastolic INTEGER,
                    gestational_weeks INTEGER,
                    predicted_delivery_hb REAL,
                    referral_facility TEXT,
                    action_taken TEXT,
                    raw_result TEXT
                )
            """)
            conn.commit()
            conn.close()
            logger.info(f"Assessment store initialized at {self._db_path}")

    def save(self, assessment: dict) -> None:
        """Save an assessment result."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                risk = assessment.get("risk", {})
                anemia = assessment.get("anemia") or {}
                referral = assessment.get("referral") or {}

                # Determine action taken
                action = "Routine follow-up scheduled"
                if risk.get("risk_level") == "critical":
                    action = "Emergency referral — ambulance dispatched"
                elif risk.get("risk_level") == "high":
                    action = f"Referred to {referral.get('facility_name', 'nearest facility')}"
                elif risk.get("risk_level") == "medium":
                    action = "IFA compliance counseling, recheck in 2 weeks"

                conn.execute("""
                    INSERT OR REPLACE INTO assessments
                    (id, timestamp, mother_name, risk_level, risk_score, hemoglobin,
                     bp_systolic, bp_diastolic, gestational_weeks, predicted_delivery_hb,
                     referral_facility, action_taken, raw_result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    assessment.get("assessment_id", ""),
                    assessment.get("timestamp", datetime.now().isoformat()),
                    assessment.get("mother_name", "Unknown"),
                    risk.get("risk_level", "unknown"),
                    risk.get("risk_score", 0),
                    assessment.get("risk", {}).get("risk_factors_summary", {}).get("hemoglobin"),
                    None, None,  # BP from risk_factors if available
                    None,  # gestational weeks
                    anemia.get("predicted_delivery_hb"),
                    referral.get("facility_name"),
                    action,
                    json.dumps(assessment),
                ))
                conn.commit()
            finally:
                conn.close()

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Get most recent assessments."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT * FROM assessments ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def get_anemia_stats(self) -> dict:
        """Compute anemia statistics from real assessment hemoglobin data."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                # Count assessments that have hemoglobin data
                total = conn.execute(
                    "SELECT COUNT(*) FROM assessments WHERE hemoglobin IS NOT NULL"
                ).fetchone()[0]

                if total == 0:
                    return {
                        "total_assessed_for_anemia": 0,
                        "assessed_prevalence": 0,
                        "assessed_severe": 0,
                        "assessed_moderate": 0,
                        "assessed_mild": 0,
                    }

                # Hb < 11 — anemic
                anemic = conn.execute(
                    "SELECT COUNT(*) FROM assessments WHERE hemoglobin IS NOT NULL AND hemoglobin < 11"
                ).fetchone()[0]

                # Hb < 7 — severe
                severe = conn.execute(
                    "SELECT COUNT(*) FROM assessments WHERE hemoglobin IS NOT NULL AND hemoglobin < 7"
                ).fetchone()[0]

                # Hb 7-9.9 — moderate
                moderate = conn.execute(
                    "SELECT COUNT(*) FROM assessments WHERE hemoglobin IS NOT NULL AND hemoglobin >= 7 AND hemoglobin < 10"
                ).fetchone()[0]

                # Hb 10-10.9 — mild
                mild = conn.execute(
                    "SELECT COUNT(*) FROM assessments WHERE hemoglobin IS NOT NULL AND hemoglobin >= 10 AND hemoglobin < 11"
                ).fetchone()[0]

                return {
                    "total_assessed_for_anemia": total,
                    "assessed_prevalence": round((anemic / total) * 100, 1),
                    "assessed_severe": round((severe / total) * 100, 1),
                    "assessed_moderate": round((moderate / total) * 100, 1),
                    "assessed_mild": round((mild / total) * 100, 1),
                }
            finally:
                conn.close()

    def get_stats(self) -> dict:
        """Get dashboard statistics."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                # Total assessments
                total = conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]

                # Today's assessments
                today = datetime.now().strftime("%Y-%m-%d")
                today_count = conn.execute(
                    "SELECT COUNT(*) FROM assessments WHERE timestamp LIKE ?",
                    (f"{today}%",)
                ).fetchone()[0]

                # Risk distribution
                distribution = {}
                for row in conn.execute(
                    "SELECT risk_level, COUNT(*) as cnt FROM assessments GROUP BY risk_level"
                ):
                    distribution[row[0]] = row[1]

                # High risk count
                high_risk = distribution.get("high", 0) + distribution.get("critical", 0)
                critical = distribution.get("critical", 0)

                return {
                    "total_assessments": total,
                    "today_assessments": today_count,
                    "high_risk": high_risk,
                    "critical_alerts": critical,
                    "risk_distribution": {
                        "low": distribution.get("low", 0),
                        "medium": distribution.get("medium", 0),
                        "high": distribution.get("high", 0),
                        "critical": distribution.get("critical", 0),
                    }
                }
            finally:
                conn.close()
