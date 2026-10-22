from sqlalchemy import inspect, text

from app.db.session import Base, engine
from app.models.analysis_cases import AnalysisJob  # noqa: F401
from app.models.property import Property  # noqa: F401
from app.models.user import User  # noqa: F401


def _upgrade_existing_schema(connection) -> None:
    inspector = inspect(connection)
    if "properties" not in inspector.get_table_names():
        return
    if "owner_id" not in {column["name"] for column in inspector.get_columns("properties")}:
        connection.execute(text("ALTER TABLE properties ADD COLUMN owner_id VARCHAR(255)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_properties_owner_id ON properties (owner_id)"))
    if connection.dialect.name == "postgresql":
        foreign_keys = {fk.get("name") for fk in inspect(connection).get_foreign_keys("properties")}
        if "fk_properties_owner_id_users" not in foreign_keys:
            connection.execute(text(
                "ALTER TABLE properties ADD CONSTRAINT fk_properties_owner_id_users "
                "FOREIGN KEY (owner_id) REFERENCES users(user_id)"
            ))


async def ensure_schema() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_upgrade_existing_schema)
