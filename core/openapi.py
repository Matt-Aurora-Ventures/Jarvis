"""
OpenAPI Documentation Generator - Auto-generate API docs from FastAPI/Flask apps.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# === OPENAPI SCHEMA DEFINITIONS ===

@dataclass
class Contact:
    name: str = "Kr8tiv AI"
    url: str = "https://jarvislife.io"
    email: str = "support@kr8tivai.com"


@dataclass
class License:
    name: str = "MIT"
    url: str = "https://opensource.org/licenses/MIT"


@dataclass
class Info:
    title: str = "Jarvis API"
    description: str = "AI Trading Assistant API - Sentiment analysis, trading, and portfolio management"
    version: str = "4.2.0"
    contact: Contact = field(default_factory=Contact)
    license: License = field(default_factory=License)


@dataclass
class Server:
    url: str
    description: str = ""


@dataclass
class Parameter:
    name: str
    in_: str  # query, path, header, cookie
    description: str = ""
    required: bool = False
    schema: Dict = field(default_factory=lambda: {"type": "string"})


@dataclass
class RequestBody:
    description: str = ""
    required: bool = True
    content: Dict = field(default_factory=dict)


@dataclass
class Response:
    description: str
    content: Dict = field(default_factory=dict)


@dataclass
class Operation:
    summary: str
    description: str = ""
    operation_id: str = ""
    tags: List[str] = field(default_factory=list)
    parameters: List[Parameter] = field(default_factory=list)
    request_body: Optional[RequestBody] = None
    responses: Dict[str, Response] = field(default_factory=dict)
    security: List[Dict] = field(default_factory=list)


# === JARVIS API DOCUMENTATION ===

JARVIS_OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Jarvis API",
        "description": """
# Jarvis - AI Trading Assistant API

Jarvis is an open-source autonomous AI trading assistant built for Solana.

## Features

- **Sentiment Analysis**: Real-time market sentiment powered by Grok AI
- **Trading**: Automated trading via Jupiter aggregator
- **Portfolio Management**: Treasury tracking and P&L reporting
- **Alerts**: Telegram and Twitter notifications

## Authentication

Most endpoints require an API key passed in the `X-API-Key` header.

```
X-API-Key: your-api-key-here
```

## Rate Limits

- Default: 100 requests/minute
- Trading endpoints: 10 requests/minute
- Sentiment endpoints: 30 requests/minute

## WebSocket

Real-time updates available at `/ws/updates`

""",
        "version": "4.2.0",
        "contact": {
            "name": "Kr8tiv AI",
            "url": "https://jarvislife.io",
            "email": "support@kr8tivai.com"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    },
    "servers": [
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "https://api.jarvislife.io", "description": "Production"},
    ],
    "tags": [
        {"name": "Health", "description": "System health and status"},
        {"name": "Sentiment", "description": "Market sentiment analysis"},
        {"name": "Trading", "description": "Trade execution"},
        {"name": "Portfolio", "description": "Portfolio and treasury management"},
        {"name": "Tokens", "description": "Token information and analysis"},
        {"name": "Alerts", "description": "Alert configuration"},
        {"name": "Admin", "description": "Administrative endpoints"},
    ],
    "paths": {
        "/health": {
            "get": {
                "summary": "Health check",
                "description": "Check if the API is running",
                "tags": ["Health"],
                "responses": {
                    "200": {
                        "description": "API is healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "healthy"},
                                        "version": {"type": "string", "example": "4.2.0"},
                                        "uptime": {"type": "number", "example": 3600}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/metrics": {
            "get": {
                "summary": "Prometheus metrics",
                "description": "Export metrics in Prometheus format",
                "tags": ["Health"],
                "responses": {
                    "200": {
                        "description": "Metrics in Prometheus format",
                        "content": {
                            "text/plain": {
                                "example": "jarvis_trades_total 42\njarvis_uptime_seconds 3600"
                            }
                        }
                    }
                }
            }
        },
        "/api/sentiment": {
            "get": {
                "summary": "Get market sentiment",
                "description": "Get current market sentiment analysis powered by Grok AI",
                "tags": ["Sentiment"],
                "parameters": [
                    {
                        "name": "tokens",
                        "in": "query",
                        "description": "Number of tokens to analyze (default 10)",
                        "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50}
                    },
                    {
                        "name": "include_macro",
                        "in": "query",
                        "description": "Include macro market analysis",
                        "schema": {"type": "boolean", "default": True}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Sentiment analysis",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SentimentReport"}
                            }
                        }
                    }
                },
                "security": [{"apiKey": []}]
            }
        },
        "/api/sentiment/token/{mint}": {
            "get": {
                "summary": "Get token sentiment",
                "description": "Get sentiment analysis for a specific token",
                "tags": ["Sentiment"],
                "parameters": [
                    {
                        "name": "mint",
                        "in": "path",
                        "required": True,
                        "description": "Token mint address",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Token sentiment",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TokenSentiment"}
                            }
                        }
                    },
                    "404": {"description": "Token not found"}
                },
                "security": [{"apiKey": []}]
            }
        },
        "/api/trading/quote": {
            "post": {
                "summary": "Get swap quote",
                "description": "Get a quote for swapping tokens via Jupiter",
                "tags": ["Trading"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/QuoteRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Swap quote",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/QuoteResponse"}
                            }
                        }
                    },
                    "400": {"description": "Invalid request"}
                },
                "security": [{"apiKey": []}]
            }
        },
        "/api/trading/swap": {
            "post": {
                "summary": "Execute swap",
                "description": "Execute a token swap via Jupiter",
                "tags": ["Trading"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SwapRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Swap executed",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SwapResponse"}
                            }
                        }
                    },
                    "400": {"description": "Invalid request"},
                    "403": {"description": "Spending limit exceeded"},
                    "500": {"description": "Swap failed"}
                },
                "security": [{"apiKey": []}]
            }
        },
        "/api/portfolio": {
            "get": {
                "summary": "Get portfolio",
                "description": "Get current treasury portfolio holdings",
                "tags": ["Portfolio"],
                "responses": {
                    "200": {
                        "description": "Portfolio holdings",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Portfolio"}
                            }
                        }
                    }
                },
                "security": [{"apiKey": []}]
            }
        },
        "/api/portfolio/pnl": {
            "get": {
                "summary": "Get P&L",
                "description": "Get profit/loss summary",
                "tags": ["Portfolio"],
                "parameters": [
                    {
                        "name": "period",
                        "in": "query",
                        "description": "Time period (1d, 7d, 30d, all)",
                        "schema": {"type": "string", "default": "7d"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "P&L summary",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PnLSummary"}
                            }
                        }
                    }
                },
                "security": [{"apiKey": []}]
            }
        },
        "/api/tokens/trending": {
            "get": {
                "summary": "Get trending tokens",
                "description": "Get currently trending Solana tokens",
                "tags": ["Tokens"],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 10, "maximum": 50}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Trending tokens",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/TrendingToken"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/tokens/{mint}": {
            "get": {
                "summary": "Get token info",
                "description": "Get detailed information about a token",
                "tags": ["Tokens"],
                "parameters": [
                    {
                        "name": "mint",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Token information",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TokenInfo"}
                            }
                        }
                    },
                    "404": {"description": "Token not found"}
                }
            }
        },
        "/api/predictions": {
            "get": {
                "summary": "Get predictions",
                "description": "Get recent predictions and their outcomes",
                "tags": ["Sentiment"],
                "parameters": [
                    {
                        "name": "status",
                        "in": "query",
                        "description": "Filter by status",
                        "schema": {"type": "string", "enum": ["pending", "win", "loss", "all"]}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 20}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Predictions list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Prediction"}
                                }
                            }
                        }
                    }
                },
                "security": [{"apiKey": []}]
            }
        },
        "/api/predictions/accuracy": {
            "get": {
                "summary": "Get prediction accuracy",
                "description": "Get prediction accuracy statistics",
                "tags": ["Sentiment"],
                "parameters": [
                    {
                        "name": "days",
                        "in": "query",
                        "schema": {"type": "integer", "default": 7}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Accuracy statistics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AccuracyStats"}
                            }
                        }
                    }
                },
                "security": [{"apiKey": []}]
            }
        }
    },
    "components": {
        "securitySchemes": {
            "apiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key"
            }
        },
        "schemas": {
            "SentimentReport": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string", "format": "date-time"},
                    "overall_sentiment": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                    "tokens": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/TokenSentiment"}
                    },
                    "macro": {"$ref": "#/components/schemas/MacroAnalysis"}
                }
            },
            "TokenSentiment": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "mint": {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reasoning": {"type": "string"},
                    "price": {"type": "number"},
                    "change_24h": {"type": "number"},
                    "volume_24h": {"type": "number"},
                    "targets": {
                        "type": "object",
                        "properties": {
                            "safe": {"type": "number"},
                            "medium": {"type": "number"},
                            "degen": {"type": "number"},
                            "stop_loss": {"type": "number"}
                        }
                    }
                }
            },
            "MacroAnalysis": {
                "type": "object",
                "properties": {
                    "short_term": {"type": "string"},
                    "medium_term": {"type": "string"},
                    "long_term": {"type": "string"},
                    "dxy": {
                        "type": "object",
                        "properties": {
                            "direction": {"type": "string"},
                            "analysis": {"type": "string"}
                        }
                    },
                    "stocks": {
                        "type": "object",
                        "properties": {
                            "direction": {"type": "string"},
                            "analysis": {"type": "string"}
                        }
                    }
                }
            },
            "QuoteRequest": {
                "type": "object",
                "required": ["input_mint", "output_mint", "amount"],
                "properties": {
                    "input_mint": {"type": "string", "description": "Input token mint address"},
                    "output_mint": {"type": "string", "description": "Output token mint address"},
                    "amount": {"type": "number", "description": "Amount in input token"},
                    "slippage_bps": {"type": "integer", "default": 50, "description": "Slippage in basis points"}
                }
            },
            "QuoteResponse": {
                "type": "object",
                "properties": {
                    "input_amount": {"type": "number"},
                    "output_amount": {"type": "number"},
                    "price_impact": {"type": "number"},
                    "route": {"type": "array", "items": {"type": "string"}},
                    "quote_id": {"type": "string"}
                }
            },
            "SwapRequest": {
                "type": "object",
                "required": ["quote_id"],
                "properties": {
                    "quote_id": {"type": "string", "description": "Quote ID from /quote endpoint"},
                    "risk_profile": {"type": "string", "enum": ["safe", "medium", "degen"], "default": "safe"}
                }
            },
            "SwapResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "tx_signature": {"type": "string"},
                    "input_amount": {"type": "number"},
                    "output_amount": {"type": "number"},
                    "price": {"type": "number"}
                }
            },
            "Portfolio": {
                "type": "object",
                "properties": {
                    "wallet": {"type": "string"},
                    "total_value_usd": {"type": "number"},
                    "total_value_sol": {"type": "number"},
                    "positions": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Position"}
                    }
                }
            },
            "Position": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "mint": {"type": "string"},
                    "amount": {"type": "number"},
                    "value_usd": {"type": "number"},
                    "pnl_percent": {"type": "number"},
                    "entry_price": {"type": "number"},
                    "current_price": {"type": "number"}
                }
            },
            "PnLSummary": {
                "type": "object",
                "properties": {
                    "period": {"type": "string"},
                    "total_pnl_usd": {"type": "number"},
                    "total_pnl_percent": {"type": "number"},
                    "winning_trades": {"type": "integer"},
                    "losing_trades": {"type": "integer"},
                    "win_rate": {"type": "number"}
                }
            },
            "TrendingToken": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "mint": {"type": "string"},
                    "price": {"type": "number"},
                    "change_24h": {"type": "number"},
                    "volume_24h": {"type": "number"},
                    "market_cap": {"type": "number"},
                    "buy_sell_ratio": {"type": "number"}
                }
            },
            "TokenInfo": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "name": {"type": "string"},
                    "mint": {"type": "string"},
                    "decimals": {"type": "integer"},
                    "price": {"type": "number"},
                    "market_cap": {"type": "number"},
                    "volume_24h": {"type": "number"},
                    "holders": {"type": "integer"},
                    "logo_url": {"type": "string"}
                }
            },
            "Prediction": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "symbol": {"type": "string"},
                    "prediction_type": {"type": "string"},
                    "confidence": {"type": "number"},
                    "price_at_prediction": {"type": "number"},
                    "target_price": {"type": "number"},
                    "stop_loss": {"type": "number"},
                    "outcome": {"type": "string", "enum": ["pending", "win", "loss"]},
                    "outcome_price": {"type": "number"},
                    "pnl_percent": {"type": "number"}
                }
            },
            "AccuracyStats": {
                "type": "object",
                "properties": {
                    "period_days": {"type": "integer"},
                    "total_predictions": {"type": "integer"},
                    "wins": {"type": "integer"},
                    "losses": {"type": "integer"},
                    "pending": {"type": "integer"},
                    "accuracy_percent": {"type": "number"},
                    "avg_pnl_percent": {"type": "number"},
                    "by_type": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "total": {"type": "integer"},
                                "wins": {"type": "integer"},
                                "accuracy": {"type": "number"}
                            }
                        }
                    }
                }
            }
        }
    }
}


def get_openapi_spec() -> Dict:
    """Get the OpenAPI specification."""
    return JARVIS_OPENAPI_SPEC


def save_openapi_spec(path: Path = None):
    """Save OpenAPI spec to file."""
    if path is None:
        path = Path(__file__).parent.parent / "docs" / "openapi.json"

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(JARVIS_OPENAPI_SPEC, f, indent=2)

    logger.info(f"OpenAPI spec saved to {path}")
    return path


def setup_swagger_ui(app, spec_url: str = "/openapi.json", docs_url: str = "/docs"):
    """Setup Swagger UI for FastAPI app."""
    from fastapi import FastAPI
    from fastapi.openapi.docs import get_swagger_ui_html

    @app.get(spec_url, include_in_schema=False)
    async def openapi_spec():
        return get_openapi_spec()

    @app.get(docs_url, include_in_schema=False)
    async def swagger_ui():
        return get_swagger_ui_html(
            openapi_url=spec_url,
            title="Jarvis API Documentation"
        )

    logger.info(f"Swagger UI available at {docs_url}")
