"""
Tests for core/jupiter_api.py - Jupiter DEX API wrapper

US-005: bags.fm + Jupiter Backup with TP/SL
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestJupiterAPI:
    """Test JupiterAPI wrapper class."""

    def test_jupiter_api_has_base_url(self):
        """JupiterAPI should have the correct base URL."""
        from core.jupiter_api import JupiterAPI

        assert JupiterAPI.BASE_URL == "https://quote-api.jup.ag/v6"

    @pytest.mark.asyncio
    async def test_get_quote_returns_quote_dict(self):
        """get_quote() should return a quote dict with amounts and route."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "inputMint": "So11111111111111111111111111111111111111112",
                "outputMint": "TOKEN123",
                "inAmount": "1000000000",
                "outAmount": "5000000000",
                "priceImpactPct": "0.1",
                "routePlan": [{"swap": "info"}],
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await api.get_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="TOKEN123",
                amount=1000000000,
                slippage_bps=100,
            )

            assert result is not None
            assert "outAmount" in result or "out_amount" in result or hasattr(result, "out_amount")

    @pytest.mark.asyncio
    async def test_execute_swap_returns_result(self):
        """execute_swap() should return swap result with signature."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_quote = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": "TOKEN123",
            "inAmount": "1000000000",
            "outAmount": "5000000000",
        }

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            # Mock the actual swap execution
            with patch.object(api, '_sign_and_send') as mock_sign:
                mock_sign.return_value = {
                    "success": True,
                    "signature": "tx_sig_123",
                }

                result = await api.execute_swap(
                    quote=mock_quote,
                    user_public_key="user_wallet_123",
                )

                assert result is not None
                assert "success" in result or "signature" in result or "error" in result


class TestJupiterAPIErrorHandling:
    """Test error handling in JupiterAPI."""

    @pytest.mark.asyncio
    async def test_get_quote_returns_none_on_error(self):
        """get_quote() should return None on API error."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_client.get = AsyncMock(side_effect=Exception("API Error"))

            result = await api.get_quote(
                input_mint="SOL",
                output_mint="TOKEN123",
                amount=1000000000,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_execute_swap_returns_error_on_failure(self):
        """execute_swap() should return error dict on failure."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_quote = {"inputMint": "SOL", "outputMint": "TOKEN123"}

        with patch.object(api, '_client') as mock_client:
            mock_client.post = AsyncMock(side_effect=Exception("Swap failed"))

            result = await api.execute_swap(
                quote=mock_quote,
                user_public_key="wallet123",
            )

            assert result is not None
            assert result.get("success") is False or "error" in result


class TestJupiterAPITransactionSimulation:
    """Test transaction simulation in JupiterAPI."""

    @pytest.mark.asyncio
    async def test_simulate_transaction_returns_success_result(self):
        """simulate_transaction() should return success with compute units on valid tx."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        # Mock a successful simulation response
        mock_simulation_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": None,
                    "logs": [
                        "Program 11111111111111111111111111111111 invoke [1]",
                        "Program log: Instruction: Transfer",
                        "Program 11111111111111111111111111111111 consumed 1234 of 200000 compute units",
                        "Program 11111111111111111111111111111111 success",
                    ],
                    "unitsConsumed": 1234,
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_simulation_response)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await api.simulate_transaction("base64_encoded_transaction")

            assert result["success"] is True
            assert result["compute_units"] == 1234
            assert result["error"] is None
            assert "logs" in result

    @pytest.mark.asyncio
    async def test_simulate_transaction_extracts_cu_with_buffer(self):
        """simulate_transaction() should add 10% buffer to compute units."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_simulation_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": None,
                    "logs": [],
                    "unitsConsumed": 10000,
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_simulation_response)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await api.simulate_transaction("base64_encoded_transaction")

            assert result["success"] is True
            # 10000 * 1.1 = 11000
            assert result["compute_units_with_buffer"] == 11000

    @pytest.mark.asyncio
    async def test_simulate_transaction_detects_simulation_failure(self):
        """simulate_transaction() should return failure on simulation error."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_simulation_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": {"InstructionError": [0, "ProgramFailedToComplete"]},
                    "logs": [
                        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [1]",
                        "Program log: Error: insufficient funds",
                        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA failed",
                    ],
                    "unitsConsumed": 500,
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_simulation_response)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await api.simulate_transaction("base64_encoded_transaction")

            assert result["success"] is False
            assert result["error"] is not None
            assert "InstructionError" in str(result["error"]) or "ProgramFailedToComplete" in str(result["error"])

    @pytest.mark.asyncio
    async def test_simulate_transaction_detects_honeypot_transfer_blocked(self):
        """simulate_transaction() should detect honeypot patterns (transfer blocked)."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        # Common honeypot error: transfer blocked by token program
        mock_simulation_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": {"InstructionError": [2, {"Custom": 6}]},
                    "logs": [
                        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [1]",
                        "Program log: Error: Token transfer not allowed",
                        "Program log: Transfer blocked by token authority",
                        "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA failed",
                    ],
                    "unitsConsumed": 100,
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_simulation_response)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await api.simulate_transaction("base64_encoded_transaction")

            assert result["success"] is False
            assert result["is_honeypot"] is True
            assert "honeypot" in result["error"].lower() or "blocked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_simulate_transaction_detects_high_slippage_rug(self):
        """simulate_transaction() should detect potential rug (slippage too high)."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        # Rug pattern: massive slippage in logs indicating manipulated pool
        mock_simulation_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": {"InstructionError": [1, {"Custom": 1}]},
                    "logs": [
                        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 invoke [1]",
                        "Program log: SlippageToleranceExceeded",
                        "Program log: Expected minimum: 1000000, got: 1",
                        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 failed",
                    ],
                    "unitsConsumed": 50000,
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_simulation_response)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await api.simulate_transaction("base64_encoded_transaction")

            assert result["success"] is False
            assert result.get("is_potential_rug") is True or "slippage" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_simulate_transaction_handles_rpc_error(self):
        """simulate_transaction() should handle RPC connection errors gracefully."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

            result = await api.simulate_transaction("base64_encoded_transaction")

            assert result["success"] is False
            assert result["error"] is not None
            assert "Connection" in result["error"] or "refused" in result["error"]

    @pytest.mark.asyncio
    async def test_simulate_transaction_parses_cu_from_logs_fallback(self):
        """simulate_transaction() should parse CU from logs if unitsConsumed missing."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        # Some RPC responses don't include unitsConsumed directly
        mock_simulation_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": None,
                    "logs": [
                        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 invoke [1]",
                        "Program log: Swap executed",
                        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 consumed 75432 of 200000 compute units",
                        "Program JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 success",
                    ],
                    # unitsConsumed intentionally missing
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_simulation_response)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await api.simulate_transaction("base64_encoded_transaction")

            assert result["success"] is True
            assert result["compute_units"] == 75432


class TestJupiterAPIExecuteSwapWithSimulation:
    """Test execute_swap integration with simulation."""

    @pytest.mark.asyncio
    async def test_execute_swap_simulates_before_returning(self):
        """execute_swap() should simulate transaction before returning it."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_quote = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": "TOKEN123",
            "inAmount": "1000000000",
            "outAmount": "5000000000",
            "_raw": {"quoteResponse": "data"},
        }

        # Mock the swap response
        mock_swap_response = {
            "swapTransaction": "YmFzZTY0X3RyYW5zYWN0aW9u",  # base64 encoded
            "lastValidBlockHeight": 123456,
        }

        # Mock the simulation response
        mock_sim_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": None,
                    "logs": [],
                    "unitsConsumed": 50000,
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            # First call: POST to swap endpoint
            # Second call: POST to RPC for simulation
            mock_swap_resp = AsyncMock()
            mock_swap_resp.json = MagicMock(return_value=mock_swap_response)
            mock_swap_resp.raise_for_status = MagicMock()

            mock_sim_resp = AsyncMock()
            mock_sim_resp.json = AsyncMock(return_value=mock_sim_response)

            mock_client.post = AsyncMock(side_effect=[mock_swap_resp, mock_sim_resp])

            result = await api.execute_swap(
                quote=mock_quote,
                user_public_key="user_wallet_123",
                simulate=True,
            )

            assert result is not None
            assert result.get("success") is True
            assert result.get("simulation") is not None
            assert result["simulation"]["success"] is True
            assert result["simulation"]["compute_units"] == 50000

    @pytest.mark.asyncio
    async def test_execute_swap_fails_on_honeypot_detection(self):
        """execute_swap() should fail if simulation detects honeypot."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_quote = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": "HONEYPOT_TOKEN",
            "inAmount": "1000000000",
            "outAmount": "5000000000",
            "_raw": {"quoteResponse": "data"},
        }

        mock_swap_response = {
            "swapTransaction": "YmFzZTY0X3RyYW5zYWN0aW9u",
            "lastValidBlockHeight": 123456,
        }

        # Honeypot simulation response
        mock_sim_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": {"InstructionError": [2, {"Custom": 6}]},
                    "logs": [
                        "Program log: Transfer blocked by token authority",
                    ],
                    "unitsConsumed": 100,
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            mock_swap_resp = AsyncMock()
            mock_swap_resp.json = MagicMock(return_value=mock_swap_response)
            mock_swap_resp.raise_for_status = MagicMock()

            mock_sim_resp = AsyncMock()
            mock_sim_resp.json = AsyncMock(return_value=mock_sim_response)

            mock_client.post = AsyncMock(side_effect=[mock_swap_resp, mock_sim_resp])

            result = await api.execute_swap(
                quote=mock_quote,
                user_public_key="user_wallet_123",
                simulate=True,
            )

            assert result is not None
            assert result.get("success") is False
            assert "honeypot" in result.get("error", "").lower() or "simulation" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_execute_swap_includes_cu_estimate_in_result(self):
        """execute_swap() should include CU estimate with buffer in result."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_quote = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": "TOKEN123",
            "inAmount": "1000000000",
            "outAmount": "5000000000",
            "_raw": {"quoteResponse": "data"},
        }

        mock_swap_response = {
            "swapTransaction": "YmFzZTY0X3RyYW5zYWN0aW9u",
            "lastValidBlockHeight": 123456,
        }

        mock_sim_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456789},
                "value": {
                    "err": None,
                    "logs": [],
                    "unitsConsumed": 80000,
                }
            }
        }

        with patch.object(api, '_client') as mock_client:
            mock_swap_resp = AsyncMock()
            mock_swap_resp.json = MagicMock(return_value=mock_swap_response)
            mock_swap_resp.raise_for_status = MagicMock()

            mock_sim_resp = AsyncMock()
            mock_sim_resp.json = AsyncMock(return_value=mock_sim_response)

            mock_client.post = AsyncMock(side_effect=[mock_swap_resp, mock_sim_resp])

            result = await api.execute_swap(
                quote=mock_quote,
                user_public_key="user_wallet_123",
                simulate=True,
            )

            assert result is not None
            assert result.get("success") is True
            # Should have CU estimate with 10% buffer: 80000 * 1.1 = 88000
            assert result.get("compute_units_estimate") == 88000
