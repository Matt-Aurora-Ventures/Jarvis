import { describe, it, expect, beforeEach } from 'vitest';
import { useSettingsStore } from '@/stores/useSettingsStore';

describe('useSettingsStore - AI consensus fields', () => {
  beforeEach(() => {
    // Reset the store state directly (avoid triggering persist middleware issues)
    useSettingsStore.setState({
      defaultStopLoss: 5,
      defaultTakeProfit: 20,
      aiConsensus: null,
      aiBestWinRate: null,
      aiSignalStrength: null,
      aiSuggestedTP: null,
      aiSuggestedSL: null,
    });
  });

  it('should have aiConsensus defaulting to null', () => {
    const state = useSettingsStore.getState();
    expect(state.aiConsensus).toBeNull();
  });

  it('should have aiBestWinRate defaulting to null', () => {
    const state = useSettingsStore.getState();
    expect(state.aiBestWinRate).toBeNull();
  });

  it('should have aiSignalStrength defaulting to null', () => {
    const state = useSettingsStore.getState();
    expect(state.aiSignalStrength).toBeNull();
  });

  it('should have aiSuggestedTP defaulting to null', () => {
    const state = useSettingsStore.getState();
    expect(state.aiSuggestedTP).toBeNull();
  });

  it('should have aiSuggestedSL defaulting to null', () => {
    const state = useSettingsStore.getState();
    expect(state.aiSuggestedSL).toBeNull();
  });

  it('should set AI signal data via setAISignal', () => {
    const store = useSettingsStore.getState();
    store.setAISignal({
      consensus: 'BUY',
      bestWinRate: 72,
      signalStrength: '3/4',
      suggestedTP: 25,
      suggestedSL: 8,
    });

    const state = useSettingsStore.getState();
    expect(state.aiConsensus).toBe('BUY');
    expect(state.aiBestWinRate).toBe(72);
    expect(state.aiSignalStrength).toBe('3/4');
    expect(state.aiSuggestedTP).toBe(25);
    expect(state.aiSuggestedSL).toBe(8);
  });

  it('should also update defaultTakeProfit and defaultStopLoss when setAISignal is called', () => {
    const store = useSettingsStore.getState();
    store.setAISignal({
      consensus: 'BUY',
      bestWinRate: 65,
      signalStrength: '2/4',
      suggestedTP: 30,
      suggestedSL: 12,
    });

    const state = useSettingsStore.getState();
    expect(state.defaultTakeProfit).toBe(30);
    expect(state.defaultStopLoss).toBe(12);
  });

  it('should clear AI signal data via clearAISignal', () => {
    const store = useSettingsStore.getState();
    store.setAISignal({
      consensus: 'BUY',
      bestWinRate: 72,
      signalStrength: '3/4',
      suggestedTP: 25,
      suggestedSL: 8,
    });

    useSettingsStore.getState().clearAISignal();

    const state = useSettingsStore.getState();
    expect(state.aiConsensus).toBeNull();
    expect(state.aiBestWinRate).toBeNull();
    expect(state.aiSignalStrength).toBeNull();
    expect(state.aiSuggestedTP).toBeNull();
    expect(state.aiSuggestedSL).toBeNull();
  });

  it('should have hasAISignal returning true when AI data is set', () => {
    const store = useSettingsStore.getState();
    expect(store.hasAISignal()).toBe(false);

    store.setAISignal({
      consensus: 'BUY',
      bestWinRate: 72,
      signalStrength: '3/4',
      suggestedTP: 25,
      suggestedSL: 8,
    });

    const updatedStore = useSettingsStore.getState();
    expect(updatedStore.hasAISignal()).toBe(true);
  });

  it('should handle SELL consensus', () => {
    const store = useSettingsStore.getState();
    store.setAISignal({
      consensus: 'SELL',
      bestWinRate: 55,
      signalStrength: '1/4',
      suggestedTP: 15,
      suggestedSL: 10,
    });

    const state = useSettingsStore.getState();
    expect(state.aiConsensus).toBe('SELL');
    expect(state.aiSignalStrength).toBe('1/4');
  });

  it('should handle HOLD consensus', () => {
    const store = useSettingsStore.getState();
    store.setAISignal({
      consensus: 'HOLD',
      bestWinRate: 48,
      signalStrength: '2/4',
      suggestedTP: 20,
      suggestedSL: 10,
    });

    const state = useSettingsStore.getState();
    expect(state.aiConsensus).toBe('HOLD');
  });
});
