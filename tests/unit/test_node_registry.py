"""Unit tests for GUI Node Registry - Phase 1 Foundation.

Tests the core node registration, lifecycle, and pairing functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestNodeModel:
    """Test Node dataclass model."""

    def test_node_creation_basic(self):
        """Test basic node creation with required fields."""
        from core.nodes.registry import Node, NodeStatus, NodeType, NodePlatform

        node = Node(
            id="node_123",
            name="My Desktop",
            type=NodeType.GUI,
            platform=NodePlatform.WINDOWS,
            status=NodeStatus.ONLINE,
            capabilities=["browser", "filesystem", "shell"],
            last_seen=datetime.now(),
            ip_address="192.168.1.100",
            user_id=12345
        )

        assert node.id == "node_123"
        assert node.name == "My Desktop"
        assert node.type == NodeType.GUI
        assert node.platform == NodePlatform.WINDOWS
        assert node.status == NodeStatus.ONLINE
        assert "browser" in node.capabilities
        assert node.user_id == 12345

    def test_node_creation_with_connection_info(self):
        """Test node creation with WebSocket connection info."""
        from core.nodes.registry import Node, NodeStatus, NodeType, NodePlatform

        node = Node(
            id="node_456",
            name="Linux Server",
            type=NodeType.HEADLESS,
            platform=NodePlatform.LINUX,
            status=NodeStatus.PENDING,
            capabilities=["shell"],
            last_seen=datetime.now(),
            ip_address="10.0.0.5",
            user_id=12345,
            connection_info={"ws_url": "ws://10.0.0.5:8765", "auth_token": "abc123"}
        )

        assert node.connection_info["ws_url"] == "ws://10.0.0.5:8765"
        assert node.status == NodeStatus.PENDING

    def test_node_status_enum(self):
        """Test NodeStatus enum values."""
        from core.nodes.registry import NodeStatus

        assert NodeStatus.ONLINE.value == "online"
        assert NodeStatus.OFFLINE.value == "offline"
        assert NodeStatus.PENDING.value == "pending"
        assert NodeStatus.PAIRING.value == "pairing"

    def test_node_type_enum(self):
        """Test NodeType enum values."""
        from core.nodes.registry import NodeType

        assert NodeType.GUI.value == "gui"
        assert NodeType.HEADLESS.value == "headless"
        assert NodeType.MOBILE.value == "mobile"

    def test_node_platform_enum(self):
        """Test NodePlatform enum values."""
        from core.nodes.registry import NodePlatform

        assert NodePlatform.WINDOWS.value == "windows"
        assert NodePlatform.LINUX.value == "linux"
        assert NodePlatform.MACOS.value == "macos"
        assert NodePlatform.ANDROID.value == "android"
        assert NodePlatform.IOS.value == "ios"


class TestNodeRegistry:
    """Test NodeRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh NodeRegistry instance."""
        from core.nodes.registry import NodeRegistry
        return NodeRegistry()

    @pytest.fixture
    def sample_node_info(self):
        """Sample node registration info."""
        from core.nodes.registry import NodeType, NodePlatform
        return {
            "name": "Test Node",
            "type": NodeType.GUI,
            "platform": NodePlatform.WINDOWS,
            "capabilities": ["browser", "filesystem"],
            "ip_address": "192.168.1.50",
            "user_id": 12345
        }

    def test_register_node(self, registry, sample_node_info):
        """Test registering a new node."""
        node = registry.register_node(**sample_node_info)

        assert node.id is not None
        assert len(node.id) > 0
        assert node.name == "Test Node"
        assert node.user_id == 12345

    def test_register_node_generates_unique_id(self, registry, sample_node_info):
        """Test that register_node generates unique IDs."""
        node1 = registry.register_node(**sample_node_info)
        node2 = registry.register_node(**sample_node_info)

        assert node1.id != node2.id

    def test_get_node(self, registry, sample_node_info):
        """Test retrieving a node by ID."""
        node = registry.register_node(**sample_node_info)

        retrieved = registry.get_node(node.id)

        assert retrieved is not None
        assert retrieved.id == node.id
        assert retrieved.name == node.name

    def test_get_node_not_found(self, registry):
        """Test getting a non-existent node."""
        result = registry.get_node("nonexistent_id")
        assert result is None

    def test_list_nodes_all(self, registry, sample_node_info):
        """Test listing all nodes."""
        registry.register_node(**sample_node_info)
        registry.register_node(**{**sample_node_info, "name": "Node 2"})

        nodes = registry.list_nodes()

        assert len(nodes) == 2

    def test_list_nodes_by_status(self, registry, sample_node_info):
        """Test listing nodes filtered by status."""
        from core.nodes.registry import NodeStatus

        node1 = registry.register_node(**sample_node_info)
        registry.update_status(node1.id, NodeStatus.ONLINE)

        node2 = registry.register_node(**{**sample_node_info, "name": "Node 2"})
        registry.update_status(node2.id, NodeStatus.OFFLINE)

        online_nodes = registry.list_nodes(status=NodeStatus.ONLINE)

        assert len(online_nodes) == 1
        assert online_nodes[0].id == node1.id

    def test_list_nodes_by_user(self, registry, sample_node_info):
        """Test listing nodes filtered by user ID."""
        registry.register_node(**sample_node_info)  # user 12345
        registry.register_node(**{**sample_node_info, "user_id": 67890})

        user_nodes = registry.list_nodes(user_id=12345)

        assert len(user_nodes) == 1

    def test_update_heartbeat(self, registry, sample_node_info):
        """Test updating node heartbeat timestamp."""
        node = registry.register_node(**sample_node_info)
        old_time = node.last_seen

        # Wait a bit to ensure time difference
        import time
        time.sleep(0.01)

        registry.update_heartbeat(node.id)

        updated = registry.get_node(node.id)
        assert updated.last_seen > old_time

    def test_mark_offline(self, registry, sample_node_info):
        """Test marking a node as offline."""
        from core.nodes.registry import NodeStatus

        node = registry.register_node(**sample_node_info)
        registry.update_status(node.id, NodeStatus.ONLINE)

        registry.mark_offline(node.id)

        updated = registry.get_node(node.id)
        assert updated.status == NodeStatus.OFFLINE

    def test_update_status(self, registry, sample_node_info):
        """Test updating node status."""
        from core.nodes.registry import NodeStatus

        node = registry.register_node(**sample_node_info)

        registry.update_status(node.id, NodeStatus.ONLINE)
        assert registry.get_node(node.id).status == NodeStatus.ONLINE

        registry.update_status(node.id, NodeStatus.OFFLINE)
        assert registry.get_node(node.id).status == NodeStatus.OFFLINE

    def test_remove_node(self, registry, sample_node_info):
        """Test removing a node."""
        node = registry.register_node(**sample_node_info)

        result = registry.remove_node(node.id)

        assert result is True
        assert registry.get_node(node.id) is None

    def test_remove_nonexistent_node(self, registry):
        """Test removing a non-existent node."""
        result = registry.remove_node("nonexistent_id")
        assert result is False


class TestPairingCode:
    """Test pairing code generation and validation."""

    @pytest.fixture
    def registry(self):
        """Create a fresh NodeRegistry instance."""
        from core.nodes.registry import NodeRegistry
        return NodeRegistry()

    def test_generate_pairing_code(self, registry):
        """Test pairing code generation."""
        code = registry.generate_pairing_code(user_id=12345)

        assert len(code) == 6
        assert code.isupper()
        assert code.isalnum()

    def test_pairing_code_unique(self, registry):
        """Test that pairing codes are unique."""
        codes = [registry.generate_pairing_code(user_id=12345) for _ in range(100)]
        # High probability of uniqueness
        assert len(set(codes)) >= 95

    def test_validate_pairing_code_valid(self, registry):
        """Test validating a valid pairing code."""
        code = registry.generate_pairing_code(user_id=12345)

        result = registry.validate_pairing_code(code)

        assert result is not None
        assert result["user_id"] == 12345

    def test_validate_pairing_code_invalid(self, registry):
        """Test validating an invalid pairing code."""
        result = registry.validate_pairing_code("INVALID")
        assert result is None

    def test_validate_pairing_code_expired(self, registry):
        """Test that expired pairing codes are rejected."""
        code = registry.generate_pairing_code(user_id=12345, ttl_seconds=0)

        # Wait for expiry
        import time
        time.sleep(0.1)

        result = registry.validate_pairing_code(code)
        assert result is None

    def test_pairing_code_consumed_after_use(self, registry):
        """Test that pairing codes can only be used once."""
        code = registry.generate_pairing_code(user_id=12345)

        # First use should succeed
        result1 = registry.validate_pairing_code(code, consume=True)
        assert result1 is not None

        # Second use should fail
        result2 = registry.validate_pairing_code(code)
        assert result2 is None


class TestNodeManager:
    """Test NodeManager class for node lifecycle management."""

    @pytest.fixture
    def manager(self):
        """Create a fresh NodeManager instance."""
        from core.nodes.manager import NodeManager
        return NodeManager()

    @pytest.fixture
    def sample_node_data(self):
        """Sample node pairing data."""
        return {
            "name": "Test Desktop",
            "platform": "windows",
            "type": "gui",
            "capabilities": ["browser", "filesystem", "shell"],
            "ip_address": "192.168.1.100"
        }

    @pytest.mark.asyncio
    async def test_pair_node_success(self, manager, sample_node_data):
        """Test successful node pairing."""
        # Generate pairing code for user
        code = manager.registry.generate_pairing_code(user_id=12345)

        # Pair node with code
        node = await manager.pair_node(code, sample_node_data)

        assert node is not None
        assert node.name == "Test Desktop"
        assert node.user_id == 12345
        assert node.status.value == "pending"

    @pytest.mark.asyncio
    async def test_pair_node_invalid_code(self, manager, sample_node_data):
        """Test pairing with invalid code."""
        node = await manager.pair_node("INVALID", sample_node_data)
        assert node is None

    @pytest.mark.asyncio
    async def test_approve_node(self, manager, sample_node_data):
        """Test approving a pending node."""
        from core.nodes.registry import NodeStatus

        code = manager.registry.generate_pairing_code(user_id=12345)
        node = await manager.pair_node(code, sample_node_data)

        result = await manager.approve_node(node.id, user_id=12345)

        assert result is True
        updated = manager.registry.get_node(node.id)
        assert updated.status == NodeStatus.ONLINE

    @pytest.mark.asyncio
    async def test_approve_node_wrong_user(self, manager, sample_node_data):
        """Test that only the owner can approve a node."""
        code = manager.registry.generate_pairing_code(user_id=12345)
        node = await manager.pair_node(code, sample_node_data)

        # Try to approve as different user
        result = await manager.approve_node(node.id, user_id=99999)

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_node(self, manager, sample_node_data):
        """Test removing a node."""
        code = manager.registry.generate_pairing_code(user_id=12345)
        node = await manager.pair_node(code, sample_node_data)

        result = await manager.remove_node(node.id, user_id=12345)

        assert result is True
        assert manager.registry.get_node(node.id) is None

    @pytest.mark.asyncio
    async def test_get_node_status(self, manager, sample_node_data):
        """Test getting detailed node status."""
        code = manager.registry.generate_pairing_code(user_id=12345)
        node = await manager.pair_node(code, sample_node_data)

        status = await manager.get_node_status(node.id)

        assert status is not None
        assert status["id"] == node.id
        assert status["name"] == "Test Desktop"
        assert "last_seen" in status
        assert "capabilities" in status

    @pytest.mark.asyncio
    async def test_send_command(self, manager, sample_node_data):
        """Test queueing a command for a node."""
        from core.nodes.registry import NodeStatus

        code = manager.registry.generate_pairing_code(user_id=12345)
        node = await manager.pair_node(code, sample_node_data)
        await manager.approve_node(node.id, user_id=12345)

        command_id = await manager.send_command(
            node_id=node.id,
            command="open_browser",
            args={"url": "https://example.com"},
            user_id=12345
        )

        assert command_id is not None

    @pytest.mark.asyncio
    async def test_send_command_to_offline_node(self, manager, sample_node_data):
        """Test that commands to offline nodes are queued."""
        from core.nodes.registry import NodeStatus

        code = manager.registry.generate_pairing_code(user_id=12345)
        node = await manager.pair_node(code, sample_node_data)
        manager.registry.mark_offline(node.id)

        command_id = await manager.send_command(
            node_id=node.id,
            command="test_command",
            args={},
            user_id=12345
        )

        # Command should still be queued even for offline nodes
        assert command_id is not None

    @pytest.mark.asyncio
    async def test_get_pending_commands(self, manager, sample_node_data):
        """Test retrieving pending commands for a node."""
        code = manager.registry.generate_pairing_code(user_id=12345)
        node = await manager.pair_node(code, sample_node_data)
        await manager.approve_node(node.id, user_id=12345)

        await manager.send_command(node.id, "cmd1", {}, user_id=12345)
        await manager.send_command(node.id, "cmd2", {}, user_id=12345)

        commands = await manager.get_pending_commands(node.id)

        assert len(commands) == 2


class TestNodeCapabilities:
    """Test node capability checking."""

    @pytest.fixture
    def registry(self):
        """Create a fresh NodeRegistry instance."""
        from core.nodes.registry import NodeRegistry
        return NodeRegistry()

    def test_check_capability_present(self, registry):
        """Test checking for a present capability."""
        from core.nodes.registry import NodeType, NodePlatform

        node = registry.register_node(
            name="Test Node",
            type=NodeType.GUI,
            platform=NodePlatform.WINDOWS,
            capabilities=["browser", "filesystem"],
            ip_address="192.168.1.1",
            user_id=12345
        )

        assert registry.has_capability(node.id, "browser") is True
        assert registry.has_capability(node.id, "filesystem") is True

    def test_check_capability_absent(self, registry):
        """Test checking for an absent capability."""
        from core.nodes.registry import NodeType, NodePlatform

        node = registry.register_node(
            name="Test Node",
            type=NodeType.HEADLESS,
            platform=NodePlatform.LINUX,
            capabilities=["shell"],
            ip_address="192.168.1.1",
            user_id=12345
        )

        assert registry.has_capability(node.id, "browser") is False

    def test_check_capability_nonexistent_node(self, registry):
        """Test checking capability for non-existent node."""
        result = registry.has_capability("nonexistent", "browser")
        assert result is False


class TestOfflineDetection:
    """Test automatic offline detection."""

    @pytest.fixture
    def registry(self):
        """Create a fresh NodeRegistry instance."""
        from core.nodes.registry import NodeRegistry
        return NodeRegistry()

    def test_detect_stale_nodes(self, registry):
        """Test detecting nodes that haven't sent heartbeat."""
        from core.nodes.registry import NodeType, NodePlatform, NodeStatus

        node = registry.register_node(
            name="Test Node",
            type=NodeType.GUI,
            platform=NodePlatform.WINDOWS,
            capabilities=["browser"],
            ip_address="192.168.1.1",
            user_id=12345
        )
        registry.update_status(node.id, NodeStatus.ONLINE)

        # Manually set last_seen to old time
        node_obj = registry.get_node(node.id)
        node_obj.last_seen = datetime.now() - timedelta(minutes=10)

        stale = registry.get_stale_nodes(timeout_seconds=300)

        assert len(stale) == 1
        assert stale[0].id == node.id

    def test_mark_stale_nodes_offline(self, registry):
        """Test marking stale nodes as offline."""
        from core.nodes.registry import NodeType, NodePlatform, NodeStatus

        node = registry.register_node(
            name="Test Node",
            type=NodeType.GUI,
            platform=NodePlatform.WINDOWS,
            capabilities=["browser"],
            ip_address="192.168.1.1",
            user_id=12345
        )
        registry.update_status(node.id, NodeStatus.ONLINE)

        # Manually set last_seen to old time
        node_obj = registry.get_node(node.id)
        node_obj.last_seen = datetime.now() - timedelta(minutes=10)

        count = registry.mark_stale_offline(timeout_seconds=300)

        assert count == 1
        assert registry.get_node(node.id).status == NodeStatus.OFFLINE
