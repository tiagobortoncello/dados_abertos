import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import json 
import datetime 

st.set_page_config(layout="wide")

# --- CONFIGURAÇÕES E CONSTANTES ---

CHAVE_GEMINI_CONFIGURADA = False 
# Tenta configurar a chave da API do Gemini
if "GEMINI_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        CHAVE_GEMINI_CONFIGURADA = True
    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini: {e}")
else:
    st.warning("Chave da API do Gemini não encontrada nos segredos do Streamlit.")

# --- MAPA COMPLETO DE ENDPOINTS E PARÂMETROS ---
# Note a diferença no formato de data (YYYY-MM-DD vs AAAAMMDD)

ENDPOINTS_MAP = {
    "proposicoes": {
        "url": "https://dadosabertos.almg.gov.br/api/v2/proposicoes/pesquisa/avancada",
        "description": "Consultas sobre projetos de lei (PL), PECs e proposições, usando filtros de tipo (tp), conteúdo (expr) e data (YYYY-MM-DD).",
        "date_format": "YYYY-MM-DD",
        "params": {
            'tp': 'CÓDIGO NUMÉRICO do Tipo de Proposição (Ex: 10 para PL, 100 para PEC).',
            'expr': 'Palavra-chave para pesquisa na Ementa.',
            'dataInicial': 'Data de apresentação inicial (formato YYYY-MM-DD)',
            'dataFinal': 'Data de apresentação final (formato YYYY-MM-DD)',
            'ord': 'Código NUMÉRICO de Ordenação (Ex: 0=Mais Recente)',
        }
    },
    "deputados": {
        "url": "https://dadosabertos.almg.gov.br/api/v2/deputados/em_exercicio",
        "description": "Lista de deputados estaduais em exercício. Pode ser filtrada por partido ou nome.",
        "date_format": None,
        "params": {
            'siglaPartido': 'Sigla do Partido do deputado (Ex: PT, NOVO, PSDB)',
            'nome': 'Nome do deputado (Filtra por parte do nome)',
        }
    },
    "agenda": {
        "url": "https://dadosabertos.almg.gov.br/api/v2/agenda/diaria/home/pesquisa",
        "description": "Itens da Agenda Diária por período (AAAAMMDD) e palavra-chave.",
        "date_format": "AAAAMMDD",
        "params": {
            'expr': 'Palavra-chave para pesquisa no item da agenda.',
            'ini': 'Data inicial (formato AAAAMMDD)',
            'fim': 'Data final (formato AAAAMMDD)',
            'cat': 'Lista de identificadores de categorias (código numérico separado por vírgula).',
        }
    },
    "diario_legislativo": {
        "url": "https://dadosabertos.almg.gov.br/api/v2/diario_legislativo/pesquisa",
        "description": "Pesquisa no Diário do Legislativo por período (AAAAMMDD) e palavra-chave.",
        "date_format": "AAAAMMDD",
        "params": {
            'expressao': 'Palavra-chave ou Expressão para pesquisa no diário.',
            'ini': 'Data inicial (formato AAAAMMDD)',
            'fim': 'Data final (formato AAAAMMDD)',
        }
    },
    "comissoes_reunioes": {
        "url": "https://dadosabertos.almg.gov.br/api/v2/comissoes/reunioes/pesquisa",
        "description": "Pesquisa resultados de reuniões de comissão por data (AAAAMMDD) e palavra-chave.",
        "date_format": "AAAAMMDD",
        "params": {
            'expr': 'Palavra-chave para pesquisa na reunião.',
            'ini': 'Data inicial (formato AAAAMMDD)',
            'fim': 'Data final (formato AAAAMMDD)',
            'tipoReun': 'Código NUMÉRICO do tipo de reunião (Ex: 1 para Ordinária, 2 para Especial).',
        }
    },
    "contratos": {
        "url": "https://dadosabertos.almg.gov.br/api/v2/prestacao_contas/contratos/pesquisa",
        "description": "Pesquisa de Contratos por objeto ou fornecedor.",
        "date_format": None,
        "params": {
            'obj': 'Objeto do Contrato.',
            'forn': 'Nome ou CNPJ do fornecedor.',
        }
    }
}
# --- FIM DO MAPA ---

# --- FUNÇÕES ---

def gerar_parametros_com_gemini(pergunta_usuario, endpoints_map):
    """Usa o Gemini para converter a pergunta em um JSON estruturado com endpoint e parâmetros."""
    
    if not CHAVE_GEMINI_CONFIGURADA:
        return None
    
    # Monta a lista de endpoints e seus parâmetros para o prompt
    endpoint_descriptions = []
    for nome, config in endpoints_map.items():
        parametros = ", ".join([f"{k} ({v})" for k, v in config["params"].items()])
        endpoint_descriptions.append(f"- **{nome}**: {config['description']}. Filtros: {parametros}")

    prompt = f"""
    Sua tarefa é analisar a pergunta do usuário e retornar um **objeto JSON** estruturado em duas chaves: 'endpoint' e 'params'.

    1.  **Escolha do 'endpoint':** Determine qual dos endpoints listados abaixo é o mais adequado.
    2.  **Geração dos 'params':** Gere os filtros necessários para o endpoint escolhido.

    Endpoints Disponíveis:
    {'\n'.join(endpoint_descriptions)}

    Instruções para o JSON:
    - O JSON deve ter a estrutura: {{ "endpoint": "nome_do_endpoint", "params": {{ "filtro1": "valor1", ... }} }}
    - Use os CÓDIGOS NUMÉRICOS (Ex: tp=10, tipoReun=1) quando necessário.
    - Se o usuário perguntar por um ANO, inclua-o como "ano" nos params (o código Python irá convertê-lo para o formato de data correto).
    - Se a pergunta for genérica demais ou não se encaixar em nenhum endpoint, retorne APENAS: {{ "endpoint": "nenhum", "params": {{}} }}

    Pergunta do Usuário: "{pergunta_usuario}"
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt, stream=False)
        
        resultado = json.loads(response.text.strip())
        
        if 'endpoint' in resultado and 'params' in resultado:
            return resultado
        else:
            st.error("Erro de estrutura: Gemini não retornou 'endpoint' e 'params'.")
            return None
        
    except json.JSONDecodeError:
        st.error(f"Erro: Gemini não retornou um JSON válido. Resposta: {response.text}")
        return None
    except Exception as e:
        st.error(f"Erro ao gerar JSON: {e}")
        return None


def carregar_dados_da_api_dinamico(resultado_gemini):
    """Faz a chamada à API com base na escolha do Gemini e trata a conversão de datas."""
    
    if resultado_gemini is None:
        return pd.DataFrame()

    endpoint_key = resultado_gemini.get("endpoint")
    params = resultado_gemini.get("params", {})
    
    if endpoint_key == "nenhum":
        st.warning("O Gemini não identificou um endpoint apropriado para a sua pergunta.")
        return pd.DataFrame()
        
    if endpoint_key not in ENDPOINTS_MAP:
        st.error(f"Endpoint '{endpoint_key}' é inválido. Verifique o mapa de endpoints.")
        return pd.DataFrame()

    config = ENDPOINTS_MAP[endpoint_key]
    url_base = config["url"].split('{')[0] # Remove possíveis path parameters da URL base
    
    # 1. CONVERSÃO: Tratar o parâmetro 'ano' (se gerado)
    if 'ano' in params:
        ano = params.pop('ano')
        date_format = config.get("date_format")
        
        if date_format == "YYYY-MM-DD":
            # Usado pelo endpoint 'proposicoes'
            params['dataInicial'] = f'{ano}-01-01'
            params['dataFinal'] = f'{ano}-12-31'
            st.info(f"Convertendo ano={ano} para o intervalo YYYY-MM-DD: {params['dataInicial']} a {params['dataFinal']}")
        
        elif date_format == "AAAAMMDD":
            # Usado pelos endpoints 'agenda', 'diario_legislativo', 'comissoes_reunioes'
            params['ini'] = f'{ano}0101'
            params['fim'] = f'{ano}1231'
            st.info(f"Convertendo ano={ano} para o intervalo AAAAMMDD: {params['ini']} a {params['fim']}")


    # 2. FILTRO DE EMERGÊNCIA (Apenas para o endpoint de proposições instável)
    if endpoint_key == "proposicoes" and len(params) <= 1: 
        params['tp'] = 10 
        params['dataInicial'] = '2023-01-01'
        params['dataFinal'] = '2023-03-01' 
        st.warning("O Gemini não gerou filtros restritivos. Acionando filtro de emergência (tp=10, Jan-Mar/2023).")
        st.info(f"Filtros de emergência: tp={params['tp']}, dataInicial={params['dataInicial']}")
    
    try:
        st.info(f"Buscando dados no endpoint: **{endpoint_key}** | URL: {url_base} | Filtros: {params}")
        
        response = requests.get(url_base, params=params) 
        response.raise_for_status() 
        dados = response.json()
        
        # TRATAMENTO DE RESPOSTA
        if 'list' in dados:
            df = pd.DataFrame(dados.get('list', []))
        elif 'resultadoPesquisa' in dados and 'lista' in dados['resultadoPesquisa']:
            df = pd.DataFrame(dados['resultadoPesquisa'].get('lista', []))
        elif isinstance(dados, list):
            df = pd.DataFrame(dados)
        else:
            # Tenta pegar a primeira chave que é uma lista, como listaDeputado, listaMunicipio, etc.
            list_key = next((k for k, v in dados.items() if isinstance(v, list)), None)
            if list_key:
                 df = pd.DataFrame(dados.get(list_key, []))
            else:
                 st.warning("A API retornou dados que não puderam ser convertidos em DataFrame ou era um único objeto.")
                 df = pd.DataFrame([dados])
                 
        return df
        
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro no servidor da API ({e.response.status_code}): {e}. O endpoint da ALMG está rejeitando os filtros ou está fora do ar.")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão: {e}. Verifique sua conexão com a internet.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao processar os dados: {e}")
        return pd.DataFrame()


# --- LÓGICA PRINCIPAL DA APLICAÇÃO ---

st.title("Assistente de Dados Abertos da ALMG (Multi-Endpoint)")
st.subheader("Use linguagem natural para consultar **Proposições, Deputados, Comissões, Agenda, Diário e Contratos**.")

with st.expander("❓ Dicas de Perguntas (Seja Específico!)"):
    st.markdown("""
    O assistente agora pode consultar diversos temas. Lembre-se de ser **o mais específico possível** para o Gemini conseguir selecionar o endpoint e os filtros corretos.

    ### 📝 Proposições (PL, PEC, etc. - API Instável):
    > **"Quero as proposições do tipo PL (Projeto de Lei) de 2023 que contenham a palavra 'saúde' na ementa."**

    ### 👤 Deputados:
    > **"Quais são os deputados do partido PT?"**

    ### 🗓️ Agenda:
    > **"Me mostre os itens da agenda de 2024 que falem sobre 'educação'."**

    ### 📰 Diário:
    > **"Pesquise o diário de janeiro de 2024 que contenha a palavra 'convocação'."**
    
    ### 💰 Contratos:
    > **"Quais são os contratos que têm 'locação' no objeto?"**
    """)

user_query = st.text_input("Sua pergunta ou filtro:", placeholder="Ex: Quais são os deputados do partido PT? OU: Quero as PLs de 2023 sobre saúde.")

if user_query:
    st.markdown("---")
    
    if not CHAVE_GEMINI_CONFIGURADA: 
        st.error("Por favor, configure sua chave da API do Gemini.")
    
    else:
        # 1. GERA O ENDPOINT E OS PARÂMETROS COM O GEMINI
        with st.spinner("Analisando sua pergunta e escolhendo o endpoint..."):
            resultado_gemini = gerar_parametros_com_gemini(user_query, ENDPOINTS_MAP)
        
        # 2. CARREGA OS DADOS COM BASE NA ESCOLHA DO GEMINI
        if resultado_gemini and resultado_gemini.get('endpoint') != 'nenhum':
             with st.spinner(f"Buscando dados no endpoint: {resultado_gemini.get('endpoint')}..."):
                 df_dados = carregar_dados_da_api_dinamico(resultado_gemini)
        else:
            df_dados = pd.DataFrame()

        # 3. EXIBIÇÃO
        if not df_dados.empty:
            
            st.success(f"Foram carregados **{len(df_dados)}** resultados do endpoint **{resultado_gemini.get('endpoint')}**.")
            st.dataframe(df_dados)
        else:
            st.warning("Nenhum dado foi encontrado ou a API falhou. Tente refinar sua pergunta, garantindo que você especificou o tema (Proposições, Deputados, etc.) e os filtros (ano, palavra-chave).")
