import streamlit as st
import xmltodict
import pandas as pd
from datetime import date, datetime
import os
import requests
from fpdf import FPDF
import zipfile
import tempfile

# ========== FUNÇÕES AUXILIARES ==========
def extrair_dados_xml(xml_content):
    """Extrai dados fiscais de XML (NFe/CTe)"""
    try:
        data = xmltodict.parse(xml_content)
        
        if "nfeProc" in data:
            nfe = data["nfeProc"]["NFe"]["infNFe"]
            emitente = nfe["emit"]["xNome"]
            destinatario = nfe["dest"]["xNome"]
            chave = nfe["@Id"].replace("NFe", "")
            produtos = nfe["det"]
            
            if isinstance(produtos, dict):
                produtos = [produtos]
            
            dados = []
            for produto in produtos:
                ncm = produto["prod"]["NCM"]
                cfop = produto["prod"]["CFOP"]
                cest = produto["prod"].get("CEST", "Não informado")
                
                icms = produto["imposto"]["ICMS"].get("ICMS00", {}) or \
                       produto["imposto"]["ICMS"].get("ICMS20", {})
                
                aliquota_icms = icms.get("pICMS", "0%")
                st_icms = "Sim" if "ICMSST" in produto["imposto"]["ICMS"] else "Não"
                
                dados.append({
                    "Item": produto["@nItem"],
                    "Descrição": produto["prod"]["xProd"],
                    "NCM": ncm,
                    "CEST": cest,
                    "CFOP": cfop,
                    "ICMS": aliquota_icms,
                    "ST": st_icms,
                    "Monofásico?": "Sim" if cfop in ["5933", "6933"] else "Não"
                })
            
            return {
                "Tipo": "NFe",
                "Emitente": emitente,
                "Destinatário": destinatario,
                "Chave": chave,
                "Produtos": pd.DataFrame(dados)
            }
        
        elif "cteProc" in data:
            cte = data["cteProc"]["CTe"]["infCte"]
            return {
                "Tipo": "CTe",
                "Emitente": cte["emit"]["xNome"],
                "Destinatário": cte["dest"]["xNome"],
                "Chave": cte["@Id"].replace("CTe", ""),
                "Produtos": None
            }
        
        else:
            st.error("XML não reconhecido")
            return None
    
    except Exception as e:
        st.error(f"Erro ao processar XML: {str(e)}")
        return None

def verificar_ncm_cest(ncm, cest):
    """Consulta webservice oficial (exemplo fictício)"""
    try:
        url = f"https://api.sefaz.gov.br/ncm-cest/{ncm}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            valid_cests = [item["cest"] for item in data["resultados"]]
            return str(cest).replace(".", "") in [c.replace(".", "") for c in valid_cests]
        return False
    except:
        return False  # Fallback para caso a API falhe
    
def atualizar_tabela_cest():
    url = "URL_OFICIAL_DA_TABELA"
    df = pd.read_excel(url)
    df.to_csv("tabela_cest_local.csv", index=False)
   

def gerar_relatorio_pdf(dados):
    """Gera relatório em PDF"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    # ... (código anterior do PDF)
    return pdf.output(dest="S").encode("latin1")

# ========== INTERFACE PRINCIPAL ==========
st.set_page_config(
    page_title="Analisador Fiscal",
    page_icon="🧾",
    layout="wide"
)

st.title("🔍 Analisador Fiscal (XML/NFe/CTe)")

# Upload do arquivo
uploaded_file = st.file_uploader("📤 Carregue o XML (NFe/CTe):", type=["xml"])

if uploaded_file:
    xml_content = uploaded_file.read().decode("utf-8")
    dados = extrair_dados_xml(xml_content)  # Agora a função já está definida
    
    if dados:
        st.success(f"✅ {dados['Tipo']} processada com sucesso!")
        
        # Exibição dos dados
        col1, col2 = st.columns(2)
        col1.metric("Emitente", dados["Emitente"])
        col2.metric("Destinatário", dados["Destinatário"])
        
        if dados["Tipo"] == "NFe":
            df = dados["Produtos"]
            df["Validação NCM"] = df.apply(
                lambda x: "✅ Válido" if verificar_ncm_cest(x["NCM"], x["CEST"]) else "⚠️ Verificar", 
                axis=1
            )
            st.dataframe(df, use_container_width=True)
            
            # Exportação
            if st.button("📤 Exportar para Excel"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    df.to_excel(tmp.name, index=False)
                    with open(tmp.name, "rb") as f:
                        st.download_button(
                            "⬇️ Baixar Excel",
                            f,
                            file_name="analise_fiscal.xlsx"
                        )
                        print(f"Tabela atualizada em {date.today()}")