"""Web chat MiniMax ceiling (matches shared budget cap, never above $59)."""
MINIMAX_CAP_USD = 59.0


def enforce_chat_cap(budget):
    # Called only inside the dedicated API child process, never the scheduler.
    budget.CAP_USD = min(budget.CAP_USD, MINIMAX_CAP_USD)
