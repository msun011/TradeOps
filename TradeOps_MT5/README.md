# TradeOpsBridge - Expert Advisor MQL5 para MetaTrader 5

Bridge de alta performance para MetaTrader 5 projetado para coletar periodicamente métricas financeiras, posições ativas e ordens pendentes, agrupadas por **Magic Number**, exportando-as diretamente para um arquivo JSON estruturado.

---

## 🎯 Funcionalidades Principais

1. **Execução Periódica Assíncrona via `EventSetTimer`**:
   - Roda a cada **60 segundos** (configurável via `InpTimerSeconds`) sem sobrecarregar o fluxo de ticks da plataforma (`OnTick` permanece livre).
   - Executa uma primeira exportação imediatamente no `OnInit()` para que os dados fiquem disponíveis de imediato.

2. **Agrupamento Completo por Magic Number**:
   - **Histórico Fechado (Closed PnL)**: Identifica e agrupa deals com saída (`DEAL_ENTRY_OUT`, `DEAL_ENTRY_INOUT`, `DEAL_ENTRY_OUT_BY`), calculando o lucro líquido real (`Profit + Swap + Commission + Fee`), volume total, taxa de acerto (*win rate*) e fator de lucro (*profit factor*).
   - **Trades Manuais ou sem Magic**: Mapeados automaticamente com `magic: 0` sob a tag `"Manual_or_NoMagic"`.
   - **Drawdown Pico-a-Vale (Peak-to-Valley)**: Como no MT5 o saldo é global e compartilhado entre todos os robôs, o Drawdown por Magic Number é calculado cronologicamente sobre a curva de PnL acumulado daquela estratégia individual.

3. **Floating Equity (Posições Abertas)**:
   - Extrai em tempo real todos os trades em andamento (`PositionsTotal()`).
   - Calcula o `floating_pnl` acumulado e volume por Magic Number.
   - Lista detalhadamente cada posição aberta (ticket, ativo, tipo BUY/SELL, preço de abertura, cotação atual, SL, TP, lucro atual e swap).

4. **Ordens Pendentes (Pending Orders)**:
   - Mapeia ordens de entrada que aguardam disparo (`OrdersTotal()`): `BUY_LIMIT`, `SELL_LIMIT`, `BUY_STOP`, `SELL_STOP`, `BUY_STOP_LIMIT`, `SELL_STOP_LIMIT`.
   - Agrupa a contagem e volume pendente por Magic Number e detalha preços e volumes.

5. **JSON Nativo e Seguro (Zero Dependências)**:
   - Possui serializador JSON nativo embutido no próprio `.mq5`, sem exigir nenhuma biblioteca externa (`.mqh`), DLL ou arquivo adicional.
   - Trata caracteres de escape de strings e garante formato numérico com formatação adequada de casas decimais.

---

## 📁 Onde o Arquivo JSON é Salvo?

Por padrão do MetaTrader 5 (sandbox de segurança):
- **Modo Padrão (`InpUseCommonFolder = false`)**:
  - Salvo na pasta do terminal:  
    `C:\Users\<SeuUsuario>\AppData\Roaming\MetaQuotes\Terminal\<ID_TERMINAL>\MQL5\Files\tradeops_metrics.json`
  - No MT5, você pode abrir essa pasta diretamente clicando em:  
    **Arquivo (File)** -> **Abrir Pasta de Dados (Open Data Folder)** -> subpasta **MQL5** -> **Files**.

- **Modo Compartilhado (`InpUseCommonFolder = true`)**:
  - Salvo na pasta pública de dados comuns a todos os terminais MT5 da máquina:  
    `C:\Users\<SeuUsuario>\AppData\Roaming\MetaQuotes\Terminal\Common\Files\tradeops_metrics.json`
  - Ideal caso você tenha um serviço externo em Python/Node.js/C# que precise ler métricas sem saber o ID interno do terminal.

---

## ⚙️ Parâmetros de Entrada (Inputs)

| Parâmetro | Padrão | Descrição |
| :--- | :--- | :--- |
| `InpTimerSeconds` | `60` | Intervalo em segundos do `EventSetTimer` para a atualização do JSON. |
| `InpFileName` | `"tradeops_metrics.json"` | Nome do arquivo gerado. |
| `InpUseCommonFolder` | `false` | Se `true`, grava na pasta `Common\Files`; se `false`, grava em `MQL5\Files`. |
| `InpExportImmediately` | `true` | Se `true`, exporta os dados no primeiro segundo em que o robô é acoplado. |
| `InpIncludeTodayStats` | `true` | Inclui métricas intraday de hoje (`today_summary` na conta e `today_stats` nos magics). |
| `InpIncludeOpenTrades` | `true` | Inclui detalhes de posições abertas (`positions` e `all_open_positions`). |
| `InpIncludePendingOrders`| `true` | Inclui detalhes de ordens pendentes (`pending_orders` e `all_pending_orders`). |
| `InpIncludeRecentDeals` | `false` | Inclui array dos últimos deals fechados da conta. |
| `InpMaxRecentDeals` | `50` | Quantidade máxima de deals recentes (caso o item acima esteja ativo). |

---

## 📄 Estrutura do JSON Gerado

```json
{
  "timestamp": "2026.09.09 14:38:00",
  "server_time_epoch": 1788964680,
  "bridge_version": "1.00",
  "account": {
    "login": 12345678,
    "currency": "BRL",
    "name": "Nome do Trader",
    "broker": "MetaQuotes Software Corp.",
    "server": "Demo-Server",
    "leverage": 100,
    "balance": 15000.00,
    "equity": 15150.80,
    "margin": 450.00,
    "margin_free": 14700.80,
    "margin_level": 3366.84,
    "floating_profit": 150.80,
    "today_summary": {
      "pnl": 340.50,
      "deals_total": 6,
      "deals_won": 4,
      "deals_lost": 2,
      "win_rate_pct": 66.67,
      "total_volume": 0.60
    }
  },
  "magic_groups": {
    "1001": {
      "magic": 1001,
      "tag": "Magic_1001",
      "closed_stats": {
        "deals_total": 45,
        "deals_won": 28,
        "deals_lost": 17,
        "win_rate_pct": 62.22,
        "net_pnl": 1250.40,
        "gross_profit": 2300.00,
        "gross_loss": -1049.60,
        "profit_factor": 2.19,
        "total_swap": -15.20,
        "total_commission": -34.40,
        "total_fee": 0.00,
        "total_volume": 4.50,
        "peak_pnl": 1570.90,
        "max_drawdown_currency": 320.50,
        "current_drawdown_currency": 0.00,
        "max_drawdown_pct_peak": 20.40
      },
      "today_stats": {
        "deals_total": 3,
        "deals_won": 2,
        "deals_lost": 1,
        "win_rate_pct": 66.67,
        "net_pnl": 180.20,
        "gross_profit": 260.00,
        "gross_loss": -79.80,
        "profit_factor": 3.26,
        "total_volume": 0.30
      },
      "open_stats": {
        "positions_count": 1,
        "floating_pnl": 150.80,
        "open_volume": 0.10
      },
      "pending_stats": {
        "orders_count": 1,
        "pending_volume": 0.10
      },
      "positions": [
        {
          "ticket": 98765432,
          "symbol": "WINV26",
          "type": "BUY",
          "volume": 0.10,
          "open_price": 132000.00000,
          "current_price": 132400.00000,
          "sl": 131500.00000,
          "tp": 133000.00000,
          "profit": 150.80,
          "swap": 0.00,
          "comment": "TradeOps Buy Order",
          "open_time": "2026.09.09 14:10:00"
        }
      ],
      "pending_orders": [
        {
          "ticket": 98765499,
          "symbol": "WINV26",
          "type": "BUY_STOP",
          "volume_initial": 0.10,
          "volume_current": 0.10,
          "price_open": 133200.00000,
          "sl": 132800.00000,
          "tp": 134000.00000,
          "comment": "Breakout Stop",
          "setup_time": "2026.09.09 14:15:00"
        }
      ]
    }
  },
  "all_open_positions": [ ... ],
  "all_pending_orders": [ ... ]
}
```

---

## 🚀 Como Instalar e Rodar no MetaTrader 5

1. Abra o MetaTrader 5.
2. Vá no menu **Arquivo (File)** -> **Abrir Pasta de Dados (Open Data Folder)**.
3. Navegue até a pasta `MQL5\Experts\`.
4. Copie o arquivo `TradeOpsBridge.mq5` para dentro de `MQL5\Experts\`.
5. Pressione `F4` no teclado para abrir o **MetaEditor** (ou abra pelo ícone do MT5).
6. Na barra lateral esquerda do MetaEditor (Navegador), clique duas vezes em `TradeOpsBridge.mq5`.
7. Pressione `F7` (ou clique no botão **Compilar / Compile** no topo).
   - Você verá a mensagem: `0 errors, 0 warnings`.
8. Volte ao MetaTrader 5:
   - No painel **Navegador** (Ctrl+N), em **Consultor Expert (Experts)**, clique com o botão direito e selecione **Atualizar (Refresh)**.
   - Arraste o **TradeOpsBridge** para qualquer gráfico aberto (pode ser qualquer ativo ou tempo gráfico, pois ele opera em nível de conta).
   - Certifique-se de que a opção **"Permitir AlgoTrading" (Allow Algo Trading)** esteja ativada caso queira visualizá-lo com ícone azul ativo (embora o robô apenas leia dados e não envie ordens de execução).
9. Na aba **Experts** do Terminal (Ctrl+T), você verá os logs com a confirmação:
   ```text
   TradeOpsBridge: Inicializando Expert Advisor...
   TradeOpsBridge: EventSetTimer configurado para rodar a cada 60 segundos.
   TradeOpsBridge: Dados exportados com sucesso para 'tradeops_7372379.json' (3412 bytes) às 14:38:00
   ```

---

## 📱 Notificações no Telegram (Passo a Passo)

O projeto inclui o `tradeops_telegram.py`, um script leve sem dependências externas que monitora os arquivos gerados na VPS e envia relatórios e alertas para o seu celular.

### 1. Configuração do `config.json`
Abra o arquivo [config.json](file:///c:/Projetos/TradeOps_MT5/config.json) e preencha:
```json
{
  "telegram_bot_token": "SEU_BOT_TOKEN_DO_BOTFATHER",
  "telegram_chat_id": "SEU_CHAT_ID_DO_USERINFOBOT",
  "vps_identifier": "VPS-Principal",
  "check_interval_seconds": 30,
  "notify_on_new_trade": true
}
```

### 2. Testar o envio
Basta dar um duplo clique em [test_telegram.bat](file:///c:/Projetos/TradeOps_MT5/test_telegram.bat). Ele enviará imediatamente o resumo de todas as contas encontradas na máquina para o seu Telegram.

### 3. Deixar rodando 24/7 na VPS
Dê um duplo clique em [iniciar_monitor.bat](file:///c:/Projetos/TradeOps_MT5/iniciar_monitor.bat). Ele ficará em segundo plano na VPS notificando sempre que um novo trade for fechado por qualquer um dos robôs!

