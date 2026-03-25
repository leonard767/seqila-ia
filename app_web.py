import streamlit as st
from groq import Groq
import edge_tts
import asyncio
import base64
import os
import sqlite3

# --- 1. INICIALIZACIÓN DE MEMORIA Y VARIABLES ---
def init_db():
    conn = sqlite3.connect('seqila_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history (username TEXT, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Súper importante: Inicializar estas variables ANTES de cualquier otra cosa
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. APARIENCIA GEMINI / CHATGPT ---
st.set_page_config(page_title="Seqila IA", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0c0e12; color: #e3e3e3; }
    .stChatMessage { border-radius: 20px; padding: 15px 15%; border: none !important; }
    .stChatMessage[data-test="stChatMessageAssistant"] { background-color: #1a1e26 !important; }
    .stChatInputContainer { margin: 0 15%; border: 1px solid #00f2fe !important; border-radius: 25px; }
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 3. LÓGICA DE AUDIO (MEJORADA PARA CELULAR) ---
async def generar_voz(texto, voz):
    path = "temp_audio.mp3"
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(path)
    return path

def reproducir_audio(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        # Añadimos controles para que si el autoplay falla, puedas darle Play manual
        audio_html = f"""
            <audio autoplay="true" controls style="width: 100%; height: 30px; margin-top: 10px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(audio_html, unsafe_allow_html=True)

# --- 4. PANTALLA DE LOGIN ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso a Seqila IA</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        user_input = st.text_input("Usuario")
        pw_input = st.text_input("Contraseña", type="password")
        if st.button("Entrar / Registrar"):
            if user_input and pw_input:
                conn = sqlite3.connect('seqila_memory.db')
                c = conn.cursor()
                c.execute("SELECT password FROM users WHERE username = ?", (user_input,))
                res = c.fetchone()
                if res:
                    if res[0] == pw_input:
                        st.session_state.logged_in = True
                        st.session_state.username = user_input
                        st.rerun()
                    else: st.error("Contraseña incorrecta")
                else:
                    c.execute("INSERT INTO users VALUES (?, ?)", (user_input, pw_input))
                    conn.commit()
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    st.success("¡Usuario creado!")
                    st.rerun()
                conn.close()
    st.stop()

# --- 5. INTERFAZ DE CHAT ACTIVA ---
st.markdown(f"<h3 style='text-align: center; color: #00f2fe;'>Seqila IA | {st.session_state.username}</h3>", unsafe_allow_html=True)

# Cargar historial de la DB si el chat está vacío
if not st.session_state.messages:
    conn = sqlite3.connect('seqila_memory.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_history WHERE username = ?", (st.session_state.username,))
    hist = c.fetchall()
    if hist:
        st.session_state.messages = [{"role": r, "content": ct} for r, ct in hist]
    else:
        st.session_state.messages = [{"role": "system", "content": "Eres Seqila IA, asistente formal y divertida."}]
    conn.close()

# Mostrar mensajes
for m in st.session_state.messages:
    if m["role"] != "system":
        with st.chat_message(m["role"], avatar="🤖" if m["role"]=="assistant" else "👤"):
            st.markdown(m["content"])

# Input de usuario
if prompt := st.chat_input("Dígame, ¿en qué puedo ayudarle hoy?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Respuesta de IA
    with st.chat_message("assistant", avatar="🤖"):
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=st.session_state.messages
        )
        ans = res.choices[0].message.content
        st.markdown(ans)
        
        # Audio
        p = asyncio.run(generar_voz(ans, "es-MX-DaliaNeural"))
        reproducir_audio(p)
        
    # Guardar en Memoria (DB y Session)
    st.session_state.messages.append({"role": "assistant", "content": ans})
    conn = sqlite3.connect('seqila_memory.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat_history VALUES (?, 'user', ?)", (st.session_state.username, prompt))
    c.execute("INSERT INTO chat_history VALUES (?, 'assistant', ?)", (st.session_state.username, ans))
    conn.commit()
    conn.close()
