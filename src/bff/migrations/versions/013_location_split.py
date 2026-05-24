"""split location into city/state/country columns

Revision ID: 013_location_split
Revises: 012_schema_cleanup
Create Date: 2026-05-24 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '013_location_split'
down_revision: Union[str, None] = '012_schema_cleanup'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match the map in file_processor/service.py
_LOCATION_MAP: dict[str, tuple[str, str, str]] = {
    "New York": ("New York", "NY", "US"),
    "London": ("London", "", "GB"),
    "Chicago": ("Chicago", "IL", "US"),
    "Boston": ("Boston", "MA", "US"),
    "Dallas": ("Dallas", "TX", "US"),
    "Miami": ("Miami", "FL", "US"),
    "Seattle": ("Seattle", "WA", "US"),
    "Denver": ("Denver", "CO", "US"),
    "San Francisco": ("San Francisco", "CA", "US"),
    "Los Angeles": ("Los Angeles", "CA", "US"),
    "Austin": ("Austin", "TX", "US"),
    "Atlanta": ("Atlanta", "GA", "US"),
    "Portland": ("Portland", "OR", "US"),
    "Phoenix": ("Phoenix", "AZ", "US"),
    "Toronto": ("Toronto", "ON", "CA"),
    "Iran": ("", "", "Iran"),
    "North Korea": ("", "", "North Korea"),
    "Syria": ("", "", "Syria"),
    "Crimea": ("", "", "Crimea"),
    "Cayman": ("George Town", "", "Cayman Islands"),
    "NY": ("New York", "NY", "US"),
    "CA": ("", "CA", "US"),
    "MA": ("", "MA", "US"),
    "TX": ("", "TX", "US"),
    "LA": ("Los Angeles", "CA", "US"),
    "XX": ("", "", ""),
}


def upgrade() -> None:
    op.add_column("transaction", sa.Column("city", sa.String(), nullable=True))
    op.add_column("transaction", sa.Column("state", sa.String(), nullable=True))
    op.add_column("transaction", sa.Column("country", sa.String(), nullable=True))

    # Backfill from existing location column
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, location FROM \"transaction\"")).fetchall()
    for row_id, loc_val in rows:
        if loc_val:
            entry = _LOCATION_MAP.get(loc_val)
            if entry:
                city, state, country = entry
                conn.execute(
                    sa.text(
                        "UPDATE \"transaction\" SET city = :city, state = :state, country = :country WHERE id = :id"
                    ),
                    {"city": city, "state": state, "country": country, "id": row_id},
                )
            else:
                # Unknown location — store as raw city
                conn.execute(
                    sa.text(
                        "UPDATE \"transaction\" SET city = :city WHERE id = :id"
                    ),
                    {"city": loc_val, "id": row_id},
                )

    op.drop_column("transaction", "location")


def downgrade() -> None:
    op.add_column("transaction", sa.Column("location", sa.String(), nullable=True))

    # Reverse: reconstruct location from city/state/country
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, city, state, country FROM \"transaction\""
    )).fetchall()
    for row_id, city, state, country in rows:
        # Prefer city if available, else country
        loc = city or country or ""
        conn.execute(
            sa.text("UPDATE \"transaction\" SET location = :loc WHERE id = :id"),
            {"loc": loc, "id": row_id},
        )

    op.drop_column("transaction", "country")
    op.drop_column("transaction", "state")
    op.drop_column("transaction", "city")
