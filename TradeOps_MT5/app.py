import streamlit as st
import pandas as pd
import json
import urllib.request
from datetime import datetime, date

# ====================================================================
# Configurações da Página
# ====================================================================
st.set_page_config(
    page_title="TradeOps Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .metric-card {
        background: linear-gradient(135deg, #1e222d 0%, #161922 100%);
        border: 1px solid #2a2e39;
        border-radius: 14px;
        padding: 22px 20px;
        margin-bottom: 12px;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #848e9c;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
        font-weight: 500;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #eaecef;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #848e9c;
        margin-top: 4px;
    }
    .positive { color: #0ecb81 !important; }
    .negative { color: #f6465d !important; }
    .neutral  { color: #f0b90b !important; }

    .vps-badge {
        display: inline-block;
        background: #2b313a;
        color: #f0b90b;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 6px;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #eaecef;
        border-left: 3px solid #f0b90b;
        padding-left: 10px;
        margin: 20px 0 12px 0;
    }
</style>
""", unsafe_allow_html=True)

# ====================================================================
# Constantes Supabase
# ====================================================================
SUPABASE_URL = "https://sibhvalhyyeqkczwksdd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNpYmh2YWxoeXllcWtjendrc2RkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg5NzcwODUsImV4cCI6MjEwNDU1MzA4NX0.e-yt1fuAmOHuRUVHT9xAaAPJUto76Llub8mL-zZcX3c"

# ====================================================================
# Helpers de Dados
# ====================================================================

def safe_get(d, *keys, default=0.0):
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return default
    return d if d is not None else default

def fmt_usd(val, sign=False):
    if val is None: return "$0.00"
    prefix = "+" if sign and val > 0 else ("-" if val < 0 else "")
    return f"{prefix}${abs(val):,.2f}"

def fmt_pct(val):
    if val is None: return "0.00%"
    return f"{val:.2f}%"

@st.cache_data(ttl=30)
def fetch_all_records(limit=300):
    endpoint = (
        f"{SUPABASE_URL}/rest/v1/tradeops_metrics"
        f"?select=*&order=created_at.desc&limit={limit}"
    )
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    req = urllib.request.Request(endpoint, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

def build_accounts(records):
    accounts = {}
    for r in records:
        login = str(r.get("account_login", ""))
        if login and login not in accounts:
            raw = r.get("raw_data") or {}
            acct = raw.get("account") or {}
            balance = safe_get(acct, "balance", default=None) or r.get("balance", 0.0)
            broker  = safe_get(acct, "broker",  default=None) or r.get("broker", "")
            equity  = safe_get(acct, "equity",  default=None) or r.get("equity", 0.0)
            r["balance"] = float(balance or 0.0)
            r["equity"]  = float(equity  or 0.0)
            r["broker"]  = str(broker or "")
            accounts[login] = r
    return accounts

def extract_magic_rows(records, filter_login=None):
    rows = []
    seen = set()
    for r in records:
        login = str(r.get("account_login", ""))
        if filter_login and login != filter_login:
            continue
        raw = r.get("raw_data") or {}
        magics = raw.get("magic_groups") or {}
        for m_id, m_info in magics.items():
            key = (login, m_id)
            if key in seen:
                continue
            seen.add(key)
            c = m_info.get("closed_stats") or {}
            t = m_info.get("today_stats")  or {}
            o = m_info.get("open_stats")   or {}
            p = m_info.get("pending_stats") or {}
            rows.append({
                "Conta":               login,
                "Magic":               m_id,
                "Tag":                 m_info.get("tag", f"Magic_{m_id}"),
                "Historico PnL ($)":   round(float(c.get("net_pnl", 0.0)), 2),
                "Hoje PnL ($)":        round(float(t.get("net_pnl", 0.0)), 2),
                "Total Trades":        int(c.get("deals_total", 0)),
                "Hoje Trades":         int(t.get("deals_total", 0)),
                "Win Rate (%)":        round(float(c.get("win_rate_pct", 0.0)), 1),
                "Win Rate Hoje (%)":   round(float(t.get("win_rate_pct", 0.0)), 1),
                "Profit Factor":       round(float(c.get("profit_factor", 0.0)), 2),
                "Profit Factor Hoje":  round(float(t.get("profit_factor", 0.0)), 2),
                "Max DD ($)":          round(float(c.get("max_drawdown_currency", 0.0)), 2),
                "DD Atual ($)":        round(float(c.get("current_drawdown_currency", 0.0)), 2),
                "DD Pico (%)":         round(float(c.get("max_drawdown_pct_peak", 0.0)), 2),
                "Volume Total":        round(float(c.get("total_volume", 0.0)), 2),
                "Swap ($)":            round(float(c.get("total_swap", 0.0)), 2),
                "Comissao ($)":        round(float(c.get("total_commission", 0.0)), 2),
                "Gross Profit ($)":    round(float(c.get("gross_profit", 0.0)), 2),
                "Gross Loss ($)":      round(float(c.get("gross_loss", 0.0)), 2),
                "Peak PnL ($)":        round(float(c.get("peak_pnl", 0.0)), 2),
                "Posicoes Abertas":    int(o.get("positions_count", 0)),
                "Floating PnL ($)":    round(float(o.get("floating_pnl", 0.0)), 2),
                "Ordens Pendentes":    int(p.get("orders_count", 0)),
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def extract_equity_history(records, login):
    rows = []
    for r in reversed(records):
        if str(r.get("account_login", "")) != login:
            continue
        created_at = r.get("created_at", "")
        try:
            ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            continue
        raw = r.get("raw_data") or {}
        acct = raw.get("account") or {}
        balance = safe_get(acct, "balance", default=0.0) or r.get("balance", 0.0)
        equity  = safe_get(acct, "equity",  default=0.0) or r.get("equity", 0.0)
        rows.append({
            "Horario": ts,
            "Saldo":   float(balance or 0.0),
            "Equity":  float(equity or 0.0),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("Horario")
    return df

# ====================================================================
# Carregar dados
# ====================================================================
all_records   = fetch_all_records(limit=300)
accounts_data = build_accounts(all_records)

# ====================================================================
# Sidebar
# ====================================================================
with st.sidebar:
    st.title("📈 TradeOps")
    st.caption("Multi-Account Quant Monitor")
    st.divider()

    st.header("⚙️ Filtros")
    account_labels = {
        login: f"{login} · {acc.get('broker','')[:20]}"
        for login, acc in accounts_data.items()
    }
    all_label = "🌐 Todas as Contas (Consolidado)"
    options = [all_label] + list(account_labels.values())
    selected_label = st.selectbox("Conta:", options)

    if selected_label == all_label:
        selected_login = None
    else:
        selected_login = [k for k, v in account_labels.items() if v == selected_label][0]

    st.divider()

    vps_ids = list({
        (r.get("raw_data") or {}).get("vps_id", r.get("vps_id", "?")) or r.get("vps_id", "?")
        for r in all_records
    })
    st.markdown("**VPSs Online:**")
    for v in vps_ids:
        st.markdown(f'<span class="vps-badge">{v}</span>', unsafe_allow_html=True)

    st.divider()
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Ultimo refresh: {datetime.now().strftime('%H:%M:%S')}")

# ====================================================================
# Título dinâmico
# ====================================================================
if selected_login:
    acc  = accounts_data[selected_login]
    raw  = acc.get("raw_data") or {}
    acct = raw.get("account") or {}
    broker = acc.get("broker", "")
    st.title(f"📊 Conta {selected_login}")
    st.caption(f"{broker}  ·  Alavancagem 1:{int(safe_get(acct,'leverage',default=0))}x  ·  {safe_get(acct,'currency',default='USD')}")
else:
    st.title("🌐 Portfolio Consolidado")
    st.caption(f"{len(accounts_data)} conta(s) ativas monitoradas via TradeOpsBridge")

# ====================================================================
# KPIs principais
# ====================================================================
def render_kpis(accs):
    total_balance = sum(float(a.get("balance", 0.0)) for a in accs.values())
    total_equity  = sum(float(a.get("equity",  0.0)) for a in accs.values())
    total_pnl_day = sum(float(a.get("today_pnl", 0.0)) for a in accs.values())
    total_deals   = sum(int(a.get("today_deals", 0)) for a in accs.values())
    float_pnl_tot = sum(
        float(safe_get((a.get("raw_data") or {}).get("account") or {}, "floating_profit", default=0.0))
        for a in accs.values()
    )
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 Saldo Total", fmt_usd(total_balance))
    col2.metric("📐 Equity Total", fmt_usd(total_equity))
    col3.metric("📅 Resultado Hoje", fmt_usd(total_pnl_day),
                delta=fmt_usd(total_pnl_day, sign=True),
                delta_color="normal" if total_pnl_day >= 0 else "inverse")
    col4.metric("⚡ Floating PnL", fmt_usd(float_pnl_tot),
                delta_color="normal" if float_pnl_tot >= 0 else "inverse")
    col5.metric("🎯 Trades Hoje", f"{total_deals} ops")

if selected_login:
    render_kpis({selected_login: accounts_data[selected_login]})
else:
    render_kpis(accounts_data)

st.divider()

# ====================================================================
# Abas
# ====================================================================
tab_robots, tab_accounts, tab_positions, tab_history, tab_raw = st.tabs([
    "🤖 Robos",
    "🏦 Por Conta",
    "⚡ Posicoes & Ordens",
    "📈 Curva de Equity",
    "🔍 Snapshots"
])

# ────────────────────────────────────────────────────────────────────
# ABA 1: Robôs
# ────────────────────────────────────────────────────────────────────
with tab_robots:
    st.markdown('<div class="section-title">Performance dos Robos por Magic Number</div>', unsafe_allow_html=True)

    df_robots = extract_magic_rows(all_records, filter_login=selected_login)

    if df_robots.empty:
        st.info("Nenhum dado de robo disponivel ainda. Aguardando sincronia da VPS.")
    else:
        criticos = df_robots[
            (df_robots["DD Atual ($)"] > 0) &
            (df_robots["Max DD ($)"] > 0) &
            (df_robots["DD Atual ($)"] >= df_robots["Max DD ($)"] * 0.75)
        ]
        if not criticos.empty:
            st.error(f"⚠️ **{len(criticos)} robo(s) em Drawdown Critico** (>75% do DD Maximo Historico):")
            for _, row in criticos.iterrows():
                st.warning(f"🔴 **{row['Tag']}** (Conta {row['Conta']}): DD Atual = {fmt_usd(row['DD Atual ($)'])} de Max {fmt_usd(row['Max DD ($)'])}")

        st.divider()

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            sort_by = st.selectbox("Ordenar por:", [
                "Historico PnL ($)", "Hoje PnL ($)", "Profit Factor",
                "Win Rate (%)", "Max DD ($)", "Total Trades"
            ])
        with col_f2:
            only_active_today = st.checkbox("Apenas robos com atividade hoje", value=False)
        with col_f3:
            only_positive = st.checkbox("Apenas robos positivos (PnL > 0)", value=False)

        df_view = df_robots.copy()
        if only_active_today:
            df_view = df_view[df_view["Hoje Trades"] > 0]
        if only_positive:
            df_view = df_view[df_view["Historico PnL ($)"] > 0]
        df_view = df_view.sort_values(by=sort_by, ascending=False)

        display_cols = [
            "Conta", "Tag", "Historico PnL ($)", "Hoje PnL ($)",
            "Total Trades", "Hoje Trades", "Win Rate (%)",
            "Profit Factor", "Max DD ($)", "DD Atual ($)", "DD Pico (%)",
            "Posicoes Abertas", "Floating PnL ($)"
        ]
        st.dataframe(
            df_view[display_cols].style.format({
                "Historico PnL ($)": "${:,.2f}",
                "Hoje PnL ($)":      "${:,.2f}",
                "Max DD ($)":        "${:,.2f}",
                "DD Atual ($)":      "${:,.2f}",
                "DD Pico (%)":       "{:.2f}%",
                "Win Rate (%)":      "{:.1f}%",
                "Profit Factor":     "{:.2f}",
                "Floating PnL ($)":  "${:,.2f}",
            }).background_gradient(
                subset=["Historico PnL ($)"],
                cmap="RdYlGn",
                vmin=-5000, vmax=15000
            ),
            use_container_width=True,
            hide_index=True,
            height=400
        )

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown('<div class="section-title">PnL Historico por Robo</div>', unsafe_allow_html=True)
            chart_pnl = df_view.set_index("Tag")["Historico PnL ($)"].sort_values(ascending=False)
            st.bar_chart(chart_pnl)
        with col_g2:
            st.markdown('<div class="section-title">Drawdown Maximo por Robo</div>', unsafe_allow_html=True)
            chart_dd = df_view.set_index("Tag")["Max DD ($)"].sort_values(ascending=False)
            st.bar_chart(chart_dd)

        st.divider()
        st.markdown('<div class="section-title">Analise de Custos (Swap & Comissoes)</div>', unsafe_allow_html=True)
        cost_cols = ["Conta", "Tag", "Volume Total", "Swap ($)", "Comissao ($)", "Gross Profit ($)", "Gross Loss ($)", "Historico PnL ($)"]
        st.dataframe(
            df_view[cost_cols].style.format({
                "Swap ($)":         "${:,.2f}",
                "Comissao ($)":     "${:,.2f}",
                "Gross Profit ($)": "${:,.2f}",
                "Gross Loss ($)":   "${:,.2f}",
                "Historico PnL ($)":"${:,.2f}",
                "Volume Total":     "{:.2f}",
            }),
            use_container_width=True,
            hide_index=True
        )

# ────────────────────────────────────────────────────────────────────
# ABA 2: Por Conta
# ────────────────────────────────────────────────────────────────────
with tab_accounts:
    st.markdown('<div class="section-title">Resumo Detalhado por Conta</div>', unsafe_allow_html=True)

    accs_to_show = {selected_login: accounts_data[selected_login]} if selected_login else accounts_data

    for login, acc in accs_to_show.items():
        raw  = acc.get("raw_data") or {}
        acct = raw.get("account") or {}
        today = acct.get("today_summary") or {}

        balance  = acc.get("balance", 0.0)
        equity   = float(safe_get(acct, "equity",   default=0.0))
        broker   = acc.get("broker", "")
        leverage = int(safe_get(acct, "leverage", default=0))
        margin   = float(safe_get(acct, "margin",      default=0.0))
        margin_f = float(safe_get(acct, "margin_free", default=0.0))
        margin_l = float(safe_get(acct, "margin_level",default=0.0))
        float_p  = float(safe_get(acct, "floating_profit", default=0.0))

        t_pnl   = float(today.get("pnl", acc.get("today_pnl", 0.0)))
        t_deals = int(today.get("deals_total", acc.get("today_deals", 0)))
        t_won   = int(today.get("deals_won",  0))
        t_lost  = int(today.get("deals_lost", 0))
        t_wr    = float(today.get("win_rate_pct", 0.0))
        t_vol   = float(today.get("total_volume",  0.0))

        magics   = raw.get("magic_groups") or {}
        hist_pnl = sum(float((m.get("closed_stats") or {}).get("net_pnl", 0.0)) for m in magics.values())
        total_trades = sum(int((m.get("closed_stats") or {}).get("deals_total", 0)) for m in magics.values())

        with st.expander(f"🏦 Conta {login} — {broker}", expanded=True):
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Saldo",   fmt_usd(balance))
            c2.metric("Equity",  fmt_usd(equity))
            c3.metric("Floating PnL", fmt_usd(float_p),
                      delta=fmt_usd(float_p, sign=True),
                      delta_color="normal" if float_p >= 0 else "inverse")
            c4.metric("PnL Hoje", fmt_usd(t_pnl),
                      delta=fmt_usd(t_pnl, sign=True),
                      delta_color="normal" if t_pnl >= 0 else "inverse")
            c5.metric("Trades Hoje", f"{t_deals}  (W:{t_won} L:{t_lost})")
            c6.metric("Win Rate Hoje", fmt_pct(t_wr))

            st.divider()

            c7, c8, c9, c10, c11, c12 = st.columns(6)
            c7.metric("PnL Historico Total",  fmt_usd(hist_pnl))
            c8.metric("Total de Trades",       f"{total_trades:,}")
            c9.metric("Alavancagem",            f"1:{leverage}")
            c10.metric("Margem Usada",          fmt_usd(margin))
            c11.metric("Margem Livre",          fmt_usd(margin_f))
            c12.metric("Nivel de Margem",       fmt_pct(margin_l))

            df_conta = extract_magic_rows(all_records, filter_login=login)
            if not df_conta.empty:
                st.markdown("**Ranking de Robos desta Conta:**")
                mini_cols = ["Tag", "Historico PnL ($)", "Hoje PnL ($)", "Win Rate (%)", "Profit Factor", "Max DD ($)", "DD Atual ($)"]
                st.dataframe(
                    df_conta[mini_cols].sort_values("Historico PnL ($)", ascending=False).style.format({
                        "Historico PnL ($)": "${:,.2f}",
                        "Hoje PnL ($)":      "${:,.2f}",
                        "Max DD ($)":        "${:,.2f}",
                        "DD Atual ($)":      "${:,.2f}",
                        "Win Rate (%)":      "{:.1f}%",
                        "Profit Factor":     "{:.2f}",
                    }),
                    use_container_width=True, hide_index=True, height=280
                )

# ────────────────────────────────────────────────────────────────────
# ABA 3: Posições & Ordens
# ────────────────────────────────────────────────────────────────────
with tab_positions:
    st.markdown('<div class="section-title">Posicoes Abertas em Tempo Real</div>', unsafe_allow_html=True)

    all_open    = []
    all_pending = []
    seen_accs   = set()
    for r in all_records:
        login = str(r.get("account_login", ""))
        if selected_login and login != selected_login:
            continue
        if login in seen_accs:
            continue
        seen_accs.add(login)
        raw = r.get("raw_data") or {}
        for pos in raw.get("all_open_positions") or []:
            pos["Conta"] = login
            all_open.append(pos)
        for ord_ in raw.get("all_pending_orders") or []:
            ord_["Conta"] = login
            all_pending.append(ord_)

    if all_open:
        df_open = pd.DataFrame(all_open)
        st.success(f"📌 {len(all_open)} posicao(oes) abertas agora:")
        st.dataframe(df_open, use_container_width=True, hide_index=True)
    else:
        st.success("✅ **Nenhuma posicao aberta.** Portfolio zerado e fora de risco no momento.")

    st.markdown('<div class="section-title">Ordens Pendentes (Stop/Limit aguardando disparo)</div>', unsafe_allow_html=True)
    if all_pending:
        df_pend = pd.DataFrame(all_pending)
        st.info(f"🕐 {len(all_pending)} ordem(ns) pendente(s) no book:")
        st.dataframe(df_pend, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma ordem pendente no momento.")

# ────────────────────────────────────────────────────────────────────
# ABA 4: Curva de Equity
# ────────────────────────────────────────────────────────────────────
with tab_history:
    st.markdown('<div class="section-title">Curva de Equity por Conta</div>', unsafe_allow_html=True)

    logins_to_plot = [selected_login] if selected_login else list(accounts_data.keys())
    for login in logins_to_plot:
        df_eq = extract_equity_history(all_records, login)
        if df_eq.empty:
            st.caption(f"Conta {login}: historico insuficiente (aguardando mais snapshots).")
            continue
        broker_name = accounts_data.get(login, {}).get("broker", "")
        st.subheader(f"Conta {login} · {broker_name}")
        st.line_chart(df_eq[["Equity"]])
        if len(df_eq) > 1:
            delta_eq = df_eq["Equity"].iloc[-1] - df_eq["Equity"].iloc[0]
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Equity Atual",          fmt_usd(df_eq["Equity"].iloc[-1]))
            col_b.metric("Equity Minima (periodo)", fmt_usd(df_eq["Equity"].min()))
            col_c.metric("Variacao no Periodo",    fmt_usd(delta_eq, sign=True),
                         delta_color="normal" if delta_eq >= 0 else "inverse")

# ────────────────────────────────────────────────────────────────────
# ABA 5: Snapshots
# ────────────────────────────────────────────────────────────────────
with tab_raw:
    st.markdown('<div class="section-title">Historico de Snapshots (Supabase)</div>', unsafe_allow_html=True)
    st.caption("Cada linha e um snapshot gravado quando houve alteracao de trades ou na primeira carga do monitor.")

    snap_rows = []
    for r in all_records:
        login = str(r.get("account_login", ""))
        if selected_login and login != selected_login:
            continue
        raw  = r.get("raw_data") or {}
        acct = raw.get("account") or {}
        snap_rows.append({
            "ID":           r.get("id"),
            "Conta":        login,
            "VPS":          str(raw.get("vps_id") or r.get("vps_id", "")),
            "Timestamp":    r.get("created_at", "")[:19].replace("T", " "),
            "Saldo ($)":    float(safe_get(acct, "balance", default=0.0) or r.get("balance", 0.0)),
            "Equity ($)":   float(safe_get(acct, "equity",  default=0.0) or r.get("equity",  0.0)),
            "PnL Hoje ($)": float(r.get("today_pnl",   0.0)),
            "Trades Hoje":  int(r.get("today_deals", 0)),
        })

    if snap_rows:
        df_snaps = pd.DataFrame(snap_rows)
        st.dataframe(
            df_snaps.style.format({
                "Saldo ($)":    "${:,.2f}",
                "Equity ($)":   "${:,.2f}",
                "PnL Hoje ($)": "${:,.2f}",
            }),
            use_container_width=True, hide_index=True
        )
        st.caption(f"Total de snapshots na nuvem: {len(snap_rows)}")
    else:
        st.info("Nenhum snapshot encontrado para os filtros selecionados.")
