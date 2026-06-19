from flask import Flask, jsonify, render_template
import pandas as pd
import unicodedata
from pathlib import Path

app = Flask(__name__)
CSV_PATHS = [Path("transf.csv"), Path("TRANSF.csv")]


def normalize_name(name: str) -> str:
    if name is None:
        return ""
    value = str(name).strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return "".join(ch for ch in value if ch.isalnum())


def carregar_dados():
    csv_path = next((path for path in CSV_PATHS if path.exists()), None)
    if csv_path is None:
        raise FileNotFoundError("O arquivo transf.csv não foi encontrado.")

    # Tentar ler com UTF-8 primeiro (nosso arquivo de exemplo é UTF-8); fallback para latin1
    try:
        df = pd.read_csv(csv_path, sep=";", encoding="utf-8", skiprows=3)
    except Exception:
        df = pd.read_csv(csv_path, sep=";", encoding="latin1", skiprows=3)
    df.columns = [str(col).strip() for col in df.columns]

    # Normalizar e mapear Status carregamento para valores canônicos
    def canonical_status(s):
        if s is None:
            return ""
        raw = str(s)
        norm = unicodedata.normalize("NFKD", raw)
        # remover acentos e tornar minúsculo
        norm_ascii = "".join(ch for ch in norm if not unicodedata.combining(ch)).lower()
        norm_ascii = norm_ascii.strip()
        if any(k in norm_ascii for k in ("descarreg", "descarga", "descarregado")):
            return "Descarregado"
        if any(k in norm_ascii for k in ("patio", "patio")):
            return "Pátio"
        if any(k in norm_ascii for k in ("transit", "transito", "tranzit", "trantio", "trânsito")):
            return "Trânsito"
        if "doca" in norm_ascii:
            return "Doca"
        # distinguir 'separando' de 'separado' (usuário pediu ambos)
        if "separando" in norm_ascii:
            return "Separando"
        if any(k in norm_ascii for k in ("separado", "separ")):
            return "Separado"
        if "liber" in norm_ascii:
            return "Liberado"
        if "carreg" in norm_ascii:
            return "Carregando"
        return raw.strip()

    desired = {
        "dataoperacao": "Data Operação",
        "statuscarregamento": "Status carregamento",
        "tipodecarga": "Tipo de carga",
        "destino": "Destino",
        "transportadora": "Transportadora",
        "tons": "TONS",
    }

    normalized = {normalize_name(col): col for col in df.columns}
    column_map = {}
    for key, alias in desired.items():
        matched = normalized.get(key)
        if not matched:
            raise KeyError(f"Coluna obrigatória não encontrada: {alias}")
        column_map[alias] = matched

    df = df[list(column_map.values())].copy()
    df.columns = list(column_map.keys())
    df["TONS"] = pd.to_numeric(df["TONS"], errors="coerce")

    # Aplicar status canônico na coluna para facilitar o frontend e a detecção de fluxo
    if "Status carregamento" in df.columns:
        df["Status carregamento"] = df["Status carregamento"].apply(canonical_status)

    # Classificar fluxo (Inbound / Outbound / Other) baseado no status canônico
    def detect_flow(row):
        # Priorizar indicação pelo 'Tipo de carga' (entrada/saída) quando presente
        tipo = str(row.get("Tipo de carga", ""))
        tipo_norm = unicodedata.normalize("NFKD", tipo).lower()
        tipo_ascii = "".join(ch for ch in tipo_norm if not unicodedata.combining(ch))
        if any(k in tipo_ascii for k in ("entrada", "inbound", "receb")):
            return "Inbound"
        if any(k in tipo_ascii for k in ("saida", "outbound", "exped", "expedi")):
            return "Outbound"

        # Em seguida, usar o status canônico (após normalizacao aplicada antes)
        st = str(row.get("Status carregamento", ""))
        st_norm = unicodedata.normalize("NFKD", st).lower()
        st_ascii = "".join(ch for ch in st_norm if not unicodedata.combining(ch))
        if any(k in st_ascii for k in ("descarreg", "patio")):
            return "Inbound"
        if any(k in st_ascii for k in ("liber", "separ", "carreg")):
            return "Outbound"

        return "Other"

    df["flow"] = df.apply(detect_flow, axis=1)

    return df


def to_frontend_records(df):
    return df.rename(columns={
        "Data Operação": "data_operacao",
        "Status carregamento": "status_carregamento",
        "Tipo de carga": "tipo_de_carga",
        "Destino": "destino",
        "Transportadora": "transportadora",
        "TONS": "tons",
    })


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    try:
        df = carregar_dados()
        return jsonify(to_frontend_records(df).fillna("").to_dict(orient="records"))
    except Exception as err:
        app.logger.exception("Erro ao carregar dados")
        return jsonify([]), 500


if __name__ == "__main__":
    app.run(debug=True)
