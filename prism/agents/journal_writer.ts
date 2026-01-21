import { JournalEntry } from "../schemas/journal.js";

export class JournalWriter {
  write(entry: Omit<JournalEntry, "timestamp">): JournalEntry {
    return {
      ...entry,
      timestamp: new Date().toISOString(),
    };
  }
}
