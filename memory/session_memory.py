from __future__ import annotations

try:
    from langchain.memory import ConversationBufferMemory
except ImportError:
    ConversationBufferMemory = None


def get_memory():
    if ConversationBufferMemory is None:
        return None
    return ConversationBufferMemory(memory_key="chat_history", return_messages=True)
