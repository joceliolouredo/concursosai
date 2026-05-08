import streamlit as st
from groq import Groq
import PyPDF2
import json
import sqlite3
import pandas as pd
import random

# ==============================================================================
# 1. CONFIGURAÇÃO DE SEGURANÇA E IA (GROQ)
# ==============================================================================
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("⚠️ Erro: Chave de API não encontrada. Vá em 'Advanced Settings' -> 'Secrets' e adicione: GROQ_API_KEY = 'SUA_CHAVE'")

# ==============================================================================
# 2. SISTEMA DE BANCO DE DADOS (HUB)
# ==============================================================================
def init_db():
    conn = sqlite3.connect('hub_concursos.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS apostilas (id INTEGER PRIMARY KEY, nome TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS questoes 
                 (id INTEGER PRIMARY KEY, apostila_id INTEGER, pergunta TEXT, 
                 opcoes TEXT, correta TEXT, justificativa TEXT)''')
    conn.commit()
    conn.close()

def save_apostila(nome):
    conn = sqlite3.connect('hub_concursos.db')
    c = conn.cursor()
    c.execute('INSERT INTO apostilas (nome) VALUES (?)', (nome,))
    id_apostila = c.lastrowid
    conn.commit()
    conn.close()
    return id_apostila

def save_questoes(apostila_id, questoes):
    conn = sqlite3.connect('hub_concursos.db')
    c = conn.cursor()
    for q in questoes:
        c.execute('INSERT INTO questoes (apostila_id, pergunta, opcoes, correta, justificativa) VALUES (?, ?, ?, ?, ?)',
                  (apostila_id, q['pergunta'], json.dumps(q['opcoes']), q['correta'], q['justificativa']))
    conn.commit()
    conn.close()

def get_apostilas_com_contagem():
    """Retorna as
