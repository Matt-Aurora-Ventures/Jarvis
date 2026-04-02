# Jarvis Frontend Refactoring Plan

## Current State Analysis

### Existing Structure
```
src/
├── App.jsx                    # Router setup
├── main.jsx                   # Entry point
├── index.css                  # 2164 lines of CSS (monolithic)
├── components/
│   ├── ErrorBoundary.jsx      ✅ Good
│   ├── Layout.jsx             ⚠️ Mixed concerns
│   ├── OrderPanel.jsx         ⚠️ Large, needs splitting
│   ├── TradingChart.jsx       ⚠️ Large, tightly coupled
│   ├── VoiceOrb.jsx           ✅ Good
│   └── trading/               ❌ Empty folder
├── pages/
│   ├── Chat.jsx               ⚠️ Needs cleanup
│   ├── Dashboard.jsx          ⚠️ Needs cleanup
│   ├── Research.jsx           ⚠️ Needs cleanup
│   ├── Settings.jsx           ⚠️ Needs cleanup
│   ├── Trading.jsx            ⚠️ 592 lines, needs splitting
│   └── VoiceControl.jsx       ⚠️ Needs cleanup
└── stores/
    └── jarvisStore.js         ⚠️ Single store, needs splitting
```

### Issues Identified
1. **Monolithic CSS** - 2164 lines in single file
2. **Large Components** - Trading.jsx has 592 lines with inline components
3. **No Design Tokens** - CSS variables exist but not tokenized properly
4. **Missing Hooks** - API calls inline, no custom hooks
5. **No Types** - Pure JS, no TypeScript
6. **Empty Folders** - `/components/trading/` is empty
7. **Inconsistent Patterns** - Mixed component patterns

---

## Proposed Structure

```
src/
├── app/
│   ├── App.jsx
│   ├── routes.jsx
│   └── providers.jsx
│
├── assets/
│   ├── icons/
│   └── images/
│
├── components/
│   ├── ui/                        # Primitives (Shadcn-style)
│   │   ├── Button.jsx
│   │   ├── Card.jsx
│   │   ├── Badge.jsx
│   │   ├── Input.jsx
│   │   ├── Modal.jsx
│   │   ├── Tabs.jsx
│   │   ├── Tooltip.jsx
│   │   ├── Skeleton.jsx
│   │   └── index.js
│   │
│   ├── layout/                    # Layout components
│   │   ├── TopNav.jsx
│   │   ├── Sidebar.jsx
│   │   ├── PageLayout.jsx
│   │   └── index.js
│   │
│   ├── trading/                   # Trading domain
│   │   ├── TradingChart.jsx
│   │   ├── OrderPanel.jsx
│   │   ├── PositionCard.jsx
│   │   ├── StatsGrid.jsx
│   │   ├── TokenScanner.jsx
│   │   ├── PriceDisplay.jsx
│   │   └── index.js
│   │
│   ├── chat/                      # Chat domain
│   │   ├── ChatBubble.jsx
│   │   ├── MessageList.jsx
│   │   ├── ChatInput.jsx
│   │   └── index.js
│   │
│   └── common/                    # Shared components
│       ├── ErrorBoundary.jsx
│       ├── LoadingSpinner.jsx
│       ├── VoiceOrb.jsx
│       └── index.js
│
├── features/                      # Feature modules
│   ├── trading/
│   │   ├── TradingPage.jsx
│   │   ├── useTradingData.js
│   │   └── tradingStore.js
│   │
│   ├── dashboard/
│   │   ├── DashboardPage.jsx
│   │   └── useDashboardData.js
│   │
│   ├── chat/
│   │   ├── ChatPage.jsx
│   │   └── useChatMessages.js
│   │
│   └── settings/
│       ├── SettingsPage.jsx
│       └── useSettings.js
│
├── hooks/                         # Shared hooks
│   ├── useApi.js
│   ├── useWebSocket.js
│   ├── useLocalStorage.js
│   └── index.js
│
├── lib/                           # Utilities
│   ├── api.js
│   ├── format.js
│   ├── constants.js
│   └── utils.js
│
├── stores/                        # Zustand stores
│   ├── jarvisStore.js
│   ├── tradingStore.js
│   ├── walletStore.js
│   └── index.js
│
└── styles/
    ├── globals.css                # Base styles only
    ├── tokens/
    │   ├── colors.css
    │   ├── typography.css
    │   ├── spacing.css
    │   └── shadows.css
    └── components/
        ├── buttons.css
        ├── cards.css
        ├── forms.css
        └── layout.css
```

---

## Phase 1: Foundation (Non-Breaking)

### 1.1 Create Design Token System
Split CSS variables into dedicated files for better maintainability.

### 1.2 Create UI Primitives
Build reusable, styled base components:
- Button, Card, Badge, Input, Modal, Tabs, Skeleton

### 1.3 Create Custom Hooks
Extract API logic into reusable hooks:
- `useApi` - Generic fetch wrapper
- `useWallet` - Wallet data hook
- `useSniper` - Sniper status hook
- `useTradingData` - Combined trading data

### 1.4 Create Utility Library
- `format.js` - Number/currency formatting
- `api.js` - API client with error handling
- `constants.js` - Shared constants

---

## Phase 2: Component Extraction

### 2.1 Extract from Trading.jsx (592 lines → ~100 lines)
Move inline components to proper files:
- `TopNav` → `components/layout/TopNav.jsx`
- `Sidebar` → `components/layout/Sidebar.jsx`
- `StatsGrid` → `components/trading/StatsGrid.jsx`
- `LivePositionCard` → `components/trading/PositionCard.jsx`
- `ToolsHub` → `components/trading/TokenScanner.jsx`
- `FloatingChat` → `components/chat/FloatingChat.jsx`

### 2.2 Refactor TradingChart.jsx
- Extract chart config to separate file
- Add proper loading/error states
- Add resize observer hook

### 2.3 Refactor OrderPanel.jsx
- Split into smaller components
- Add form validation
- Add loading states

---

## Phase 3: Store Refactoring

### 3.1 Split jarvisStore.js
```javascript
// walletStore.js - Wallet state
// tradingStore.js - Trading state  
// uiStore.js - UI preferences
// chatStore.js - Chat messages
```

### 3.2 Add Persist Middleware
Save user preferences to localStorage.

---

## Phase 4: Polish

### 4.1 Add Loading Skeletons
Replace spinners with skeleton loaders for better UX.

### 4.2 Add Animations
Subtle micro-interactions using CSS or Framer Motion.

### 4.3 Add Dark Mode
Toggle between White Knight and Dark themes.

### 4.4 Accessibility
- ARIA labels
- Keyboard navigation
- Focus management

---

## Implementation Priority

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🔴 P0 | Create UI primitives | High | Low |
| 🔴 P0 | Extract Trading.jsx components | High | Medium |
| 🟠 P1 | Split CSS into tokens | Medium | Low |
| 🟠 P1 | Create custom hooks | Medium | Medium |
| 🟡 P2 | Store refactoring | Medium | Medium |
| 🟡 P2 | Add loading skeletons | Medium | Low |
| 🟢 P3 | Dark mode | Low | Medium |
| 🟢 P3 | Animations | Low | Low |

---

## Quick Wins (Can do now)

1. **Extract `TopNav` component** - 50 lines
2. **Extract `Sidebar` component** - 30 lines
3. **Extract `StatsGrid` component** - 40 lines
4. **Create `Button` primitive** - Consolidate button styles
5. **Create `Card` primitive** - Consolidate card styles
6. **Create `useApi` hook** - DRY up fetch calls

---

## Files to Create First

```bash
# UI Primitives
src/components/ui/Button.jsx
src/components/ui/Card.jsx
src/components/ui/Badge.jsx
src/components/ui/index.js

# Layout
src/components/layout/TopNav.jsx
src/components/layout/Sidebar.jsx
src/components/layout/index.js

# Trading
src/components/trading/StatsGrid.jsx
src/components/trading/PositionCard.jsx
src/components/trading/index.js

# Hooks
src/hooks/useApi.js
src/hooks/useWallet.js
src/hooks/index.js

# Lib
src/lib/api.js
src/lib/format.js
src/lib/constants.js
```

---

## Ready to Start?

I can begin implementing Phase 1 now. Which would you like first:

1. **UI Primitives** (Button, Card, Badge) - Clean, reusable building blocks
2. **Component Extraction** - Split Trading.jsx into smaller files
3. **Custom Hooks** - Extract API logic for reusability
4. **CSS Tokens** - Split monolithic CSS into organized modules

Let me know and I'll start implementing without breaking existing functionality!
