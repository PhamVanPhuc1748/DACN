"""Desktop session policy, separate from the Flet page tree."""


def refresh_session(cached_user, fetch_account):
    if not cached_user:
        return None
    current = fetch_account(cached_user['id'])
    if current is None or not current['active'] or current['role'] != cached_user['role']:
        return None
    return current
