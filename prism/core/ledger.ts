import { AuditRecord } from "../schemas/audit.js";
import { JournalEntry } from "../schemas/journal.js";

export interface DecisionLedger {
  recordJournal(entry: JournalEntry): void;
  recordAudit(record: AuditRecord): void;
  listJournals(): JournalEntry[];
  listAudits(): AuditRecord[];
}

export class InMemoryDecisionLedger implements DecisionLedger {
  private journals: JournalEntry[] = [];
  private audits: AuditRecord[] = [];

  recordJournal(entry: JournalEntry): void {
    this.journals.push(entry);
  }

  recordAudit(record: AuditRecord): void {
    this.audits.push(record);
  }

  listJournals(): JournalEntry[] {
    return [...this.journals];
  }

  listAudits(): AuditRecord[] {
    return [...this.audits];
  }
}
