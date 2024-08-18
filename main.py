import streamlit as st
import sqlite3
import ollama
from typing import Dict, Generator
import re

conn = sqlite3.connect("conversation_history.db")
c = conn.cursor()

def create_chat_table(chat_id: str):
    table_name = f"chat_{chat_id}"
    c.execute(f'''CREATE TABLE IF NOT EXISTS {table_name}
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return table_name

def save_message(table_name: str, role: str, content: str):
    c.execute(f"INSERT INTO {table_name} (role, content) VALUES (?, ?)", (role, content))
    conn.commit()

def load_conversation(table_name: str):
    c.execute(f"SELECT role, content FROM {table_name} ORDER BY timestamp ASC")
    return [{"role": role, "content": content} for role, content in c.fetchall()]

def list_chat_tables():
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'chat_%'")
    return [table[0] for table in c.fetchall()]

def extract_chat_id(table_name: str):
    return re.sub(r'^chat_', '', table_name)

def get_ai_preview(table_name: str):
    c.execute(f"SELECT content FROM {table_name} WHERE role='assistant' ORDER BY timestamp ASC LIMIT 1")
    result = c.fetchone()
    if result:
        return " ".join(result[0].split()[:6]) + ("..." if len(result[0].split()) > 6 else "")
    return "No AI response"

def ollama_generator(model_name: str, messages: Dict) -> Generator:
    stream = ollama.chat(model=model_name, messages=messages, stream=True)
    for chunk in stream:
        yield chunk['message']['content']

def delete_chat_table(table_name: str):
    c.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.commit()

st.sidebar.title("🤖 Ollama with Streamlit")

if st.sidebar.button("Start New Chat 💬"):
    chat_id = len(list_chat_tables()) + 1
    table_name = create_chat_table(str(chat_id))
    st.session_state.current_chat = table_name
    st.session_state.messages = []

with st.sidebar.container(border=True):
    st.session_state.selected_model = st.selectbox(
    "Please select the model:", [model["name"] for model in ollama.list()["models"]])

with st.sidebar.container(border=True):
    available_chats = list_chat_tables()
    chat_options = [
        f"Chat {extract_chat_id(name)}: {get_ai_preview(name)}" for name in available_chats
    ]
    selected_chat_option = st.selectbox("Select a chat to continue:", chat_options[::-1])
    if selected_chat_option:
        selected_chat_id = selected_chat_option.split(":")[0].strip().replace("Chat ", "")
        table_name = f"chat_{selected_chat_id}"
        st.session_state.current_chat = table_name
        st.session_state.messages = load_conversation(table_name)

with st.sidebar.container(border=True):
    available_chats = list_chat_tables()
    chat_options = [
        f"Chat {extract_chat_id(name)}: {get_ai_preview(name)}" for name in available_chats
    ]
    selected_chats_to_delete = st.multiselect("Select chats to delete:", chat_options)
    if st.button("Delete Selected Chats 🗑️"):
        if selected_chats_to_delete:
            for selected_chat_option in selected_chats_to_delete:
                selected_chat_id = selected_chat_option.split(":")[0].strip().replace("Chat ", "")
                table_name = f"chat_{selected_chat_id}"
                delete_chat_table(table_name)
            st.session_state.current_chat = None
            st.session_state.messages = []
            st.rerun()

if "messages" in st.session_state:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("How could I help you?"):
    user_message = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_message)
    save_message(st.session_state.current_chat, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
    assistant_message = {"role": "assistant", "content": ""}
    with st.chat_message("assistant"):
        response_container = st.empty()
        response = ""
        for chunk in ollama_generator(st.session_state.selected_model, st.session_state.messages):
            response += chunk
            response_container.markdown(response)
        assistant_message["content"] = response
    st.session_state.messages.append(assistant_message)
    save_message(st.session_state.current_chat, "assistant", response)

conn.close()
