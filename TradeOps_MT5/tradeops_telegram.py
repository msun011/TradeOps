#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================================
TradeOps Telegram Monitor
====================================================================
Script leve para VPS que lê os arquivos JSON gerados pelo TradeOpsBridge
no MetaTrader 5 e envia notificações automáticas e resumos no Telegram.

Requisitos:
- Apenas Python 3 (sem necessidade de instalar bibliotecas externas).
====================================================================
"""

import os
import sys
import glob
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime

CONFIG_FILE = "config.json"

def load_config():
    """Carrega as configurações do arquivo config.json."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(base_dir, CONFIG_FILE)
    
    if not os.path.exists(cfg_path):
        print(f"[ERRO] Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
        sys.exit(1)
        
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)

def send_telegram_message(token, chat_id, message_html):
    """Envia uma mensagem formatada em HTML para o Telegram usando urllib nativo."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        print(f"[ERRO Telegram] Falha ao enviar mensagem: {e}")
        return False

def find_json_files(custom_folder=None):
    """Localiza todos os arquivos JSON do TradeOps na máquina."""
    found = []
    
    # 1. Pasta personalizada se especificada
    if custom_folder and os.path.exists(custom_folder):
        found.extend(glob.glob(os.path.join(custom_folder, "tradeops*.json")))
        
    # 2. Pasta atual do script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    found.extend(glob.glob(os.path.join(base_dir, "tradeops*.json")))
    
    # 3. Pasta Common Files do MetaTrader 5 no Windows (%APPDATA%\MetaQuotes\Terminal\Common\Files)
    appdata = os.environ.get("APPDATA")
    if appdata:
        common_mt5_files = os.path.join(appdata, "MetaQuotes", "Terminal", "Common", "Files")
        if os.path.exists(common_mt5_files):
            found.extend(glob.glob(os.path.join(common_mt5_files, "tradeops*.json")))
            
    # Remove duplicados mantendo caminhos absolutos normalizados
    unique = list({os.path.normpath(f) for f in found if os.path.isfile(f)})
    return unique

def format_account_report(data, vps_id, is_alert=False, alert_title=None):
    """Formata o JSON em uma mensagem limpa e elegante para o Telegram."""
    account = data.get("account", {})
    login = account.get("login", "N/A")
    broker = account.get("broker", "Corretora")
    name = account.get("name", "Trader")
    currency = account.get("currency", "USD")
    balance = account.get("balance", 0.0)
    equity = account.get("equity", 0.0)
    
    today = account.get("today_summary", {})
    today_pnl = today.get("pnl", 0.0)
    today_deals = today.get("deals_total", 0)
    today_won = today.get("deals_won", 0)
    today_lost = today.get("deals_lost", 0)
    today_winrate = today.get("win_rate_pct", 0.0)
    
    # Ícones conforme o PnL do dia
    if today_pnl > 0:
        pnl_badge = f"🟢 <b>+${today_pnl:,.2f}</b>"
    elif today_pnl < 0:
        pnl_badge = f"🔴 <b>-${abs(today_pnl):,.2f}</b>"
    else:
        pnl_badge = f"⚪ <b>$0.00</b>"
        
    header = f"🚨 <b>{alert_title}</b>" if is_alert and alert_title else "📊 <b>TradeOps Status Report</b>"
    
    msg = [
        f"{header}",
        f"🖥️ <b>VPS:</b> <code>{vps_id}</code>",
        f"🏦 <b>Conta:</b> <code>{login}</code> ({broker})",
        f"👤 <b>Titular:</b> {name}",
        f"💰 <b>Saldo:</b> ${balance:,.2f} {currency} | <b>Equity:</b> ${equity:,.2f}",
        "",
        f"📅 <b>Resultado de Hoje:</b> {pnl_badge}",
        f"🎯 <b>Trades Hoje:</b> {today_deals} (✅ {today_won} | ❌ {today_lost} | Win: {today_winrate:.1f}%)",
    ]
    
    # Detalhamento dos Robôs que operaram hoje
    magic_groups = data.get("magic_groups", {})
    traded_today = []
    top_lifetime = []
    
    for magic_key, info in magic_groups.items():
        t_stats = info.get("today_stats", {})
        c_stats = info.get("closed_stats", {})
        
        # Filtra os que operaram hoje
        if t_stats.get("deals_total", 0) > 0:
            traded_today.append((magic_key, info.get("tag", magic_key), t_stats))
            
        # Para ranking histórico
        top_lifetime.append((magic_key, info.get("tag", magic_key), c_stats.get("net_pnl", 0.0)))
        
    if traded_today:
        msg.append("\n🤖 <b>Atividade dos Robôs Hoje:</b>")
        for m_key, tag, t_info in traded_today:
            m_pnl = t_info.get("net_pnl", 0.0)
            m_deals = t_info.get("deals_total", 0)
            m_sign = "🟢 +" if m_pnl > 0 else ("🔴 -" if m_pnl < 0 else "⚪ ")
            pnl_str = f"{m_sign}${abs(m_pnl):,.2f}"
            msg.append(f"  • <b>{tag}:</b> {pnl_str} ({m_deals} trade{'s' if m_deals > 1 else ''})")
    else:
        msg.append("\n🤖 <i>Nenhum robô fechou operações no dia de hoje.</i>")
        
    # Posições Abertas no momento
    open_positions = data.get("all_open_positions", [])
    if open_positions:
        msg.append(f"\n⚡ <b>Posições Abertas ({len(open_positions)}):</b>")
        for pos in open_positions[:5]: # Mostra até 5 para não estourar mensagem
            sym = pos.get("symbol", "")
            typ = pos.get("type", "")
            vol = pos.get("volume", 0.0)
            profit = pos.get("profit", 0.0)
            p_sign = "+" if profit >= 0 else "-"
            msg.append(f"  • {sym} {typ} {vol:.2f} | PnL: {p_sign}${abs(profit):,.2f}")
        if len(open_positions) > 5:
            msg.append(f"  <i>... e mais {len(open_positions) - 5} posições abertas.</i>")
            
    # Timestamp do arquivo
    file_time = data.get("timestamp", "")
    msg.append(f"\n🕒 <i>Atualizado às {file_time} (Servidor)</i>")
    
    return "\n".join(msg)

def main():
    print("=" * 60)
    print("           TRADEOPS TELEGRAM MONITOR - INICIADO           ")
    print("=" * 60)
    
    config = load_config()
    token = config.get("telegram_bot_token", "").strip()
    chat_id = config.get("telegram_chat_id", "").strip()
    vps_id = config.get("vps_identifier", "VPS-Local")
    interval = config.get("check_interval_seconds", 30)
    custom_folder = config.get("custom_json_folder", "")
    
    # Validação rápida de preenchimento
    if token == "COLE_SEU_BOT_TOKEN_AQUI" or not token:
        print("[ERRO] Você ainda não configurou o 'telegram_bot_token' no config.json!")
        print("Abra o arquivo config.json e cole o token gerado no @BotFather.")
        sys.exit(1)
        
    if chat_id == "COLE_SEU_CHAT_ID_AQUI" or not chat_id:
        print("[ERRO] Você ainda não configurou o 'telegram_chat_id' no config.json!")
        print("Abra o arquivo config.json e cole o Chat ID gerado no @userinfobot.")
        sys.exit(1)
        
    # Modo de teste único (--test)
    is_test_mode = "--test" in sys.argv
    
    print(f"[*] VPS Identifier: {vps_id}")
    print(f"[*] Intervalo de checagem: {interval}s")
    print("[*] Buscando arquivos JSON do TradeOps...")
    
    # Dicionário de estado para detectar alterações: {login: {"deals": X, "pnl": Y, "positions": Z}}
    last_known_state = {}
    
    files = find_json_files(custom_folder)
    print(f"[*] Encontrados {len(files)} arquivo(s) de métricas:")
    for f in files:
        print(f"    - {f}")
        
    if not files:
        print("[AVISO] Nenhum arquivo 'tradeops*.json' encontrado ainda.")
        print("Certifique-se de que o Expert Advisor 'TradeOpsBridge' está rodando no MT5.")
        if is_test_mode:
            test_msg = f"🚀 <b>Teste de Conexão TradeOps</b>\n\nConexão com o Telegram funcionando perfeitamente na <code>{vps_id}</code>!\n\n<i>Aguardando o MT5 gerar os arquivos JSON...</i>"
            send_telegram_message(token, chat_id, test_msg)
            print("[SUCESSO] Mensagem de teste enviada para o Telegram!")
            return

    # Se for modo de teste, envia o status atual de cada conta e finaliza
    if is_test_mode:
        print("[*] Enviando relatório de teste de todas as contas encontradas...")
        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                msg = format_account_report(data, vps_id, is_alert=False)
                send_telegram_message(token, chat_id, msg)
                print(f"[OK] Relatório da conta {data.get('account', {}).get('login')} enviado com sucesso!")
            except Exception as e:
                print(f"[ERRO ao ler {fpath}]: {e}")
        return

    # Mensagem de Boas-Vindas no Startup
    startup_msg = f"🚀 <b>TradeOps Monitor Ativo!</b>\n\nMonitoramento iniciado na <code>{vps_id}</code>.\nContas detectadas: <b>{len(files)}</b>.\nVocê receberá atualizações quando houver novos trades!"
    send_telegram_message(token, chat_id, startup_msg)
    
    # Loop de monitoramento contínuo
    print("\n[*] Monitoramento em execução. Pressione Ctrl+C para encerrar.\n")
    while True:
        try:
            current_files = find_json_files(custom_folder)
            
            for fpath in current_files:
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue
                    
                account = data.get("account", {})
                login = str(account.get("login", "0"))
                today = account.get("today_summary", {})
                
                curr_deals = today.get("deals_total", 0)
                curr_pnl = today.get("pnl", 0.0)
                curr_open = len(data.get("all_open_positions", []))
                
                # Primeira vez lendo essa conta
                if login not in last_known_state:
                    last_known_state[login] = {
                        "deals": curr_deals,
                        "pnl": curr_pnl,
                        "open_positions": curr_open
                    }
                    # Envia o estado inicial da conta
                    msg = format_account_report(data, vps_id, is_alert=False)
                    send_telegram_message(token, chat_id, msg)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Relatório inicial enviado para a conta {login}")
                else:
                    prev = last_known_state[login]
                    # Detecta novo trade fechado
                    if curr_deals != prev["deals"] or curr_pnl != prev["pnl"]:
                        diff_deals = curr_deals - prev["deals"]
                        diff_pnl = curr_pnl - prev["pnl"]
                        
                        title = f"Novo Fechamento ({'+' if diff_pnl >= 0 else '-'}${abs(diff_pnl):,.2f})"
                        msg = format_account_report(data, vps_id, is_alert=True, alert_title=title)
                        send_telegram_message(token, chat_id, msg)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Notificação de novo trade enviada! Conta: {login} (PnL: {diff_pnl:+,.2f})")
                        
                        last_known_state[login]["deals"] = curr_deals
                        last_known_state[login]["pnl"] = curr_pnl
                        last_known_state[login]["open_positions"] = curr_open
                    elif curr_open != prev["open_positions"]:
                        # Apenas atualiza a contagem de posições abertas
                        last_known_state[login]["open_positions"] = curr_open
                        
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n[!] Monitoramento encerrado pelo usuário.")
            break
        except Exception as e:
            print(f"[ERRO no loop]: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    main()
