import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import json 
import altair as alt 

st.set_page_config(layout="wide")

# --- CONFIGURAÇÕES E CONSTANTES ---

# Variável de controle para verificar o status da chave
CHAVE_GEMINI_CONFIGURADA = False 

# Configura a chave da API do Gemini de forma segura
if "GEMINI_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        CHAVE_GEMINI_CONFIGURADA = True
    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini: {e}")
else:
    st.warning("Chave da API do Gemini não encontrada nos segredos do Streamlit.")

# URL da API da ALMG
url_api = "https://dadosabertos.almg.gov.br/api/v2/proposicoes/pesquisa/avancada"

# Mapeamento de Parâmetros Válidos da API (O 'DNA' que o Gemini usará)
PARAMETROS_ALMG = {
    'siglaTipo': 'Sigla do tipo de Proposição (Ex: PL, PEC, REQ)',
    'numero': 'Número da Proposição (apenas números)',
    'ano': 'Ano da Proposição (apenas 4 dígitos)',
    'palavraChave': 'Palavra-chave para pesquisa na Ementa',
    'dataInicial': 'Data de apresentação inicial (formato YYYY-MM-DD)',
    'itensPorPagina': 'Limite de resultados (padrão 100, máximo 500)',
    'pagina': 'Número da página (para paginação)'
}

# --- FUNÇÕES ---

def gerar_parametros_com_gemini(pergunta_usuario, parametros_validos):
    """Usa o Gemini para converter a pergunta em um JSON de parâmetros da API."""
    
    # Esta verificação garante que a função só será executada se a chave estiver configurada
    if not CHAVE_GEMINI_CONFIGURADA:
        return {}
        
    lista_de_parametros = "\n".join([f"- {k} ({v})" for k, v in parametros_validos.items()])

    prompt = f"""
    Sua tarefa é converter a pergunta do usuário em um **objeto JSON** contendo os parâmetros de consulta válidos para a API de Proposições da ALMG.

    Parâmetros Válidos:
    {lista_de_parametros}
    
    Instruções:
    1. Responda **APENAS** com o objeto JSON. Não inclua texto, explicação ou formatação Markdown (ex: ```json).
    2. O JSON deve conter apenas os parâmetros que foram explicitamente pedidos ou sugeridos na pergunta.
    3. Use o tipo de dado correto (string, número).
    4. Se o usuário perguntar por algo que a API não pode filtrar (ex: 'quantas proposições existem?'), retorne um JSON vazio: {{}}.

    Exemplos:
    - Pergunta: "Quero todos os projetos de lei (PL) do ano de 2024"
    - Resposta: {{"siglaTipo": "PL", "ano": 2024}}
    
    - Pergunta: "Busque por propostas com a palavra chave 'saneamento'"
    - Resposta: {{"palavraChave": "saneamento"}}

    Pergunta do Usuário: "{pergunta_usuario}"
    """
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt, temperature=0.1)
        
        # Tenta carregar o JSON (o Gemini deve retornar APENAS o JSON)
        return json.loads(response.text.strip())
        
    except json.JSONDecodeError:
        st.error(f"Erro: O Gemini não retornou um JSON válido. Resposta recebida: {response.text}")
        return {}
    except Exception as e:
        st.error(f"Erro ao gerar JSON de parâmetros: {e}")
        return {}


def carregar_dados_da_api_dinamico(url, params=None):
    """Faz a chamada à API com os parâmetros de filtro e retorna um DataFrame."""
    
    if params is None:
        params = {}
    
    # Define um limite de resultados padrão se não for especificado
    if 'itensPorPagina' not in params:
        params['itensPorPagina'] = 100 
    
    try:
        st.info(f"Buscando dados na API da ALMG com filtros: {params}")
        
        response = requests.get(url, params=params) 
        
        response.raise_for_status() 
        dados = response.json()
        
        # CONFIRME se o nome da chave que contém a lista de proposições é 'list'
        df = pd.DataFrame(dados.get('list', []))
        
        if not df.empty:
             # Seleciona apenas as colunas úteis para a análise
             df = df[['siglaTipo', 'numero', 'ano', 'ementa', 'apresentacao']]
        return df
        
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro no servidor da API: {e}. O modelo Gemini pode ter gerado um filtro inválido ou a ALMG impôs um limite de requisições.")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a API: {e}. Verifique sua conexão com a internet.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar os dados da API: {e}. Verifique a estrutura JSON da resposta.")
        return pd.DataFrame()


# --- LÓGICA PRINCIPAL DA APLICAÇÃO ---

st.title("Assistente de Pesquisa e Análise de Proposições da ALMG (Beta)")
st.subheader("Use linguagem natural para filtrar e analisar os dados.")

user_query = st.text_input("Sua pergunta ou filtro:", placeholder="Ex: Quero as proposições PL de 2023 com a palavra 'saúde' e depois me diga o tipo mais comum")

if user_query:
    st.markdown("---")
    
    # A CORREÇÃO ESTÁ AQUI: Usamos a variável de controle definida no início.
    if not CHAVE_GEMINI_CONFIGURADA: 
        st.error("Por favor, configure sua chave da API do Gemini nos segredos do Streamlit para continuar com a geração de filtros.")
    
    else:
        # 1. GERA OS PARÂMETROS COM O GEMINI
        api_params = gerar_parametros_com_gemini(user_query, PARAMETROS_ALMG)
        
        # 2. CARREGA OS DADOS COM OS PARÂMETROS (DINAMICAMENTE)
        df_proposicoes = carregar_dados_da_api_dinamico(url_api, params=api_params)

        # 3. ANALISA OS DADOS FILTRADOS (Recuperando a lógica original)
        if not df_proposicoes.empty:
            
            st.success(f"Foram carregados **{len(df_proposicoes)}** proposições com os filtros aplicados.")
            
            # --- INSIRA AQUI A SUA LÓGICA DE ANÁLISE COM O SEGUNDO PROMPT DO GEMINI ---
            
            # Exemplo de onde a lógica de análise deve continuar:
            # st.info("Passo 3: Analisando os dados filtrados e gerando a resposta e o gráfico...")
            # data_string = df_proposicoes.to_string(index=False)
            # prompt_analise = f"""...use os dados {data_string} para responder a {user_query} e gere um gráfico..."""
            # ... (Chamada para o modelo e execução do código do gráfico)
            
            st.dataframe(df_proposicoes)
        else:
            st.warning("Nenhuma proposição foi encontrada com os filtros gerados. Tente refinar a sua pergunta.")
