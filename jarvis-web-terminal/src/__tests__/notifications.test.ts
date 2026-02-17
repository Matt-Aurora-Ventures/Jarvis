import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// 1. Notification Store Tests
// ---------------------------------------------------------------------------

describe('useNotificationStore', () => {
  beforeEach(() => {
    // Clear localStorage before each test to avoid persist bleed
    localStorage.clear();
    // Reset zustand store module between tests
    vi.resetModules();
  });

  async function getStore() {
    const mod = await import('@/stores/useNotificationStore');
    const store = mod.useNotificationStore;
    // Clear state for a clean slate
    store.getState().clearAll();
    return store;
  }

  it('should start with empty notifications', async () => {
    const store = await getStore();
    const state = store.getState();
    expect(state.notifications).toEqual([]);
    expect(state.unreadCount).toBe(0);
  });

  it('should add a notification with generated id and read=false', async () => {
    const store = await getStore();
    store.getState().addNotification({
      type: 'stop_loss',
      tokenSymbol: 'BONK',
      entryPrice: 0.001,
      triggerPrice: 0.0008,
      changePercent: -20,
      timestamp: Date.now(),
    });

    const state = store.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.notifications[0].type).toBe('stop_loss');
    expect(state.notifications[0].tokenSymbol).toBe('BONK');
    expect(state.notifications[0].read).toBe(false);
    expect(state.notifications[0].id).toBeDefined();
    expect(typeof state.notifications[0].id).toBe('string');
    expect(state.notifications[0].id.length).toBeGreaterThan(0);
  });

  it('should update unreadCount when adding notifications', async () => {
    const store = await getStore();
    expect(store.getState().unreadCount).toBe(0);

    store.getState().addNotification({
      type: 'stop_loss',
      tokenSymbol: 'BONK',
      entryPrice: 0.001,
      triggerPrice: 0.0008,
      changePercent: -20,
      timestamp: Date.now(),
    });
    expect(store.getState().unreadCount).toBe(1);

    store.getState().addNotification({
      type: 'take_profit',
      tokenSymbol: 'WIF',
      entryPrice: 1.5,
      triggerPrice: 2.0,
      changePercent: 33.3,
      timestamp: Date.now(),
    });
    expect(store.getState().unreadCount).toBe(2);
  });

  it('should mark all as read and set unreadCount to 0', async () => {
    const store = await getStore();

    store.getState().addNotification({
      type: 'stop_loss',
      tokenSymbol: 'BONK',
      entryPrice: 0.001,
      triggerPrice: 0.0008,
      changePercent: -20,
      timestamp: Date.now(),
    });
    store.getState().addNotification({
      type: 'take_profit',
      tokenSymbol: 'WIF',
      entryPrice: 1.5,
      triggerPrice: 2.0,
      changePercent: 33.3,
      timestamp: Date.now(),
    });

    expect(store.getState().unreadCount).toBe(2);
    store.getState().markAllRead();

    const state = store.getState();
    expect(state.unreadCount).toBe(0);
    expect(state.notifications.every((n) => n.read === true)).toBe(true);
  });

  it('should clear all notifications', async () => {
    const store = await getStore();

    store.getState().addNotification({
      type: 'stop_loss',
      tokenSymbol: 'BONK',
      entryPrice: 0.001,
      triggerPrice: 0.0008,
      changePercent: -20,
      timestamp: Date.now(),
    });
    store.getState().addNotification({
      type: 'take_profit',
      tokenSymbol: 'WIF',
      entryPrice: 1.5,
      triggerPrice: 2.0,
      changePercent: 33.3,
      timestamp: Date.now(),
    });

    expect(store.getState().notifications).toHaveLength(2);
    store.getState().clearAll();

    const state = store.getState();
    expect(state.notifications).toEqual([]);
    expect(state.unreadCount).toBe(0);
  });

  it('should prepend new notifications (most recent first)', async () => {
    const store = await getStore();

    store.getState().addNotification({
      type: 'stop_loss',
      tokenSymbol: 'FIRST',
      entryPrice: 1,
      triggerPrice: 0.5,
      changePercent: -50,
      timestamp: 1000,
    });
    store.getState().addNotification({
      type: 'take_profit',
      tokenSymbol: 'SECOND',
      entryPrice: 1,
      triggerPrice: 2,
      changePercent: 100,
      timestamp: 2000,
    });

    const state = store.getState();
    expect(state.notifications[0].tokenSymbol).toBe('SECOND');
    expect(state.notifications[1].tokenSymbol).toBe('FIRST');
  });

  it('should persist notifications to localStorage', async () => {
    const store = await getStore();

    store.getState().addNotification({
      type: 'stop_loss',
      tokenSymbol: 'PERSIST',
      entryPrice: 1.0,
      triggerPrice: 0.8,
      changePercent: -20,
      timestamp: Date.now(),
    });

    // zustand persist writes to localStorage synchronously after state change
    // Wait for persist middleware to flush
    await new Promise((r) => setTimeout(r, 50));

    const stored = localStorage.getItem('jarvis-notifications');
    expect(stored).not.toBeNull();
    const parsed = JSON.parse(stored!);
    expect(parsed.state.notifications).toHaveLength(1);
    expect(parsed.state.notifications[0].tokenSymbol).toBe('PERSIST');
  });

  it('should cap notifications at 50 max', async () => {
    const store = await getStore();

    for (let i = 0; i < 55; i++) {
      store.getState().addNotification({
        type: 'stop_loss',
        tokenSymbol: `TOKEN${i}`,
        entryPrice: 1,
        triggerPrice: 0.5,
        changePercent: -50,
        timestamp: i,
      });
    }

    expect(store.getState().notifications.length).toBeLessThanOrEqual(50);
  });
});

// ---------------------------------------------------------------------------
// 2. Notification Sound Tests
// ---------------------------------------------------------------------------

describe('playNotificationSound', () => {
  let mockOscillator: Record<string, unknown>;
  let mockGain: Record<string, unknown>;
  let mockAudioContext: Record<string, unknown>;
  let ctorSpy = vi.fn();

  beforeEach(() => {
    mockOscillator = {
      type: 'sine',
      frequency: { setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
    };
    mockGain = {
      gain: { setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
      connect: vi.fn(),
    };
    mockAudioContext = {
      currentTime: 0,
      destination: {},
      createOscillator: vi.fn(() => mockOscillator),
      createGain: vi.fn(() => mockGain),
    };

    // Use a proper class mock so `new AudioContext()` works without warnings
    ctorSpy = vi.fn();
    class MockAudioContext {
      currentTime: number;
      destination: Record<string, unknown>;
      createOscillator: () => unknown;
      createGain: () => unknown;
      constructor() {
        ctorSpy();
        this.currentTime = mockAudioContext.currentTime as number;
        this.destination = mockAudioContext.destination as Record<string, unknown>;
        this.createOscillator = mockAudioContext.createOscillator as () => unknown;
        this.createGain = mockAudioContext.createGain as () => unknown;
      }
    }

    vi.stubGlobal('AudioContext', MockAudioContext);
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function getPlaySound() {
    const mod = await import('@/lib/notification-sound');
    return mod.playNotificationSound;
  }

  it('should create an AudioContext lazily on first call', async () => {
    const playNotificationSound = await getPlaySound();
    expect(ctorSpy).not.toHaveBeenCalled();

    playNotificationSound('success');
    expect(ctorSpy).toHaveBeenCalledTimes(1);
  });

  it('should reuse the same AudioContext on subsequent calls', async () => {
    const playNotificationSound = await getPlaySound();

    playNotificationSound('success');
    playNotificationSound('warning');
    playNotificationSound('error');

    expect(ctorSpy).toHaveBeenCalledTimes(1);
  });

  it('should create oscillator and gain nodes for success sound', async () => {
    const playNotificationSound = await getPlaySound();
    playNotificationSound('success');

    expect(mockAudioContext.createOscillator).toHaveBeenCalled();
    expect(mockAudioContext.createGain).toHaveBeenCalled();
    expect(mockOscillator.connect).toHaveBeenCalled();
    expect(mockOscillator.start).toHaveBeenCalled();
    expect(mockOscillator.stop).toHaveBeenCalled();
  });

  it('should create oscillator and gain nodes for warning sound', async () => {
    const playNotificationSound = await getPlaySound();
    playNotificationSound('warning');

    expect(mockAudioContext.createOscillator).toHaveBeenCalled();
    expect(mockAudioContext.createGain).toHaveBeenCalled();
    expect(mockOscillator.start).toHaveBeenCalled();
    expect(mockOscillator.stop).toHaveBeenCalled();
  });

  it('should create oscillator and gain nodes for error sound', async () => {
    const playNotificationSound = await getPlaySound();
    playNotificationSound('error');

    expect(mockAudioContext.createOscillator).toHaveBeenCalled();
    expect(mockAudioContext.createGain).toHaveBeenCalled();
    expect(mockOscillator.start).toHaveBeenCalled();
    expect(mockOscillator.stop).toHaveBeenCalled();
  });

  it('should not throw if AudioContext is unavailable', async () => {
    vi.stubGlobal('AudioContext', undefined);
    vi.resetModules();
    const playNotificationSound = (await import('@/lib/notification-sound')).playNotificationSound;

    expect(() => playNotificationSound('success')).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// 3. SLTPMonitor integration with notification store
// ---------------------------------------------------------------------------

describe('SLTPMonitor notification integration', () => {
  it('checkPositionThresholds fires events that can be recorded in store', async () => {
    // This tests the integration pattern: SLTPMonitor triggers -> store records
    vi.resetModules();
    localStorage.clear();

    const { checkPositionThresholds } = await import('@/lib/stop-loss-manager');
    const { useNotificationStore } = await import('@/stores/useNotificationStore');

    // Clear store
    useNotificationStore.getState().clearAll();

    const positions = [
      {
        id: 'pos-1',
        tokenMint: 'mintA',
        tokenSymbol: 'BONK',
        entryPrice: 1.0,
        currentPrice: 0.0,
        amount: 100,
        amountUsd: 100,
        solAmount: 0.1,
        stopLossPercent: 10,
        takeProfitPercent: 50,
        status: 'open' as const,
        side: 'long' as const,
        openedAt: Date.now(),
        timestamp: Date.now(),
        pnl: 0,
        pnlPercent: 0,
      },
    ];

    const prices = new Map<string, number>();
    prices.set('mintA', 0.85); // 15% drop - below 10% SL

    const triggered = new Set<string>();

    checkPositionThresholds(positions, prices, triggered, (event) => {
      useNotificationStore.getState().addNotification({
        type: event.type,
        tokenSymbol: event.tokenSymbol,
        entryPrice: event.entryPrice,
        triggerPrice: event.currentPrice,
        changePercent: event.changePercent,
        timestamp: Date.now(),
      });
    });

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.notifications[0].type).toBe('stop_loss');
    expect(state.notifications[0].tokenSymbol).toBe('BONK');
    expect(state.unreadCount).toBe(1);
  });

  it('checkPositionThresholds fires TP events that can be recorded in store', async () => {
    vi.resetModules();
    localStorage.clear();

    const { checkPositionThresholds } = await import('@/lib/stop-loss-manager');
    const { useNotificationStore } = await import('@/stores/useNotificationStore');

    useNotificationStore.getState().clearAll();

    const positions = [
      {
        id: 'pos-2',
        tokenMint: 'mintB',
        tokenSymbol: 'WIF',
        entryPrice: 1.0,
        currentPrice: 0.0,
        amount: 50,
        amountUsd: 50,
        solAmount: 0.1,
        stopLossPercent: 10,
        takeProfitPercent: 50,
        status: 'open' as const,
        side: 'long' as const,
        openedAt: Date.now(),
        timestamp: Date.now(),
        pnl: 0,
        pnlPercent: 0,
      },
    ];

    const prices = new Map<string, number>();
    prices.set('mintB', 1.6); // 60% gain - above 50% TP

    const triggered = new Set<string>();

    checkPositionThresholds(positions, prices, triggered, (event) => {
      useNotificationStore.getState().addNotification({
        type: event.type,
        tokenSymbol: event.tokenSymbol,
        entryPrice: event.entryPrice,
        triggerPrice: event.currentPrice,
        changePercent: event.changePercent,
        timestamp: Date.now(),
      });
    });

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.notifications[0].type).toBe('take_profit');
    expect(state.notifications[0].tokenSymbol).toBe('WIF');
    expect(state.unreadCount).toBe(1);
  });
});
