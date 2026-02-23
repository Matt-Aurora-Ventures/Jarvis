export function getAutonomyReadToken(): string {
  return String(
    process.env.NEXT_PUBLIC_AUTONOMY_READ_TOKEN
    || '',
  ).trim();
}

export function getAutonomyTelemetryToken(): string {
  return String(
    process.env.NEXT_PUBLIC_AUTONOMY_TELEMETRY_TOKEN
    || '',
  ).trim();
}

export function buildAutonomyReadHeaders(initial?: HeadersInit): Headers {
  const headers = new Headers(initial || undefined);
  const token = getAutonomyReadToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return headers;
}

export function buildAutonomyTelemetryHeaders(initial?: HeadersInit): Headers {
  const headers = new Headers(initial || undefined);
  const token = getAutonomyTelemetryToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return headers;
}
