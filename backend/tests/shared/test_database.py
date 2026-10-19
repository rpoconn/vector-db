from pathlib import Path

from sqlalchemy import text

from app.shared.database import Database


async def test_database_creates_parent_dir_and_enforces_foreign_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "app.db"
    database = Database(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    try:
        assert db_path.parent.is_dir()
        async with database.session_factory() as session:
            result = await session.execute(text("PRAGMA foreign_keys"))
            assert result.scalar_one() == 1
    finally:
        await database.dispose()
