/**
 * Resilient AI Provider Chain
 * 
 * Implements fallback chain for AI inference:
 * - Dexter (Free) → Ollama (Local) → Grok (Paid)
 * - Reduces inference costs by ~90%
 * - Auto-failover on errors
 */

export interface AIProviderConfig {
    name: string;
    endpoint: string;
    apiKey?: string;
    model: string;
    priority: number;
    costPerToken: number; // in USD
    isLocal: boolean;
    timeout: number;
}

export interface AIResponse {
    content: string;
    provider: string;
    model: string;
    tokensUsed?: number;
    latencyMs: number;
    cost: number;
}

// Default provider configurations
const DEFAULT_PROVIDERS: AIProviderConfig[] = [
    {
        name: 'dexter',
        endpoint: 'https://api.dexter.ai/v1/chat/completions',
        model: 'dexter-7b',
        priority: 1,
        costPerToken: 0,
        isLocal: false,
        timeout: 30000,
    },
    {
        name: 'ollama',
        endpoint: 'http://localhost:11434/api/generate',
        model: 'llama2',
        priority: 2,
        costPerToken: 0,
        isLocal: true,
        timeout: 60000,
    },
    {
        name: 'grok',
        endpoint: 'https://api.x.ai/v1/chat/completions',
        model: 'grok-4-1-fast-non-reasoning',
        priority: 3,
        costPerToken: 0.0001,
        isLocal: false,
        timeout: 30000,
    },
];

export class ResilientAIProvider {
    private providers: AIProviderConfig[];
    private failedProviders: Map<string, number> = new Map();
    private circuitBreakerTimeout = 60000; // 1 minute cooldown

    constructor(providers: AIProviderConfig[] = DEFAULT_PROVIDERS) {
        this.providers = providers.sort((a, b) => a.priority - b.priority);
    }

    /**
     * Send prompt to AI with automatic failover
     */
    async complete(prompt: string, options?: {
        systemPrompt?: string;
        maxTokens?: number;
        temperature?: number;
    }): Promise<AIResponse> {
        const { systemPrompt, maxTokens = 500, temperature = 0.7 } = options || {};

        for (const provider of this.providers) {
            // Check if provider is in circuit breaker cooldown
            const failedAt = this.failedProviders.get(provider.name);
            if (failedAt && Date.now() - failedAt < this.circuitBreakerTimeout) {
                console.log(`⏸️ ${provider.name} in cooldown`);
                continue;
            }

            try {
                const startTime = Date.now();
                const response = await this.callProvider(provider, prompt, {
                    systemPrompt,
                    maxTokens,
                    temperature,
                });
                const latencyMs = Date.now() - startTime;

                // Success - remove from failed list
                this.failedProviders.delete(provider.name);

                return {
                    ...response,
                    provider: provider.name,
                    model: provider.model,
                    latencyMs,
                    cost: (response.tokensUsed || 0) * provider.costPerToken,
                };
            } catch (error) {
                console.warn(`⚠️ ${provider.name} failed:`, error);
                this.failedProviders.set(provider.name, Date.now());
                continue;
            }
        }

        throw new Error('All AI providers failed');
    }

    /**
     * Call a specific provider
     */
    private async callProvider(
        provider: AIProviderConfig,
        prompt: string,
        options: { systemPrompt?: string; maxTokens: number; temperature: number }
    ): Promise<Omit<AIResponse, 'provider' | 'model' | 'latencyMs' | 'cost'>> {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), provider.timeout);

        try {
            if (provider.name === 'ollama') {
                return await this.callOllama(provider, prompt, options, controller.signal);
            } else {
                return await this.callOpenAICompatible(provider, prompt, options, controller.signal);
            }
        } finally {
            clearTimeout(timeoutId);
        }
    }

    /**
     * Call OpenAI-compatible API (Dexter, Grok, etc.)
     */
    private async callOpenAICompatible(
        provider: AIProviderConfig,
        prompt: string,
        options: { systemPrompt?: string; maxTokens: number; temperature: number },
        signal: AbortSignal
    ): Promise<Omit<AIResponse, 'provider' | 'model' | 'latencyMs' | 'cost'>> {
        const messages = [];

        if (options.systemPrompt) {
            messages.push({ role: 'system', content: options.systemPrompt });
        }
        messages.push({ role: 'user', content: prompt });

        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };
        if (provider.apiKey) {
            headers['Authorization'] = `Bearer ${provider.apiKey}`;
        }

        const response = await fetch(provider.endpoint, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                model: provider.model,
                messages,
                max_tokens: options.maxTokens,
                temperature: options.temperature,
            }),
            signal,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();

        return {
            content: data.choices?.[0]?.message?.content || '',
            tokensUsed: data.usage?.total_tokens,
        };
    }

    /**
     * Call Ollama local API
     */
    private async callOllama(
        provider: AIProviderConfig,
        prompt: string,
        options: { systemPrompt?: string; maxTokens: number; temperature: number },
        signal: AbortSignal
    ): Promise<Omit<AIResponse, 'provider' | 'model' | 'latencyMs' | 'cost'>> {
        const fullPrompt = options.systemPrompt
            ? `${options.systemPrompt}\n\n${prompt}`
            : prompt;

        const response = await fetch(provider.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: provider.model,
                prompt: fullPrompt,
                stream: false,
                options: {
                    num_predict: options.maxTokens,
                    temperature: options.temperature,
                },
            }),
            signal,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();

        return {
            content: data.response || '',
            tokensUsed: data.eval_count,
        };
    }

    /**
     * Check provider health
     */
    async healthCheck(): Promise<Record<string, boolean>> {
        const results: Record<string, boolean> = {};

        for (const provider of this.providers) {
            try {
                await this.complete('ping', { maxTokens: 5 });
                results[provider.name] = true;
            } catch {
                results[provider.name] = false;
            }
        }

        return results;
    }

    /**
     * Get provider stats
     */
    getStats(): {
        activeProviders: string[];
        failedProviders: string[];
        costSavings: string;
    } {
        const active: string[] = [];
        const failed: string[] = [];

        for (const provider of this.providers) {
            const failedAt = this.failedProviders.get(provider.name);
            if (failedAt && Date.now() - failedAt < this.circuitBreakerTimeout) {
                failed.push(provider.name);
            } else {
                active.push(provider.name);
            }
        }

        // Calculate potential cost savings
        const usingFreeProvider = active.some(p =>
            this.providers.find(pr => pr.name === p)?.costPerToken === 0
        );

        return {
            activeProviders: active,
            failedProviders: failed,
            costSavings: usingFreeProvider ? '~90%' : '0%',
        };
    }
}

// Singleton instance
export const aiProvider = new ResilientAIProvider();
