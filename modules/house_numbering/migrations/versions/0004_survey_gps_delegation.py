"""Persist GPS quality evidence for delegated/offline field survey."""

from __future__ import annotations

from alembic import op

revision = "hn_0004_survey_gps_delegation"
down_revision = "hn_0003_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE house_numbering.surveys
        ADD COLUMN gps_accuracy_m double precision NULL,
        ADD COLUMN gps_deviation_m double precision NULL,
        ADD COLUMN warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN payload_fingerprint varchar(64) NULL,
        ADD CONSTRAINT ck_hn_survey_gps_accuracy
            CHECK (gps_accuracy_m IS NULL OR gps_accuracy_m > 0),
        ADD CONSTRAINT ck_hn_survey_gps_deviation
            CHECK (gps_deviation_m IS NULL OR gps_deviation_m >= 0),
        ADD CONSTRAINT ck_hn_survey_payload_fingerprint
            CHECK (payload_fingerprint IS NULL OR length(payload_fingerprint) = 64)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE house_numbering.surveys
        DROP CONSTRAINT IF EXISTS ck_hn_survey_payload_fingerprint,
        DROP CONSTRAINT IF EXISTS ck_hn_survey_gps_deviation,
        DROP CONSTRAINT IF EXISTS ck_hn_survey_gps_accuracy,
        DROP COLUMN payload_fingerprint,
        DROP COLUMN warnings,
        DROP COLUMN gps_deviation_m,
        DROP COLUMN gps_accuracy_m
    """)
