"""Role-Based Access Control (RBAC) system."""
from typing import Dict, Set, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """System permissions."""
    # Read permissions
    READ_TRADES = "trades:read"
    READ_POSITIONS = "positions:read"
    READ_BALANCE = "balance:read"
    READ_CONFIG = "config:read"
    READ_LOGS = "logs:read"
    READ_USERS = "users:read"
    
    # Write permissions
    WRITE_TRADES = "trades:write"
    WRITE_CONFIG = "config:write"
    WRITE_USERS = "users:write"
    
    # Execute permissions
    EXECUTE_TRADES = "trades:execute"
    EXECUTE_BACKTEST = "backtest:execute"
    EXECUTE_AUTOMATION = "automation:execute"
    
    # Admin permissions
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"
    ADMIN_SECRETS = "admin:secrets"


class Role(str, Enum):
    """Pre-defined roles."""
    VIEWER = "viewer"
    TRADER = "trader"
    ANALYST = "analyst"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.VIEWER: {
        Permission.READ_TRADES,
        Permission.READ_POSITIONS,
        Permission.READ_BALANCE,
    },
    Role.TRADER: {
        Permission.READ_TRADES,
        Permission.READ_POSITIONS,
        Permission.READ_BALANCE,
        Permission.WRITE_TRADES,
        Permission.EXECUTE_TRADES,
    },
    Role.ANALYST: {
        Permission.READ_TRADES,
        Permission.READ_POSITIONS,
        Permission.READ_BALANCE,
        Permission.READ_CONFIG,
        Permission.EXECUTE_BACKTEST,
    },
    Role.ADMIN: {
        Permission.READ_TRADES,
        Permission.READ_POSITIONS,
        Permission.READ_BALANCE,
        Permission.READ_CONFIG,
        Permission.READ_LOGS,
        Permission.READ_USERS,
        Permission.WRITE_TRADES,
        Permission.WRITE_CONFIG,
        Permission.EXECUTE_TRADES,
        Permission.EXECUTE_BACKTEST,
        Permission.EXECUTE_AUTOMATION,
        Permission.ADMIN_USERS,
    },
    Role.SUPER_ADMIN: set(Permission),  # All permissions
}


@dataclass
class User:
    """User with roles and permissions."""
    id: str
    username: str
    roles: Set[Role] = field(default_factory=set)
    extra_permissions: Set[Permission] = field(default_factory=set)
    denied_permissions: Set[Permission] = field(default_factory=set)
    
    def get_permissions(self) -> Set[Permission]:
        """Get all effective permissions."""
        permissions = set()
        
        # Add permissions from roles
        for role in self.roles:
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        
        # Add extra permissions
        permissions.update(self.extra_permissions)
        
        # Remove denied permissions
        permissions -= self.denied_permissions
        
        return permissions
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in self.get_permissions()
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if user has any of the permissions."""
        user_perms = self.get_permissions()
        return any(p in user_perms for p in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """Check if user has all of the permissions."""
        user_perms = self.get_permissions()
        return all(p in user_perms for p in permissions)
    
    def has_role(self, role: Role) -> bool:
        """Check if user has a role."""
        return role in self.roles


class RBACManager:
    """Manage RBAC policies."""
    
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._resource_policies: Dict[str, Set[Permission]] = {}
    
    def register_user(self, user: User):
        """Register a user."""
        self._users[user.id] = user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)
    
    def assign_role(self, user_id: str, role: Role):
        """Assign a role to a user."""
        if user_id in self._users:
            self._users[user_id].roles.add(role)
            logger.info(f"Assigned role {role.value} to user {user_id}")
    
    def revoke_role(self, user_id: str, role: Role):
        """Revoke a role from a user."""
        if user_id in self._users:
            self._users[user_id].roles.discard(role)
            logger.info(f"Revoked role {role.value} from user {user_id}")
    
    def grant_permission(self, user_id: str, permission: Permission):
        """Grant extra permission to user."""
        if user_id in self._users:
            self._users[user_id].extra_permissions.add(permission)
    
    def deny_permission(self, user_id: str, permission: Permission):
        """Explicitly deny a permission."""
        if user_id in self._users:
            self._users[user_id].denied_permissions.add(permission)
    
    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has permission."""
        user = self._users.get(user_id)
        if not user:
            return False
        return user.has_permission(permission)
    
    def set_resource_policy(self, resource: str, required_permissions: Set[Permission]):
        """Set required permissions for a resource."""
        self._resource_policies[resource] = required_permissions
    
    def can_access_resource(self, user_id: str, resource: str) -> bool:
        """Check if user can access a resource."""
        if resource not in self._resource_policies:
            return True  # No policy = open access
        
        user = self._users.get(user_id)
        if not user:
            return False
        
        required = self._resource_policies[resource]
        return user.has_any_permission(list(required))


# Global RBAC manager
rbac = RBACManager()


def require_permission(*permissions: Permission):
    """Decorator to require permissions for a function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get user_id from kwargs or first arg
            user_id = kwargs.get('user_id') or (args[0] if args else None)
            
            if not user_id:
                raise PermissionError("No user context")
            
            user = rbac.get_user(user_id)
            if not user:
                raise PermissionError("User not found")
            
            if not user.has_any_permission(list(permissions)):
                raise PermissionError(f"Missing required permission: {permissions}")
            
            return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id') or (args[0] if args else None)
            
            if not user_id:
                raise PermissionError("No user context")
            
            user = rbac.get_user(user_id)
            if not user:
                raise PermissionError("User not found")
            
            if not user.has_any_permission(list(permissions)):
                raise PermissionError(f"Missing required permission: {permissions}")
            
            return await func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


def require_role(*roles: Role):
    """Decorator to require roles for a function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id') or (args[0] if args else None)
            
            if not user_id:
                raise PermissionError("No user context")
            
            user = rbac.get_user(user_id)
            if not user:
                raise PermissionError("User not found")
            
            if not any(user.has_role(role) for role in roles):
                raise PermissionError(f"Missing required role: {roles}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
