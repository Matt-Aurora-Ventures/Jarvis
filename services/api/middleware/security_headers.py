"""Security headers middleware."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request
from typing import Dict, Optional


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Implements OWASP recommended security headers:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: max-age=31536000
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    """

    # Default security headers
    DEFAULT_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

    def __init__(
        self,
        app,
        csp_policy: str = None,
        custom_headers: Dict[str, str] = None
    ):
        """
        Initialize security headers middleware.

        Args:
            app: The ASGI application
            csp_policy: Content Security Policy (or None for default)
            custom_headers: Additional custom headers to add
        """
        if app is not None:
            super().__init__(app)
        else:
            # Allow None for testing
            self._app = None

        self.csp_policy = csp_policy or "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        self.custom_headers = custom_headers or {}

    def get_security_headers(self) -> Dict[str, str]:
        """
        Get all security headers as a dictionary.

        Useful for testing and inspection.

        Returns:
            Dict of header name -> value
        """
        headers = dict(self.DEFAULT_HEADERS)
        headers["Content-Security-Policy"] = self.csp_policy

        # Add custom headers
        headers.update(self.custom_headers)

        return headers

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add security headers to response."""
        response = await call_next(request)

        # Add all security headers
        for header, value in self.get_security_headers().items():
            # Only add HSTS for HTTPS requests
            if header == "Strict-Transport-Security" and request.url.scheme != "https":
                continue
            response.headers[header] = value

        return response


def get_recommended_csp(
    allow_inline_scripts: bool = True,
    allow_inline_styles: bool = True,
    allow_eval: bool = False,
    frame_ancestors: str = "'none'",
    report_uri: Optional[str] = None
) -> str:
    """
    Generate a recommended Content Security Policy.

    Args:
        allow_inline_scripts: Allow inline script tags
        allow_inline_styles: Allow inline styles
        allow_eval: Allow eval() (dangerous, avoid if possible)
        frame_ancestors: Who can embed this page
        report_uri: URI to report violations

    Returns:
        CSP policy string
    """
    directives = ["default-src 'self'"]

    # Script source
    script_src = "'self'"
    if allow_inline_scripts:
        script_src += " 'unsafe-inline'"
    if allow_eval:
        script_src += " 'unsafe-eval'"
    directives.append(f"script-src {script_src}")

    # Style source
    style_src = "'self'"
    if allow_inline_styles:
        style_src += " 'unsafe-inline'"
    directives.append(f"style-src {style_src}")

    # Frame ancestors
    directives.append(f"frame-ancestors {frame_ancestors}")

    # Image sources
    directives.append("img-src 'self' data: https:")

    # Font sources
    directives.append("font-src 'self' data:")

    # Connect sources (API calls)
    directives.append("connect-src 'self'")

    # Report URI
    if report_uri:
        directives.append(f"report-uri {report_uri}")

    return "; ".join(directives)
