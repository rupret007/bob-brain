"""One supported capability registry for advice, routing and executors."""
BILLING_FACTS = {
    'source': 'https://learn.chatgpt.com/docs/pricing',
    'verified_on': '2026-10-03',
    'openai_api_billing': 'ChatGPT Pro does not pay for OpenAI API requests. ChatGPT-authenticated Codex uses the plan’s allowance; API-key requests are billed separately. [OpenAI pricing](https://learn.chatgpt.com/docs/pricing)',
    'subscription_scope': 'ChatGPT Work and Codex share the applicable plan allowance. An included subscription route is not unlimited, and its remaining allowance or extra-usage settings must be observed separately.',
}
ROUTES = {
    'codex': dict(tasks=['conversation', 'local coding', 'scoped project jobs'], auth='ChatGPT login or separately billed API; inspect observed mode',
                  reach='Two supported routes: (1) conversation through the CLI reply adapter using supplied context; (2) local file and coding work in assigned worktrees through the scoped executor. A limitation of route 1 does not remove route 2. Current permission and input availability still determine whether a specific task can run.',
                  billing='ChatGPT plan allowance when authenticated with ChatGPT; credits may apply',
                  conversation_quality='Supported conversation adapter; current comparative answer quality and remaining quota are not established by login',
                  report_adapter='No qualified tool-free bounded report adapter'),
    'claude': dict(tasks=['explicitly selected conversation', 'bounded project reports', 'short reviews'], auth='claude.ai subscription login for bounded reports; inspect observed mode for other routes',
                   reach='Supports ordinary conversation through the explicitly selected Claude chat adapter. Separately, the bounded report executor reads supplied evidence and returns a saved artifact; its report-only restrictions do not limit the conversation adapter.',
                   billing='Claude plan allowance; actual extra usage and invoice unverified',
                   conversation_quality='Supported conversation adapter; comparative quality and current allowance still need observation, just as for Codex and Cursor',
                   report_adapter='One attempt, high effort, requested Opus family, no model tools; model identity checked'),
    'cursor': dict(tasks=['conversation', 'local coding', 'scoped project jobs'], auth='Observe Cursor authenticated status; login alone does not prove funding route',
                   reach='Two supported routes: conversation through the CLI ask-mode adapter using supplied context, and local file/coding work in assigned worktrees through the scoped executor. Current permission and input availability still govern each task.',
                   billing='Cursor account; included versus on-demand usage unverified',
                   conversation_quality='Supported conversation adapter; no measured quality or capacity guarantee from authentication alone',
                   dependency='Reducing Cursor may reduce Grok Bot included allowance; verify linked account before changing plan'),
    'gemini': dict(tasks=['conversation', 'reasoning', 'voice', 'research', 'evidence reports'], auth='Funded Gemini API account',
                   reach='Configured Web Bob tools; bounded server evidence and approved actions', billing='Separately metered API; ledger charge/reservation is not account credit balance',
                   default='Keep existing quality settings until representative comparison qualifies an alternative'),
    'minimax': dict(tasks=['conversation fallback', 'evidence reports'], auth='Configured API account',
                    reach='Supplied evidence; no native local command execution', billing='Separately metered API under existing budget stops'),
    'dot': dict(tasks=['owner-relayed review handoffs'], auth='Reported Mini/connected-app access; native product route unverified',
                reach='Reported read access; journal-write check failed', billing='Ordinary Dot conversation and Work/Codex task usage differ; task allowance shared with ChatGPT Work/Codex',
                automatic_dispatch=False),
    'grok': dict(tasks=['owner-relayed handoffs', 'native receiver catch-up when available'], auth='Historical receiver evidence only',
                 reach='Grok reported local bridge reads; no authenticated Web Bob push interface established',
                 billing='Grok Bot allowance may depend on Cursor or linked SuperGrok; xAI API is separate; no assumed capacity stacking',
                 automatic_dispatch=False),
}

CAPABILITIES = {
    "codex": {"conversation", "scoped-code"},
    "cursor": {"conversation", "scoped-code"},
    "claude": {"conversation", "bounded-report"},
    "gemini": {"conversation", "vision", "voice", "research", "evidence-report"},
    "minimax": {"conversation", "evidence-report"},
    "dot": {"manual-handoff"},
    "grok": {"manual-handoff"},
}

def supports(resource, capability):
    return capability in CAPABILITIES.get(resource, set())
