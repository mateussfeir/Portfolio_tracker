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
        const clearBtn = document.getElementById('portfolio-assistant-clear');
        const storageKey = 'portfolioAssistantChatHistory';
        const timeframeStorageKey = 'portfolioAssistantTimeframe';
        const username = widget.dataset.username || 'there';
        const currencySymbol = widget.dataset.currencySymbol || '$';
        let debugMode = false;
        try {
            debugMode = localStorage.getItem('pa_debug') === '1';
        } catch (e) {
            debugMode = false;
        }

        let state = {
            messages: [],
            currentTimeFilter: 'all time'
        };

        const DEFAULT_TIMEFRAME = 'all time';

        const TICKER_ALIASES = {
            BTC: ['btc', 'bitcoin', 'xbt'],
            ETH: ['eth', 'ethereum', 'ether'],
            SOL: ['sol', 'solana'],
            USDC: ['usdc', 'usd coin', 'usdcoin'],
            CASH: ['cash', 'usd', 'cad', 'dollars']
        };

        const KEYWORDS = {
            greeting: ['hello', 'hi', 'hey', 'yo', 'good morning', 'good evening'],
            help: ['help', 'what can you do', 'how do you work', 'commands', 'what can you show'],
            price: ['price', 'quote', 'rate'],
            holdings: ['holding', 'holdings', 'position', 'positions', 'do i have', 'amount', 'bags', 'what is my position'],
            total_value: ['total value', 'portfolio value', 'net worth', 'how much money', 'how much do i have', 'how much cash', 'how much do we have', 'total'],
            allocation: ['allocation', 'distribution', 'weights', 'weighting', 'pie'],
            best_asset: ['best asset', 'best coin', 'top performer', 'best performing', 'top gainer', 'biggest gain', 'highest gain', 'up the most'],
            worst_asset: ['worst asset', 'lost the most', 'biggest loss', 'top loser', 'down the most', 'laggard', 'worst performing'],
            performance_summary: ['performance', 'returns', 'return', 'show performance', 'how am i doing', 'results', 'pnl'],
            asset_performance: ['performance', 'return', 'pnl', 'gain', 'loss'],
            pnl: ['pnl', 'profit', 'loss']
        };

        function getPortfolioSnapshot(range = state.currentTimeFilter) {
            // Placeholder data - replace with API call when available
            void range;
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
                const storedTimeframe = localStorage.getItem(timeframeStorageKey);
                if (storedTimeframe) {
                    state.currentTimeFilter = storedTimeframe;
                }
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

        function clearConversation() {
            state.messages = [];
            saveHistory();
            renderMessages();
            toggleBtn.classList.remove('has-unread');
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

        const TIMEFRAME_PATTERNS = [
            { value: 'today', patterns: [/\btoday\b/] },
            { value: '7 days', patterns: [/\b(7|seven)\s*(days?|d)\b/, /\b7d\b/, /\blast\s+week\b/] },
            { value: '30 days', patterns: [/\b(30|thirty)\s*(days?|d)\b/, /\b30d\b/] },
            { value: 'this month', patterns: [/\bthis\s+month\b/, /\bcurrent\s+month\b/, /\bmonth\b/] },
            { value: 'all time', patterns: [/\ball\s*time\b/, /\boverall\b/, /\balltime\b/] }
        ];

        function normalizeMessage(message) {
            if (!message) {
                return '';
            }
            return message
                .toLowerCase()
                .replace(/[\u2018\u2019\u201A\u201B]/g, "'")
                .replace(/[\u201C\u201D\u201E\u201F]/g, '"')
                .replace(/[^a-z0-9\s]/g, ' ')
                .replace(/\s+/g, ' ')
                .trim();
        }

        function parseTimeframe(normalized) {
            if (!normalized) {
                return null;
            }
            for (const entry of TIMEFRAME_PATTERNS) {
                for (const pattern of entry.patterns) {
                    const match = normalized.match(pattern);
                    if (match) {
                        return { value: entry.value, matched: match[0].trim() };
                    }
                }
            }
            return null;
        }

        function extractTicker(normalized) {
            if (!normalized) {
                return null;
            }
            const matches = [];
            Object.entries(TICKER_ALIASES).forEach(([ticker, aliases]) => {
                aliases.forEach(alias => {
                    const pattern = new RegExp(`\\b${alias.replace(/\s+/g, '\\s+')}\\b`, 'i');
                    if (pattern.test(normalized)) {
                        matches.push({ ticker, alias: alias.toLowerCase() });
                    }
                });
            });

            if (!matches.length) {
                return null;
            }
            return {
                ticker: matches[0].ticker,
                alias: matches[0].alias,
                multiple: matches.length > 1
            };
        }

        function escapeRegExp(value) {
            return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }

        function containsAny(text, phrases) {
            if (!text) {
                return false;
            }
            return phrases.some(phrase => {
                const pattern = new RegExp(`\\b${escapeRegExp(phrase).replace(/\s+/g, '\\s+')}\\b`);
                return pattern.test(text);
            });
        }

        function detectIntent(message) {
            const normalized = normalizeMessage(message);
            const timeframeMatch = parseTimeframe(normalized);
            const timeFilter = timeframeMatch ? timeframeMatch.value : null;
            const timeframeOnly = timeframeMatch && normalized === timeframeMatch.matched;
            const tickerMatch = extractTicker(normalized);
            const ticker = tickerMatch ? tickerMatch.ticker : null;
            const tickerAlias = tickerMatch ? tickerMatch.alias : null;
            const tickerOnly = tickerAlias && normalized === tickerAlias;

            const result = {
                intent: 'unknown',
                ticker,
                timeFilter,
                normalized,
                multipleTickers: tickerMatch ? tickerMatch.multiple : false
            };
            const hasPriceKeyword = containsAny(normalized, KEYWORDS.price);
            const hasHoldingsKeyword = containsAny(normalized, KEYWORDS.holdings);
            const hasTotalKeyword = containsAny(normalized, KEYWORDS.total_value);
            const hasAllocationKeyword = containsAny(normalized, KEYWORDS.allocation);
            const hasBestKeyword = containsAny(normalized, KEYWORDS.best_asset);
            const hasWorstKeyword = containsAny(normalized, KEYWORDS.worst_asset);
            const hasPerformanceSummaryKeyword = containsAny(normalized, KEYWORDS.performance_summary);
            const hasAssetPerformanceKeyword = containsAny(normalized, KEYWORDS.asset_performance);
            const mentionsHowMuch = normalized.includes('how much');

            const hasGreeting = containsAny(normalized, KEYWORDS.greeting);
            if (hasGreeting) {
                result.intent = 'greeting';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (containsAny(normalized, KEYWORDS.help)) {
                result.intent = 'help';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (timeframeOnly) {
                result.intent = 'time_filter_only';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (ticker && hasAssetPerformanceKeyword) {
                result.intent = 'asset_performance';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (ticker && (tickerOnly || hasPriceKeyword)) {
                result.intent = 'price';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (ticker && (hasHoldingsKeyword || mentionsHowMuch)) {
                result.intent = 'holdings';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (hasHoldingsKeyword) {
                result.intent = 'holdings';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (hasTotalKeyword) {
                result.intent = 'total_value';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (hasAllocationKeyword) {
                result.intent = 'allocation';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (hasBestKeyword) {
                result.intent = 'best_asset';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (hasWorstKeyword) {
                result.intent = 'worst_asset';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (hasPerformanceSummaryKeyword) {
                result.intent = ticker ? 'asset_performance' : 'performance_summary';
                debugMode && console.log('[PortfolioAssistant]', result);
                return result;
            }

            if (timeFilter) {
                result.intent = 'time_filter';
            }

            debugMode && console.log('[PortfolioAssistant]', result);
            return result;
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

        function formatPercent(value) {
            if (typeof value !== 'number') {
                return `${value}%`;
            }
            return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
        }

        function persistTimeframe(value) {
            state.currentTimeFilter = value || DEFAULT_TIMEFRAME;
            try {
                localStorage.setItem(timeframeStorageKey, state.currentTimeFilter);
            } catch (error) {
                // ignore storage failures
            }
        }

        function handleIntent(intentResult) {
            const activeTimeframe = intentResult.timeFilter || state.currentTimeFilter || DEFAULT_TIMEFRAME;
            if (intentResult.timeFilter) {
                persistTimeframe(intentResult.timeFilter);
            }
            const snapshot = getPortfolioSnapshot(activeTimeframe);
            const timeframeSuffix = activeTimeframe && activeTimeframe !== DEFAULT_TIMEFRAME
                ? ` for ${activeTimeframe}`
                : '';
            const multiTickerSuffix = intentResult.multipleTickers ? ' (first ticker mentioned)' : '';

            let reply;
            switch (intentResult.intent) {
                case 'greeting':
                    reply = `Hello ${username}! I'm ready to walk through your portfolio${timeframeSuffix || ' anytime'}.`;
                    break;
                case 'help':
                    reply = 'Try asking things like "total value", "allocation", "best performing asset", "price of BTC", or "how much ETH do I have".';
                    break;
                case 'total_value':
                    reply = `Your portfolio is currently valued at ${formatCurrency(snapshot.totalValue)}${timeframeSuffix || ''}.`;
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
                case 'price':
                    if (intentResult.ticker && snapshot.prices[intentResult.ticker]) {
                        reply = `${intentResult.ticker} price${timeframeSuffix || ''}: ${formatCurrency(snapshot.prices[intentResult.ticker])} (mock data)${multiTickerSuffix}.`;
                    } else {
                        reply = `I only track ${Object.keys(snapshot.prices).join(', ')} for now.`;
                    }
                    break;
                case 'holdings': {
                    if (intentResult.ticker) {
                        const holding = snapshot.holdings.find(h => h.ticker === intentResult.ticker);
                        reply = holding
                            ? `You currently hold ${holding.amount} ${intentResult.ticker}${multiTickerSuffix}.`
                            : `I don't see any ${intentResult.ticker} in your holdings yet.`;
                    } else {
                        const topHoldings = snapshot.holdings
                            .slice(0, 4)
                            .map(h => `${h.amount} ${h.ticker}`)
                            .join(' • ');
                        reply = topHoldings
                            ? `Holdings snapshot: ${topHoldings}.`
                            : 'I could not find holdings data yet.';
                    }
                    break;
                }
                case 'performance_summary': {
                    const perfSummary = snapshot.performance
                        .map(asset => `${asset.ticker}: ${formatPercent(asset.pnlPct)}`)
                        .join(' • ');
                    reply = perfSummary
                        ? `Performance${timeframeSuffix}: ${perfSummary}.`
                        : 'No performance data yet.';
                    break;
                }
                case 'asset_performance': {
                    const asset = snapshot.performance.find(p => p.ticker === intentResult.ticker);
                    reply = asset
                        ? `${asset.ticker} performance${timeframeSuffix}: ${formatPercent(asset.pnlPct)}${multiTickerSuffix}.`
                        : `I don't have performance data for ${intentResult.ticker} yet.`;
                    break;
                }
                case 'time_filter':
                case 'time_filter_only':
                    reply = `Timeframe locked to ${state.currentTimeFilter}. Ask anything else when you're ready.`;
                    break;
                case 'unknown':
                default:
                    reply = 'I can share totals, allocations, holdings, prices, or performance (e.g., "ETH price", "best asset today", "show performance").';
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
        if (clearBtn) {
            clearBtn.addEventListener('click', clearConversation);
        }

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
