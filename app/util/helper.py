from browser_use.agent.service import AgentHistoryList


def calculate_total_token(historyList: AgentHistoryList) -> int:
    total = 0
    for h in historyList.history:
        if h.metadata:
            total += h.metadata.input_tokens

    return total

