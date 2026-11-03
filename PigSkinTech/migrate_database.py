from services.migration import migrate_sqlite_database


if __name__ == '__main__':
    result = migrate_sqlite_database()
    print(
        f"Migrated {result['users']} accounts and "
        f"{result['inspections']} cases from {result['source']}."
    )
