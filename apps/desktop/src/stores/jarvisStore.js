import { create } from 'zustand'

const useJarvisStore = create((set, get) => ({
  // Listening state
  isListening: false,
  setIsListening: (listening) => set({ isListening: listening }),
  
  // Voice state
  voiceEnabled: true,
  setVoiceEnabled: (enabled) => set({ voiceEnabled: enabled }),
  
  // Connection state
  isConnected: false,
  setIsConnected: (connected) => set({ isConnected: connected }),
  
  // Messages
  messages: [],
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, { ...message, id: Date.now(), timestamp: new Date() }]
  })),
  clearMessages: () => set({ messages: [] }),
  
  // Suggestions
  suggestions: [],
  setSuggestions: (suggestions) => set({ suggestions }),
  addSuggestion: (suggestion) => set((state) => ({
    suggestions: [{ ...suggestion, id: Date.now(), timestamp: new Date() }, ...state.suggestions].slice(0, 10)
  })),
  
  // Activity
  currentActivity: null,
  setCurrentActivity: (activity) => set({ currentActivity: activity }),
  
  // API Keys
  apiKeys: {
    gemini: '',
    groq: '',
    anthropic: '',
    openai: '',
    trello: '',
    github: '',
  },
  setApiKey: (provider, key) => set((state) => ({
    apiKeys: { ...state.apiKeys, [provider]: key }
  })),
  
  // Status
  status: {
    daemon: 'unknown',
    voice: 'off',
    monitoring: 'off',
  },
  setStatus: (newStatus) => set((state) => ({
    status: { ...state.status, ...newStatus }
  })),
}))

export default useJarvisStore
