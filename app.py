import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import altair as alt

st.set_page_config(layout="wide")

# Configura a chave da API do Gemini de forma segura
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Chave da API do Gemini não encontrada nos segredos do Streamlit. Por favor, adicione-a nas configurações do aplicativo.")

# URL da API da ALMG
url = "https://dadosabertos.almg.gov.br/api/v2/proposicoes/pesquisa/avancada"

@st.cache_data(ttl=3600)
def carregar_dados_da_api():
    """Faz a chamada à API e retorna um DataFrame do pandas."""
    try:
        st.info("Buscando dados na API da ALMG...")
        response = requests.get(url, params={"formato": "json"})
        response.raise_for_status() 
        dados = response.json()
        
        # O .get('list', []) evita erros se a chave 'list' não existir
        # Verifique esta linha se estiver usando outra API!
        df = pd.DataFrame(dados.get('list', []))
        
        if not df.empty:
            df = df[['siglaTipo', 'numero', 'ano', 'ementa', 'apresentacao']]
        return df
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro no servidor da API: {e}. Verifique o link e tente novamente.")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a API: {e}. Verifique sua conexão com a internet.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar os dados da API: {e}. Verifique a estrutura JSON.")
        return pd.DataFrame()

# Carrega os dados da API
df_proposicoes = carregar_dados_da_api()

st.title("Assistente de Dados da ALMG (Beta)")
st.subheader("Faça uma pergunta sobre as proposições ou peça um gráfico")

# O assistente só é exibido se os dados foram carregados e a chave do Gemini está configurada
if not df_proposicoes.empty and genai.api_key:
    user_query = st.text_input("Sua pergunta:", placeholder="Ex: Quantas proposições foram apresentadas por ano?")
    
    if user_query:
        st.info("Buscando a resposta e gerando o resultado...")
        
        # Converte o DataFrame para um formato de texto para o Gemini
        data_string = df_proposicoes.to_string(index=False)
        
        # Constrói o prompt com instruções para gerar código proativo
        prompt = f"""
        Você é um assistente de dados da Assembleia Legislativa de Minas Gerais.
        Sua função é analisar os dados fornecidos abaixo e responder à pergunta do usuário.

        Se a pergunta do usuário for sobre contagens, evoluções ou comparações (ex: "quantas proposições", "por ano", "mais comuns"), além da resposta textual, inclua um bloco de código Python com um gráfico para complementar a informação.

        Dados de proposições:
        {data_string}

        Instruções para gráficos:
        - Use a biblioteca `altair` para criar os gráficos.
        - O DataFrame se chama `df_proposicoes`.
        - Use a formatação de bloco de código Python: ```python ... ```
        - Exemplo de código para um gráfico de barras:
          ```python
          chart = alt.Chart(df_proposicoes).mark_bar().encode(
              x=alt.X('ano:O', title='Ano'),
              y=alt.Y('count():Q', title='Quantidade')
          ).properties(
              title='Número de Proposições por Ano'
          )
          st.altair_chart(chart, use_container_width=True)
          ```

        Pergunta do usuário: {user_query}
        """
        
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # --- Lógica para detectar e executar o código dentro da resposta ---
            if "```python" in response_text:
                parts = response_text.split("```python")
                text_part = parts[0].strip()
                code_part = parts[1].split("```")[0].strip()
                
                if text_part:
                    st.markdown(text_part)

                st.code(code_part, language='python')
                exec(code_part)
            else:
                st.markdown(response_text)
            
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")
            st.caption("Verifique se a sua chave da API está correta ou se a pergunta é clara.")

else:
    st.warning("Dados não carregados. Não é possível usar o assistente de dados.")
