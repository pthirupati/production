def is_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)


def is_authenticated(user) -> bool:
    return bool(user and user.is_authenticated)


def can_manage_resource(user, owner) -> bool:
    """
    Owner or admin can manage resource.
    """
    if is_admin(user):
        return True
    return user == owner

