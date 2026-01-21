export function buildRunId(jobType: string, timestamp: Date = new Date()): string {
  const stamp = timestamp.toISOString().replace(/[-:]/g, "").replace(/\..+/, "Z");
  return `${jobType}-${stamp}`;
}
