"""This job's $48 ceiling, independent of increases to background-lane credit."""
MINIMAX_CAP_USD = 48.0


def enforce_chat_cap(budget):
    # Called only inside the dedicated API child process, never the scheduler.
    budget.CAP_USD = min(budget.CAP_USD, MINIMAX_CAP_USD)
