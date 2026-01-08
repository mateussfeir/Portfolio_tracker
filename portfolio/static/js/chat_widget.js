(function () {
    document.addEventListener('DOMContentLoaded', function () {
        const widget = document.getElementById('portfolio-assistant-widget');
        if (!widget) {
            return;
        }

        const toggleBtn = document.getElementById('portfolio-assistant-toggle');
        const panel = document.getElementById('portfolio-assistant-panel');
        const closeBtn = document.getElementById('portfolio-assistant-close');
        const messagesEl = document.getElementById('portfolio-assistant-messages');
        const form = document.getElementById('portfolio-assistant-form');
        const input = document.getElementById('portfolio-assistant-input');
        const sendBtn = document.getElementById('portfolio-assistant-send');
        const storageKey = 'portfolioAssistantChatHistory';
        const username = widget.dataset.username || 'there';
        const currencySymbol = widget.dataset.currencySymbol || '$';

        let state = {
            messages: [],
            currentTimeFilter: 'overall'
        };

        function getPortfolioSnapshot() {
            // Placeholder data - replace with API call when available
            return {
                totalValue: 1331674.82,
                allocation: [
                    { ticker: 'BTC', pct: 58 },
                    { ticker: 'ETH', pct: 24 },
                    { ticker: 'SOL', pct: 8 },
                    { ticker: 'CASH', pct: 10 }
                ],
                performance: [
                    { ticker: 'BTC', pnlPct: 12.4 },
                    { ticker: 'ETH', pnlPct: -3.1 },
                    { ticker: 'SOL', pnlPct: 22.8 },
                    { ticker: 'CASH', pnlPct: 1.2 }
                ],
                holdings: [
                    { ticker: 'BTC', amount: 1.6 },
                    { ticker: 'ETH', amount: 10.25 },
                    { ticker: 'SOL', amount: 85.2 },
                    { ticker: 'CASH', amount: 78000 }
                ],
                prices: {
                    BTC: 95000,
                    ETH: 3650,
                    SOL: 195,
                    CASH: 1
                },
                pnlTotalPct: 9.4
            };
        }

        function loadHistory() {
            try {
                const raw = localStorage.getItem(storageKey);
                state.messages = raw ? JSON.parse(raw) : [];
            } catch (error) {
                state.messages = [];
            }
        }

        function saveHistory() {
            localStorage.setItem(storageKey, JSON.stringify(state.messages));
        }

        function formatCurrency(value) {
            if (isNaN(value)) {
                return `${currencySymbol}${value}`;
            }
            return `${currencySymbol}${Number(value).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            })}`;
        }

        function renderMessages() {
            messagesEl.innerHTML = '';
            state.messages.forEach(msg => {
                const bubble = document.createElement('div');
                bubble.className = `assistant-message ${msg.sender}`;
                bubble.textContent = msg.text;
                if (msg.timestamp) {
                    const time = document.createElement('time');
                    const date = new Date(msg.timestamp);
                    time.textContent = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    bubble.appendChild(time);
                }
                messagesEl.appendChild(bubble);
            });
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function appendMessage(sender, text) {
            const entry = {
                sender,
                text,
                timestamp: Date.now()
            };
            state.messages.push(entry);
            saveHistory();
            renderMessages();
            if (sender === 'bot' && !panel.classList.contains('open')) {
                toggleBtn.classList.add('has-unread');
            }
        }

        function initialBotGreeting() {
            if (state.messages.length === 0) {
                appendMessage('bot', `Hey ${username}, I'm your Portfolio Assistant. Ask me about totals, allocations, or even BTC prices!`);
            } else {
                renderMessages();
            }
        }

        function togglePanel(forceOpen) {
            const shouldOpen = typeof forceOpen === 'boolean' ? forceOpen : !panel.classList.contains('open');
            panel.classList.toggle('open', shouldOpen);
            if (shouldOpen) {
                toggleBtn.classList.remove('has-unread');
                messagesEl.scrollTop = messagesEl.scrollHeight;
            }
        }

        const TIME_FILTERS = [
            { label: 'today', pattern: /\btoday\b/i },
            { label: 'last 7 days', pattern: /(7|seven)\s*(days?|d)\b/i },
            { label: 'last 30 days', pattern: /(30|thirty)\s*(days?|d)\b/i },
            { label: 'this month', pattern: /\bthis\s+month\b/i }
        ];

        function extractTimeFilter(text) {
            for (const filter of TIME_FILTERS) {
                if (filter.pattern.test(text)) {
                    return filter.label;
                }
            }
            return null;
        }

        const KEYWORD_INTENTS = [
            { intent: 'greeting', keywords: ['hello', 'hi', 'hey'] },
            { intent: 'help', keywords: ['help', 'what can you do', 'commands'] },
            { intent: 'total_value', keywords: ['total', 'portfolio value', 'net worth'] },
            { intent: 'allocation', keywords: ['allocation', 'distribution', 'pie'] },
            { intent: 'best_asset', keywords: ['best performing', 'top performer', 'top asset'] },
            { intent: 'worst_asset', keywords: ['worst performing', 'biggest loss', 'laggard'] },
            { intent: 'pnl', keywords: ['pnl', 'profit', 'loss'] }
        ];

        function detectIntent(message) {
            const normalized = message.toLowerCase();
            const timeFilter = extractTimeFilter(normalized);
            const snapshot = getPortfolioSnapshot();
            const tickers = new Set([
                ...Object.keys(snapshot.prices),
                ...snapshot.holdings.map(h => h.ticker)
            ]);

            const priceMatch = normalized.match(/price(?:\s+of)?\s+([a-z]{2,6})/i);
            if (priceMatch) {
                const ticker = priceMatch[1].toUpperCase();
                if (tickers.has(ticker)) {
                    return { intent: 'price', ticker, timeFilter };
                }
            }

            const holdingMatch = normalized.match(/(how\s+much|holdings?|amount)\s+([a-z]{2,6})/i);
            if (holdingMatch) {
                const ticker = holdingMatch[2].toUpperCase();
                if (tickers.has(ticker)) {
                    return { intent: 'holdings', ticker, timeFilter };
                }
            }

            for (const mapping of KEYWORD_INTENTS) {
                if (mapping.keywords.some(keyword => normalized.includes(keyword))) {
                    return { intent: mapping.intent, timeFilter };
                }
            }

            if (timeFilter) {
                return { intent: 'time_filter', timeFilter };
            }

            return { intent: 'unknown', timeFilter };
        }

        function allocationSummary(snapshot) {
            return snapshot.allocation
                .map(entry => `${entry.ticker}: ${entry.pct}%`)
                .join(' • ');
        }

        function bestAsset(snapshot) {
            return snapshot.performance.reduce((best, asset) => {
                if (!best || asset.pnlPct > best.pnlPct) {
                    return asset;
                }
                return best;
            }, null);
        }

        function worstAsset(snapshot) {
            return snapshot.performance.reduce((worst, asset) => {
                if (!worst || asset.pnlPct < worst.pnlPct) {
                    return asset;
                }
                return worst;
            }, null);
        }

        function handleIntent(intentResult) {
            const snapshot = getPortfolioSnapshot();
            const contextTime = intentResult.timeFilter || state.currentTimeFilter;
            if (intentResult.timeFilter) {
                state.currentTimeFilter = intentResult.timeFilter;
            }

            const timeframeSuffix = state.currentTimeFilter !== 'overall'
                ? ` for ${state.currentTimeFilter}`
                : '';

            let reply;
            switch (intentResult.intent) {
                case 'greeting':
                    reply = `Hello ${username}! I'm ready to walk through your portfolio${timeframeSuffix || ' anytime'}.`;
                    break;
                case 'help':
                    reply = 'Try asking things like "total value", "allocation", "best performing asset", "price of BTC", or "how much ETH do I have".';
                    break;
                case 'total_value':
                    reply = `Your portfolio is currently valued at ${formatCurrency(snapshot.totalValue)}${timeframeSuffix}.`;
                    break;
                case 'allocation':
                    reply = `Allocation${timeframeSuffix}: ${allocationSummary(snapshot)}.`;
                    break;
                case 'best_asset': {
                    const asset = bestAsset(snapshot);
                    reply = asset
                        ? `${asset.ticker} is the top performer${timeframeSuffix}, up ${asset.pnlPct}%`
                        : 'I could not find performance data yet.';
                    break;
                }
                case 'worst_asset': {
                    const asset = worstAsset(snapshot);
                    reply = asset
                        ? `${asset.ticker} is lagging${timeframeSuffix}, down ${asset.pnlPct}%`
                        : 'I could not find performance data yet.';
                    break;
                }
                case 'pnl':
                    reply = `Overall PnL${timeframeSuffix}: ${snapshot.pnlTotalPct >= 0 ? '+' : ''}${snapshot.pnlTotalPct}% based on your tracked assets.`;
                    break;
                case 'price':
                    if (intentResult.ticker && snapshot.prices[intentResult.ticker]) {
                        reply = `Latest ${intentResult.ticker} price${timeframeSuffix || ''}: ${formatCurrency(snapshot.prices[intentResult.ticker])}.`;
                    } else {
                        reply = `I only track ${Object.keys(snapshot.prices).join(', ')} for now.`;
                    }
                    break;
                case 'holdings': {
                    const holding = snapshot.holdings.find(h => h.ticker === intentResult.ticker);
                    reply = holding
                        ? `You currently hold ${holding.amount} ${intentResult.ticker}${timeframeSuffix}.`
                        : `I don't see any ${intentResult.ticker} in your holdings yet.`;
                    break;
                }
                case 'time_filter':
                    reply = `Got it, I'll focus on ${state.currentTimeFilter} data unless you tell me otherwise.`;
                    break;
                case 'unknown':
                default:
                    reply = `I'm still learning. Try greeting me or ask about totals, allocation, or individual asset prices.`;
            }

            appendMessage('bot', reply);
        }

        function handleSubmit(event) {
            event.preventDefault();
            const value = input.value.trim();
            if (!value) {
                return;
            }
            appendMessage('user', value);
            input.value = '';
            input.style.height = 'auto';
            sendBtn.disabled = true;
            const intentResult = detectIntent(value);
            handleIntent(intentResult);
        }

        function autoResizeTextarea() {
            input.style.height = 'auto';
            input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
        }

        toggleBtn.addEventListener('click', () => togglePanel());
        closeBtn.addEventListener('click', () => togglePanel(false));

        form.addEventListener('submit', handleSubmit);

        input.addEventListener('input', () => {
            sendBtn.disabled = input.value.trim().length === 0;
            autoResizeTextarea();
        });

        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                form.requestSubmit();
            }
        });

        loadHistory();
        initialBotGreeting();
    });
})();
