import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ===== CONFIGURAÇÕES E AUTENTICAÇÃO =====
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"
]

creds = Credentials.from_service_account_file("credenciais.json", scopes=SCOPES)
client = gspread.authorize(creds)
drive_service = build("drive", "v3", credentials=creds)

# IDs do Google Drive / Sheets
ID_PASTA_ROADMAPS = ["1ZmYO3gh34Tn3C5hpU2USlEaQ8p7M1zmo","1vHNT56ZpkWmmZt8Zb8Y1SlqYuJyrj82V"]
ID_DESTINO = "1s2xGdJrJHrq95VPtVWxtdjmAYNQ0qdTsYgOnypBfRIs"

NOME_ABA_ORIGEM = "Presidência 2 - ROADMAP"
NOME_ABA_DESTINO = "NomeDaAbaDestino"

# ===== 1. BUSCAR PLANILHAS ATIVAS NO GOOGLE DRIVE =====
# trashed=false ignora arquivos na lixeira
todos_arquivos = []
for id in ID_PASTA_ROADMAPS:
    query = f"'{id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    arquivos = results.get("files", [])
    todos_arquivos.extend(arquivos)

print(f"Planilhas ativas encontradas: {len(todos_arquivos)}")

# ===== 2. CALCULAR MÉTRICA E GERAR 1 LINHA POR PLANILHA =====
relatorio_linhas = []

for arq in todos_arquivos:
    nome_planilha = arq["name"]
    id_planilha = arq["id"]
    
    try:
        planilha = client.open_by_key(id_planilha)
        
        # Pega a primeira aba da planilha (índice 0)
        aba = planilha.get_worksheet(0) 
        
        dados = aba.get_all_values()
        
        if len(dados) > 13:
            
            inicio = {
                "Setor": dados[3][2],
                "Gestão": dados[4][2],
                "Coordenador": dados[3][4],
                "Membros": dados[4][4],
                "Progresso": dados[3][8],
                "Assertividade": dados[4][8]

            }

            print(inicio)            

            if "PRAZO FINAL" in dados[12]:
                cabecalho = dados[12]
                linhas = dados[13:]
            else:
                cabecalho = dados[15]
                linhas = dados[16:]

            df = pd.DataFrame(linhas, columns=cabecalho)
            df = df[df.apply(lambda row: any(str(v).strip() for v in row), axis=1)]
            
            df["PRAZO FINAL"] = pd.to_datetime(df["PRAZO FINAL"], errors="coerce", dayfirst=True)

            mask_divisor = df["STATUS"].isin(["Finalizado", "Não Iniciado", "Em Execução"])
            mask_esperados = (df["PRAZO FINAL"] <= pd.Timestamp.today().normalize())

            total_divisor = len(df[mask_divisor])

            if total_divisor > 0:
                porcentagem = round((len(df[mask_esperados]) / total_divisor) * 100, 2)
            else:
                porcentagem = "Inválida"

            relatorio_linhas.extend([{
                "Nome do Roadmap / Projeto": nome_planilha,
                "Total Tarefas Mapeadas": len(df),
                "Porcentagem Esperada (%)": porcentagem,
                **inicio
            }])

            
    except Exception as e:
        print(f"Aviso: Não foi possível processar '{nome_planilha}': {e}")

# ===== 3. MONTA TABELA DE RESULTADOS =====
if relatorio_linhas:
    df_resultado = pd.DataFrame(relatorio_linhas)
else:
    df_resultado = pd.DataFrame(columns=["Nome do Roadmap / Projeto", "Total Tarefas Mapeadas", "Porcentagem Esperada (%)", *inicio.keys()])

dados_para_enviar = [df_resultado.columns.tolist()] + df_resultado.fillna("").values.tolist()   
print(dados_para_enviar)

# ===== 4. LIMPAR E REESCREVER DESTINO =====
planilha_destino = client.open_by_key(ID_DESTINO)
aba_destino = planilha_destino.worksheet(NOME_ABA_DESTINO)

# Limpa o conteúdo antigo para remover planilhas que foram apagadas
aba_destino.clear()

# Escreve a tabela atualizada
aba_destino.update(range_name="A1", values=dados_para_enviar)

print("Planilha de destino atualizada com sucesso!")

