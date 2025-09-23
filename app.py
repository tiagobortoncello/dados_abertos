import streamlit as st
import pandas as pd
import requests

st.set_page_config(layout="wide")

# URL da API da ALMG para Proposições
url = "https://dadosabertos.almg.gov.br/api/v2/proposicoes/pesquisa/avancada"

@st.cache_data(ttl=3600)
def carregar_dados_da_api():
    """Faz a chamada à API da ALMG e retorna um DataFrame do pandas."""
    try:
        st.info("Buscando dados na API da ALMG...")
        response = requests.get(url, params={"formato": "json"})
        response.raise_for_status() # Levanta um erro para códigos de status ruins
        
        dados = response.json()
        df = pd.DataFrame(dados.get('list', []))
        
        if not df.empty:
            df = df[['id', 'siglaTipo', 'numero', 'ano', 'ementa', 'apresentacao']]
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao carregar os dados da API: {e}")
        return pd.DataFrame()

# Título e informações do dashboard
st.title("Proposições da Assembleia Legislativa de Minas Gerais (ALMG)")
st.caption("Dados atualizados em tempo real, diretamente da API.")

# Carrega e exibe os dados
df_proposicoes = carregar_dados_da_api()

if not df_proposicoes.empty:
    st.write(f"Última atualização: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M:%S')}")
    st.dataframe(df_proposicoes, use_container_width=True)
else:
    st.warning("Nenhum dado encontrado.")
