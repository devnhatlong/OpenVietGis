"""Guard identity unlink atomically with a narrowly scoped runtime function."""

from collections.abc import Sequence

from alembic import op

revision: str = "0003a_identity_unlink_security"
down_revision: str | Sequence[str] | None = "0003_tenant_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep raw DELETE denied to the runtime role. This narrowly scoped function
    # is the only runtime unlink path and serializes all removals for one user.
    op.execute(
        """
        CREATE FUNCTION identity.unlink_identity(p_user_id uuid, p_identity_link_id uuid)
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog
        AS $$
        BEGIN
            IF p_user_id IS NULL OR p_identity_link_id IS NULL
               OR p_user_id IS DISTINCT FROM NULLIF(
                    current_setting('openvietgis.actor_user_id', true), ''
               )::uuid THEN
                RETURN 'not_found';
            END IF;

            PERFORM id FROM identity.users
                WHERE id = p_user_id AND status = 'active'
                FOR NO KEY UPDATE;
            IF NOT FOUND THEN
                RETURN 'not_found';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM identity.identity_links
                WHERE id = p_identity_link_id AND user_id = p_user_id
            ) THEN
                RETURN 'not_found';
            END IF;
            IF (SELECT count(*) FROM identity.identity_links WHERE user_id = p_user_id) <= 1 THEN
                RETURN 'last_identity';
            END IF;

            DELETE FROM identity.identity_links
                WHERE id = p_identity_link_id AND user_id = p_user_id;
            -- Existing FK CASCADE invalidates all sessions of the removed identity.
            RETURN 'unlinked';
        END;
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION identity.unlink_identity(uuid, uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION identity.unlink_identity(uuid, uuid) TO openvietgis_runtime"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS identity.unlink_identity(uuid, uuid)")
