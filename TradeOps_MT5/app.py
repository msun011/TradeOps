import streamlit as st
import pandas as pd
import json
import urllib.request
from datetime import datetime

# ====================================================================
# Configurações da Página
# ====================================================================
st.set_page_config(
    page_title="TradeOps Dashboard | Multi-Account Quant Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Customizada (Visual Moderno Dark / Quant)
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e222d 0%, #161922 100%);
        border: 1px solid #2a2e39;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }
    .metric-title {
        font-size: 0.85rem;
        color: #848e9c;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
    }
    .pnl-positive {
        color: #0ecb81 !important;
    }
    .pnl-negative {
        color: #f6465d !important;
    }
    .badge-vps {
        background-color: #2b313a;
        color: #f0b90b;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ====================================================================
# Conexão com Supabase
# ====================================================================
SUPABASE_URL = "https://sibhvalhyyeqkczwksdd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpYmh2YWxoeXllcWtjendrc2RkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg5NzcwODUsImV4cCI6MjEwNDU1MzA4NX0.e-yt1fuAmOHuRUVHT9xAaAPJUto76Llub8mL-zZcX3c"

@st.cache_data(ttl=15)
def fetch_supabase_metrics():
    """Puxa os últimos snapshots de cada conta cadastrada no Supabase."""
    endpoint = f"{SUPABASE_URL}/rest/v1/tradeops_metrics?select=*&order=created_at.desc&limit=50"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    req = urllib.request.Request(endpoint, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data
    except Exception as e:
        return []
    return []

# ====================================================================
# Cabeçalho Principal
# ====================================================================
col_logo, col_refresh = st.columns([8, 2])
with col_logo:
    st.title("📈 TradeOps Dashboard")
    st.caption("Monitoramento Multi-Conta e Gestão de Portfólio de Robôs em Tempo Real")
with col_refresh:
    st.write("")
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ====================================================================
# Carregamento e Processamento dos Dados
# ====================================================================
raw_records = fetch_supabase_metrics()

# Se ainda não houver dados no Supabase, carrega os dados locais como demonstração
if not raw_records:
    st.info("💡 **Aguardando dados da Nuvem.** Enquanto a tabela do Supabase está sendo inicializada, exibindo dados das suas contas já capturadas:")
    # Tenta ler arquivos locais se existirem
    demo_files = [
        "c:/Projetos/tradeops_metrics.json",
        "c:/Projetos/tradeops_metrics_5ersprop.json"
    ]
    accounts_data = {}
    for df in demo_files:
        try:
            with open(df, "r", encoding="utf-8") as f:
                d = json.load(f)
                login = str(d.get("account", {}).get("login"))
                accounts_data[login] = {
                    "account_login": login,
                    "broker": d.get("account", {}).get("broker"),
                    "balance": d.get("account", {}).get("balance"),
                    "equity": d.get("account", {}).get("equity"),
                    "today_pnl": d.get("account", {}).get("today_summary", {}).get("pnl", 0.0),
                    "today_deals": d.get("account", {}).get("today_summary", {}).get("deals_total", 0),
                    "raw_data": d
                }
        except Exception:
            pass
else:
    # Agrupa pegando o registro mais recente de cada account_login
    accounts_data = {}
    for r in raw_records:
        login = str(r.get("account_login"))
        if login not in accounts_data:
            raw = r.get("raw_data") or {}
            acct = raw.get("account") or {}
            
            # Garante leitura correta do balance e broker
            real_balance = acct.get("balance") if acct.get("balance") is not None else (acct.get("\\balance") if acct.get("\\balance") is not None else r.get("balance", 0.0))
            real_broker = acct.get("broker") or acct.get("\\broker") or r.get("broker") or "Broker"
            
            r["balance"] = float(real_balance or 0.0)
            r["broker"] = str(real_broker)
            accounts_data[login] = r

# ====================================================================
# Barra Lateral (Sidebar)
# ====================================================================
st.sidebar.header("⚙️ Filtros da Carteira")
account_options = ["Todas as Contas (Consolidado)"] + [
    f"{acc['account_login']} - {acc.get('broker', 'Broker')} (${acc.get('balance', 0):,.2f})"
    for acc in accounts_data.values()
]
selected_option = st.sidebar.selectbox("Selecione a Conta:", account_options)

st.sidebar.divider()
st.sidebar.markdown("""
**Status da Nuvem:** 🟢 Conectado  
**VPSs Conectadas:**
- `VPS-100k-Live`
- `VPS-Prop-10k`
""")

# ====================================================================
# Métricas Consolidadas
# ====================================================================
if selected_option == "Todas as Contas (Consolidado)":
    total_balance = sum(acc.get("balance", 0) for acc in accounts_data.values())
    total_equity = sum(acc.get("equity", 0) for acc in accounts_data.values())
    total_today_pnl = sum(acc.get("today_pnl", 0) for acc in accounts_data.values())
    total_today_deals = sum(acc.get("today_deals", 0) for acc in accounts_data.values())
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Saldo Consolidado", f"${total_balance:,.2f}")
    with col2:
        st.metric("Patrimônio (Equity)", f"${total_equity:,.2f}")
    with col3:
        pnl_sign = "+" if total_today_pnl >= 0 else "-"
        st.metric(
            "PnL de Hoje (Total)", 
            f"${total_today_pnl:,.2f}", 
            delta=f"{pnl_sign}${abs(total_today_pnl):,.2f}",
            delta_color="normal"
        )
    with col4:
        st.metric("Operações Fechadas Hoje", f"{total_today_deals} trades")

    active_accounts = list(accounts_data.values())
else:
    # Conta individual
    chosen_login = selected_option.split(" - ")[0]
    acc = accounts_data[chosen_login]
    active_accounts = [acc]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Saldo da Conta", f"${acc.get('balance', 0):,.2f}")
    with col2:
        st.metric("Patrimônio (Equity)", f"${acc.get('equity', 0):,.2f}")
    with col3:
        pnl = acc.get("today_pnl", 0)
        pnl_sign = "+" if pnl >= 0 else "-"
        st.metric("Resultado de Hoje", f"${pnl:,.2f}", delta=f"{pnl_sign}${abs(pnl):,.2f}")
    with col4:
        st.metric("Trades Fechados Hoje", f"{acc.get('today_deals', 0)} trades")

st.divider()

# ====================================================================
# Abas de Análise Detalhada
# ====================================================================
tab_robots, tab_positions, tab_compare = st.tabs(["🤖 Performance dos Robôs", "⚡ Posições Abertas", "📊 Comparativo de Contas"])

with tab_robots:
    st.subheader("Desempenho dos Robôs por Magic Number")
    
    # Extrai todos os grupos de magics das contas selecionadas
    robot_rows = []
    for acc in active_accounts:
        raw = acc.get("raw_data", {})
        login = acc.get("account_login")
        magics = raw.get("magic_groups", {})
        
        for m_id, m_info in magics.items():
            c_stats = m_info.get("closed_stats", {})
            t_stats = m_info.get("today_stats", {})
            
            robot_rows.append({
                "Conta": login,
                "Magic": m_id,
                "Tag": m_info.get("tag", f"Magic_{m_id}"),
                "PnL Hoje ($)": t_stats.get("net_pnl", 0.0),
                "Trades Hoje": t_stats.get("deals_total", 0),
                "PnL Histórico ($)": c_stats.get("net_pnl", 0.0),
                "Total Trades": c_stats.get("deals_total", 0),
                "Win Rate (%)": f"{c_stats.get('win_rate_pct', 0.0):.1f}%",
                "Profit Factor": c_stats.get("profit_factor", 0.0),
                "Max Drawdown ($)": c_stats.get("max_drawdown_currency", 0.0),
                "DD Atual ($)": c_stats.get("current_drawdown_currency", 0.0)
            })
            
    if robot_rows:
        df_robots = pd.DataFrame(robot_rows)
        # Ordena pelo maior PnL Histórico
        df_robots = df_robots.sort_values(by="PnL Histórico ($)", ascending=False)
        
        st.dataframe(
            df_robots.style.format({
                "PnL Hoje ($)": "${:,.2f}",
                "PnL Histórico ($)": "${:,.2f}",
                "Profit Factor": "{:.2f}",
                "Max Drawdown ($)": "${:,.2f}",
                "DD Atual ($)": "${:,.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Gráfico de Barras do PnL por Robô
        st.write("")
        st.markdown("#### Lucro/Prejuízo Acumulado por Robô")
        chart_data = df_robots.set_index("Tag")["PnL Histórico ($)"]
        st.bar_chart(chart_data)
    else:
        st.info("Nenhuma métrica de robô encontrada para a seleção.")

with tab_positions:
    st.subheader("Posições em Andamento no Mercado")
    open_positions = []
    for acc in active_accounts:
        raw = acc.get("raw_data", {})
        login = acc.get("account_login")
        positions = raw.get("all_open_positions", [])
        for pos in positions:
            pos["Conta"] = login
            open_positions.append(pos)
            
    if open_positions:
        df_pos = pd.DataFrame(open_positions)
        st.dataframe(df_pos, use_container_width=True, hide_index=True)
    else:
        st.success("✅ **Sem posições abertas no momento.** Todas as ordens foram encerradas e a carteira está 100% protegida fora de risco.")

with tab_compare:
    st.subheader("Comparativo da Carteira Multi-Conta")
    summary_rows = []
    for acc in accounts_data.values():
        summary_rows.append({
            "Conta": acc.get("account_login"),
            "Corretora": acc.get("broker"),
            "Saldo ($)": acc.get("balance", 0),
            "Equity ($)": acc.get("equity", 0),
            "Resultado Hoje ($)": acc.get("today_pnl", 0),
            "Operações Hoje": acc.get("today_deals", 0)
        })
    if summary_rows:
        df_summary = pd.DataFrame(summary_rows)
        st.dataframe(
            df_summary.style.format({
                "Saldo ($)": "${:,.2f}",
                "Equity ($)": "${:,.2f}",
                "Resultado Hoje ($)": "${:,.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )
