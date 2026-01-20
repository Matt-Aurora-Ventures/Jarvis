"""
Example: Enhanced Database Connection Pool Usage

Demonstrates:
- Connection pooling with health checks
- Automatic connection recycling
- Pool utilization metrics
- Error recovery with automatic reconnection
"""
import logging
from pathlib import Path
from core.db.pool import DatabaseConfig, Database, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_basic_usage():
    """Basic database operations with pooling."""
    print("\n=== Basic Usage ===")

    db = get_db()

    # Create table
    with db.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT
            )
        """)

    # Insert data
    user_id = db.insert("users", {
        "name": "Alice",
        "email": "alice@example.com"
    })
    logger.info(f"Inserted user with ID: {user_id}")

    # Query data
    user = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    logger.info(f"Fetched user: {dict(user)}")

    # Update
    db.update("users", {"email": "alice.updated@example.com"}, "id = ?", (user_id,))

    # Verify update
    user = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    logger.info(f"Updated user: {dict(user)}")

    # Cleanup
    db.delete("users", "id = ?", (user_id,))


def example_pool_monitoring():
    """Monitor pool statistics and health."""
    print("\n=== Pool Monitoring ===")

    db = get_db()

    # Perform some operations
    with db.connection() as conn:
        conn.execute("SELECT 1")

    # Get pool statistics
    stats = db.get_stats()

    logger.info("Pool Statistics:")
    logger.info(f"  Pool size: {stats['pool_size']}")
    logger.info(f"  Active connections: {stats['active_connections']}")
    logger.info(f"  Available connections: {stats['available_connections']}")
    logger.info(f"  Utilization: {stats['utilization_pct']:.1f}%")
    logger.info(f"  Total created: {stats['connections_created']}")
    logger.info(f"  Total reused: {stats['connections_reused']}")
    logger.info(f"  Total recycled: {stats['connections_recycled']}")

    # Health check
    healthy = db.health_check()
    logger.info(f"Database health: {'OK' if healthy else 'FAILED'}")


def example_custom_config():
    """Use custom pool configuration."""
    print("\n=== Custom Configuration ===")

    config = DatabaseConfig(
        sqlite_path=Path("data/custom.db"),
        pool_size=3,
        max_overflow=2,
        pool_recycle=1800,  # 30 minutes
        health_check_interval=120,  # 2 minutes
        max_retries=5,
        echo=False  # Set to True to log all SQL
    )

    db = Database(config)

    # Create table
    with db.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                price REAL
            )
        """)

    # Batch insert
    products = [
        {"name": "Widget", "price": 9.99},
        {"name": "Gadget", "price": 19.99},
        {"name": "Doohickey", "price": 14.99},
    ]

    for product in products:
        db.insert("products", product)

    # Query all
    results = db.fetchall("SELECT * FROM products ORDER BY price")
    logger.info(f"Products: {[dict(r) for r in results]}")

    stats = db.get_stats()
    logger.info(f"Pool utilization: {stats['utilization_pct']:.1f}%")

    db.disconnect()


def example_concurrent_access():
    """Demonstrate pool handling concurrent requests."""
    print("\n=== Concurrent Access ===")

    from concurrent.futures import ThreadPoolExecutor
    import time

    db = get_db()

    # Setup
    with db.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                value TEXT
            )
        """)
        for i in range(10):
            conn.execute("INSERT INTO items VALUES (?, ?)", (i, f"item_{i}"))

    def worker(worker_id):
        """Simulate concurrent database access."""
        for i in range(5):
            result = db.fetchone(
                "SELECT value FROM items WHERE id = ?",
                (worker_id % 10,)
            )
            time.sleep(0.01)  # Simulate processing
        return worker_id

    # Run concurrent workers
    start = time.time()
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(worker, range(10)))

    elapsed = time.time() - start

    logger.info(f"Completed {len(results)} workers in {elapsed:.2f}s")

    stats = db.get_stats()
    logger.info(f"Connections reused: {stats['connections_reused']}")
    logger.info(f"Peak utilization: {stats['utilization_pct']:.1f}%")


def example_error_recovery():
    """Demonstrate automatic error recovery."""
    print("\n=== Error Recovery ===")

    db = get_db()

    # Setup
    with db.connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")

    # Normal operation
    with db.connection() as conn:
        conn.execute("INSERT INTO test VALUES (1)")

    logger.info("Normal operation succeeded")

    # Force an error (invalid SQL)
    try:
        with db.connection() as conn:
            conn.execute("INVALID SQL")
    except Exception as e:
        logger.error(f"Expected error: {e}")

    # Pool should still work after error
    with db.connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM test")
        count = result.fetchone()[0]
        logger.info(f"Recovery successful, count: {count}")

    stats = db.get_stats()
    logger.info(f"Pool still healthy, utilization: {stats['utilization_pct']:.1f}%")


def example_connection_recycling():
    """Demonstrate automatic connection recycling."""
    print("\n=== Connection Recycling ===")
    import time

    config = DatabaseConfig(
        sqlite_path=Path("data/recycle_test.db"),
        pool_size=2,
        pool_recycle=2,  # Recycle after 2 seconds (normally 3600)
        health_check_interval=1  # Check every second (normally 60)
    )

    db = Database(config)

    # Use connection
    with db.connection() as conn:
        conn.execute("SELECT 1")

    stats = db.get_stats()
    recycled_before = stats["connections_recycled"]
    logger.info(f"Recycled before: {recycled_before}")

    # Wait for connection to age
    logger.info("Waiting for connections to age...")
    time.sleep(2.5)

    # Use connection again - should trigger recycling
    with db.connection() as conn:
        conn.execute("SELECT 1")

    stats = db.get_stats()
    recycled_after = stats["connections_recycled"]
    logger.info(f"Recycled after: {recycled_after}")

    if recycled_after > recycled_before:
        logger.info("Connection successfully recycled based on age")

    db.disconnect()


if __name__ == "__main__":
    print("Database Connection Pool Examples")
    print("=" * 50)

    try:
        example_basic_usage()
        example_pool_monitoring()
        example_custom_config()
        example_concurrent_access()
        example_error_recovery()
        example_connection_recycling()

        print("\n" + "=" * 50)
        print("All examples completed successfully!")

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
