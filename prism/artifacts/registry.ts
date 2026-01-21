import { z } from "zod";

export const ArtifactSchema = z.object({
  id: z.string(),
  type: z.string(),
  version: z.number(),
  createdAt: z.string(),
  payload: z.record(z.unknown()),
  links: z.array(z.string()),
});

export type Artifact = z.infer<typeof ArtifactSchema>;

export interface ArtifactRegistry {
  create(type: string, payload: Record<string, unknown>, links?: string[]): Artifact;
  get(id: string): Artifact | undefined;
  list(type?: string): Artifact[];
  link(sourceId: string, targetId: string): void;
}

export class InMemoryArtifactRegistry implements ArtifactRegistry {
  private artifacts = new Map<string, Artifact>();
  private counters = new Map<string, number>();

  create(type: string, payload: Record<string, unknown>, links: string[] = []): Artifact {
    const version = (this.counters.get(type) ?? 0) + 1;
    this.counters.set(type, version);
    const id = `${type}-${version}`;
    const artifact: Artifact = {
      id,
      type,
      version,
      createdAt: new Date().toISOString(),
      payload,
      links,
    };
    this.artifacts.set(id, artifact);
    return artifact;
  }

  get(id: string): Artifact | undefined {
    return this.artifacts.get(id);
  }

  list(type?: string): Artifact[] {
    const values = Array.from(this.artifacts.values());
    if (!type) {
      return values;
    }
    return values.filter((artifact) => artifact.type === type);
  }

  link(sourceId: string, targetId: string): void {
    const source = this.artifacts.get(sourceId);
    const target = this.artifacts.get(targetId);
    if (!source || !target) {
      return;
    }
    source.links = [...new Set([...source.links, targetId])];
    this.artifacts.set(sourceId, source);
  }
}
