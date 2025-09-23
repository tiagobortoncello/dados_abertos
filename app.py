import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import altair as alt

# Seu código de configuração da API e URL...

# URL da nova API para teste
url = "O_LINK_DA_SUA_NOVA_API_AQUI"

@st.cache_data(ttl=3600)
def carregar_dados_da_api():
    try:
        st.info("Buscando dados na nova API...")
        response = requests.get(url, params={"formato": "json"})
        
        # Levanta um erro se o status code não for 200
        response.raise_for_status() 
        
        dados = response.json()
        
        # AQUI É O PONTO CRÍTICO:
        # Se a nova API não tiver uma chave 'list', isso pode falhar.
        # Ajuste a linha abaixo para a estrutura da sua nova API.
        df = pd.DataFrame(dados.get('list', [])) 
        
        if not df.empty:
            df = df[['siglaTipo', 'numero', 'ano', 'ementa', 'apresentacao']]
        return df
        
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro no servidor da API: {e}. Verifique o link e tente novamente.")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a API: {e}. Verifique se o link está correto.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar os dados da nova API: {e}. Verifique a estrutura JSON.")
        return pd.DataFrame()

# O resto do seu código...

if not df_proposicoes.empty and genai.api_key:
    # ... código para a barra de pesquisa e assistente ...
else:
    # A mensagem de aviso abaixo agora é menos necessária,
    # pois as mensagens de erro detalhadas serão exibidas acima.
    st.warning("Não foi possível carregar os dados. Verifique os erros acima.")
