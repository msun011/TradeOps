//+------------------------------------------------------------------+
//|                                              TradeOpsBridge.mq5  |
//|                                  Copyright 2026, TradeOps Team   |
//|                                       https://tradeops.local     |
//+------------------------------------------------------------------+
#property copyright   "TradeOps Team"
#property link        "https://tradeops.local"
#property version     "1.00"
#property description "Expert Advisor Bridge para exportar métricas, PnL e Drawdown por Magic Number para JSON"
#property strict

//+------------------------------------------------------------------+
//| Parâmetros de Entrada (Inputs)                                   |
//+------------------------------------------------------------------+
input group "=== Configurações de Execução ==="
input int       InpTimerSeconds     = 60;                      // Frequência de atualização (segundos)
input string    InpFileName                 = "tradeops_metrics.json"; // Nome do arquivo JSON padrão
input bool      InpAppendAccountToFileName  = true;                    // Usar nº da conta no nome? (ex: tradeops_7372379.json)
input bool      InpUseCommonFolder          = true;                    // Salvar na pasta Common Files (compartilhada)?
input bool      InpExportImmediately        = true;                    // Exportar imediatamente ao carregar o robô?

input group "=== Configurações de Detalhamento no JSON ==="
input bool      InpIncludeTodayStats    = true;                // Incluir métricas de hoje (intraday)?
input bool      InpIncludeOpenTrades    = true;                // Incluir detalhes das posições abertas?
input bool      InpIncludePendingOrders = true;                // Incluir detalhes das ordens pendentes?
input bool      InpIncludeRecentDeals   = false;               // Incluir últimos deals fechados?
input int       InpMaxRecentDeals       = 50;                  // Quantidade máxima de deals recentes (se habilitado)

//+------------------------------------------------------------------+
//| Estruturas de Dados Internas                                     |
//+------------------------------------------------------------------+
struct SPositionDetail
{
   ulong    ticket;
   string   symbol;
   string   type;
   double   volume;
   double   open_price;
   double   current_price;
   double   sl;
   double   tp;
   double   profit;
   double   swap;
   ulong    magic;
   string   comment;
   datetime open_time;
};

struct SPendingOrderDetail
{
   ulong    ticket;
   string   symbol;
   string   type;
   double   volume_initial;
   double   volume_current;
   double   price_open;
   double   sl;
   double   tp;
   ulong    magic;
   string   comment;
   datetime setup_time;
};

struct SDealItem
{
   ulong    ticket;
   datetime time;
   double   net_profit;
   double   volume;
   ulong    magic;
};

struct SMagicMetrics
{
   ulong    magic;
   
   // Métricas de Deals Fechados
   int      deals_total;
   int      deals_won;
   int      deals_lost;
   double   net_pnl;
   double   gross_profit;
   double   gross_loss;
   double   total_swap;
   double   total_commission;
   double   total_fee;
   double   total_volume;
   double   peak_cum_pnl;
   double   max_drawdown;
   double   current_drawdown;
   
   // Métricas de Hoje (Intraday)
   int      today_deals_total;
   int      today_deals_won;
   int      today_deals_lost;
   double   today_net_pnl;
   double   today_gross_profit;
   double   today_gross_loss;
   double   today_volume;
   
   // Posições Abertas (Floating)
   int      open_positions_count;
   double   floating_pnl;
   double   open_volume;
   
   // Ordens Pendentes
   int      pending_orders_count;
   double   pending_volume;
};

//+------------------------------------------------------------------+
//| Classe Auxiliar para Construção Limpa de JSON                    |
//+------------------------------------------------------------------+
class CJsonBuilder
{
private:
   string   m_buffer;
   bool     m_needs_comma[];
   int      m_depth;

   void PushLevel()
   {
      m_depth++;
      ArrayResize(m_needs_comma, m_depth + 1);
      m_needs_comma[m_depth] = false;
   }

   void PopLevel()
   {
      if(m_depth > 0)
      {
         m_depth--;
         ArrayResize(m_needs_comma, m_depth + 1);
      }
   }

   void CheckComma()
   {
      if(m_depth >= 0 && m_needs_comma[m_depth])
      {
         StringAdd(m_buffer, ",");
      }
      if(m_depth >= 0)
      {
         m_needs_comma[m_depth] = true;
      }
   }

public:
   CJsonBuilder()
   {
      m_buffer = "";
      m_depth = -1;
      ArrayResize(m_needs_comma, 1);
   }

   void Reset()
   {
      m_buffer = "";
      m_depth = -1;
      ArrayResize(m_needs_comma, 1);
   }

   string GetString() const
   {
      return m_buffer;
   }

   static string EscapeString(const string text)
   {
      string out = "";
      int len = StringLen(text);
      for(int i = 0; i < len; i++)
      {
         ushort ch = StringGetCharacter(text, i);
         switch(ch)
         {
            case '\"': StringAdd(out, "\\\""); break;
            case '\\': StringAdd(out, "\\\\"); break;
            case 8:    StringAdd(out, "\\b");  break; // Backspace
            case 12:   StringAdd(out, "\\f");  break; // Form feed
            case '\n': StringAdd(out, "\\n");  break;
            case '\r': StringAdd(out, "\\r");  break;
            case '\t': StringAdd(out, "\\t");  break;
            default:
               StringAdd(out, ShortToString(ch));
               break;
         }
      }
      return out;
   }

   void StartObject(const string key = "")
   {
      CheckComma();
      if(StringLen(key) > 0)
      {
         StringAdd(m_buffer, "\"" + EscapeString(key) + "\":{");
      }
      else
      {
         StringAdd(m_buffer, "{");
      }
      PushLevel();
   }

   void EndObject()
   {
      PopLevel();
      StringAdd(m_buffer, "}");
   }

   void StartArray(const string key = "")
   {
      CheckComma();
      if(StringLen(key) > 0)
      {
         StringAdd(m_buffer, "\"" + EscapeString(key) + "\":[");
      }
      else
      {
         StringAdd(m_buffer, "[");
      }
      PushLevel();
   }

   void EndArray()
   {
      PopLevel();
      StringAdd(m_buffer, "]");
   }

   void AddString(const string key, const string val)
   {
      CheckComma();
      if(StringLen(key) > 0)
         StringAdd(m_buffer, "\"" + EscapeString(key) + "\":\"" + EscapeString(val) + "\"");
      else
         StringAdd(m_buffer, "\"" + EscapeString(val) + "\"");
   }

   void AddNumber(const string key, const double val, const int digits = 2)
   {
      CheckComma();
      string strVal = DoubleToString(val, digits);
      if(StringLen(key) > 0)
         StringAdd(m_buffer, "\"" + EscapeString(key) + "\":" + strVal);
      else
         StringAdd(m_buffer, strVal);
   }

   void AddInteger(const string key, const long val)
   {
      CheckComma();
      string strVal = IntegerToString(val);
      if(StringLen(key) > 0)
         StringAdd(m_buffer, "\"" + EscapeString(key) + "\":" + strVal);
      else
         StringAdd(m_buffer, strVal);
   }

   void AddUnsigned(const string key, const ulong val)
   {
      CheckComma();
      string strVal = IntegerToString(val);
      if(StringLen(key) > 0)
         StringAdd(m_buffer, "\"" + EscapeString(key) + "\":" + strVal);
      else
         StringAdd(m_buffer, strVal);
   }

   void AddBool(const string key, const bool val)
   {
      CheckComma();
      string strVal = val ? "true" : "false";
      if(StringLen(key) > 0)
         StringAdd(m_buffer, "\"" + EscapeString(key) + "\":" + strVal);
      else
         StringAdd(m_buffer, strVal);
   }
};

//+------------------------------------------------------------------+
//| Conversão de Tipos para String                                   |
//+------------------------------------------------------------------+
string PositionTypeToString(const ENUM_POSITION_TYPE type)
{
   switch(type)
   {
      case POSITION_TYPE_BUY:  return "BUY";
      case POSITION_TYPE_SELL: return "SELL";
      default:                 return "OTHER";
   }
}

string OrderTypeToString(const ENUM_ORDER_TYPE type)
{
   switch(type)
   {
      case ORDER_TYPE_BUY:             return "BUY";
      case ORDER_TYPE_SELL:            return "SELL";
      case ORDER_TYPE_BUY_LIMIT:       return "BUY_LIMIT";
      case ORDER_TYPE_SELL_LIMIT:      return "SELL_LIMIT";
      case ORDER_TYPE_BUY_STOP:        return "BUY_STOP";
      case ORDER_TYPE_SELL_STOP:       return "SELL_STOP";
      case ORDER_TYPE_BUY_STOP_LIMIT:  return "BUY_STOP_LIMIT";
      case ORDER_TYPE_SELL_STOP_LIMIT: return "SELL_STOP_LIMIT";
      default:                         return "OTHER";
   }
}

string FormatDateTimeISO(const datetime dt)
{
   return TimeToString(dt, TIME_DATE | TIME_SECONDS);
}

//+------------------------------------------------------------------+
//| Localizar ou Criar Grupo por Magic Number                        |
//+------------------------------------------------------------------+
int FindOrAddMagicGroup(SMagicMetrics &groups[], const ulong magic)
{
   int total = ArraySize(groups);
   for(int i = 0; i < total; i++)
   {
      if(groups[i].magic == magic)
         return i;
   }
   
   ArrayResize(groups, total + 1);
   ZeroMemory(groups[total]);
   groups[total].magic = magic;
   return total;
}

//+------------------------------------------------------------------+
//| Função Principal de Coleta e Exportação                          |
//+------------------------------------------------------------------+
void ExportTradeOpsData()
{
   datetime now = TimeCurrent();
   
   // Calcular início do dia atual (00:00:00 do servidor da corretora)
   MqlDateTime sdt;
   TimeToStruct(now, sdt);
   sdt.hour = 0;
   sdt.min  = 0;
   sdt.sec  = 0;
   datetime startOfToday = StructToTime(sdt);

   double accountTodayPnl = 0.0;
   int    accountTodayDeals = 0;
   int    accountTodayWon = 0;
   int    accountTodayLost = 0;
   double accountTodayVolume = 0.0;
   
   // Seleciona todo o histórico disponível na conta até o momento atual
   if(!HistorySelect(0, now))
   {
      Print("TradeOpsBridge: Falha ao selecionar histórico de negociações. Erro = ", GetLastError());
      return;
   }

   SMagicMetrics groups[];
   ArrayResize(groups, 0);

   // 1. Processar Histórico de Deals (Trades Fechados)
   int totalDeals = HistoryDealsTotal();
   
   // Estrutura temporária para armazenar deals e calcular drawdown cronológico
   SDealItem dealItems[];
   ArrayResize(dealItems, 0);

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      
      // Consideramos eventos que encerram ou alteram posições (realização de lucro/prejuízo)
      // DEAL_ENTRY_OUT: Fechamento de posição
      // DEAL_ENTRY_INOUT: Reversão de posição
      // DEAL_ENTRY_OUT_BY: Fechamento por oposta
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT || entry == DEAL_ENTRY_OUT_BY)
      {
         ulong magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
         double swap = HistoryDealGetDouble(ticket, DEAL_SWAP);
         double comm = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         double fee = HistoryDealGetDouble(ticket, DEAL_FEE);
         double netProfit = profit + swap + comm + fee;
         double vol = HistoryDealGetDouble(ticket, DEAL_VOLUME);
         datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);

         int idx = FindOrAddMagicGroup(groups, magic);
         groups[idx].deals_total++;
         groups[idx].net_pnl += netProfit;
         groups[idx].total_swap += swap;
         groups[idx].total_commission += comm;
         groups[idx].total_fee += fee;
         groups[idx].total_volume += vol;

         if(netProfit > 0.0)
         {
            groups[idx].deals_won++;
            groups[idx].gross_profit += netProfit;
         }
         else if(netProfit < 0.0)
         {
            groups[idx].deals_lost++;
            groups[idx].gross_loss += netProfit; // Valor negativo
         }

         // Métricas Intraday (Hoje)
         if(dealTime >= startOfToday)
         {
            groups[idx].today_deals_total++;
            groups[idx].today_net_pnl += netProfit;
            groups[idx].today_volume += vol;

            if(netProfit > 0.0)
            {
               groups[idx].today_deals_won++;
               groups[idx].today_gross_profit += netProfit;
            }
            else if(netProfit < 0.0)
            {
               groups[idx].today_deals_lost++;
               groups[idx].today_gross_loss += netProfit;
            }

            accountTodayPnl += netProfit;
            accountTodayDeals++;
            if(netProfit > 0.0) accountTodayWon++;
            else if(netProfit < 0.0) accountTodayLost++;
            accountTodayVolume += vol;
         }

         // Guardar item para cálculo cronológico de Drawdown
         int dSize = ArraySize(dealItems);
         ArrayResize(dealItems, dSize + 1);
         dealItems[dSize].ticket = ticket;
         dealItems[dSize].time = dealTime;
         dealItems[dSize].net_profit = netProfit;
         dealItems[dSize].volume = vol;
         dealItems[dSize].magic = magic;
      }
   }

   // 2. Calcular Drawdown Pico-a-Vale para cada Magic Number
   int dealCount = ArraySize(dealItems);
   int groupCount = ArraySize(groups);

   for(int g = 0; g < groupCount; g++)
   {
      ulong magic = groups[g].magic;
      double cumPnl = 0.0;
      double peakPnl = 0.0;
      double maxDd = 0.0;

      for(int d = 0; d < dealCount; d++)
      {
         if(dealItems[d].magic == magic)
         {
            cumPnl += dealItems[d].net_profit;
            if(cumPnl > peakPnl)
               peakPnl = cumPnl;

            double currentDd = peakPnl - cumPnl;
            if(currentDd > maxDd)
               maxDd = currentDd;
         }
      }

      groups[g].peak_cum_pnl = peakPnl;
      groups[g].max_drawdown = maxDd;
      groups[g].current_drawdown = (peakPnl - cumPnl > 0.0) ? (peakPnl - cumPnl) : 0.0;
   }

   // 3. Coletar Posições Abertas (Floating Equity / Trades em Andamento)
   SPositionDetail openPositions[];
   int totalPositions = PositionsTotal();
   ArrayResize(openPositions, totalPositions);

   for(int i = 0; i < totalPositions; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      ulong magic = PositionGetInteger(POSITION_MAGIC);
      double profit = PositionGetDouble(POSITION_PROFIT);
      double swap = PositionGetDouble(POSITION_SWAP);
      double vol = PositionGetDouble(POSITION_VOLUME);

      int idx = FindOrAddMagicGroup(groups, magic);
      groups[idx].open_positions_count++;
      groups[idx].floating_pnl += (profit + swap);
      groups[idx].open_volume += vol;

      openPositions[i].ticket = ticket;
      openPositions[i].symbol = PositionGetString(POSITION_SYMBOL);
      openPositions[i].type = PositionTypeToString((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE));
      openPositions[i].volume = vol;
      openPositions[i].open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      openPositions[i].current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
      openPositions[i].sl = PositionGetDouble(POSITION_SL);
      openPositions[i].tp = PositionGetDouble(POSITION_TP);
      openPositions[i].profit = profit;
      openPositions[i].swap = swap;
      openPositions[i].magic = magic;
      openPositions[i].comment = PositionGetString(POSITION_COMMENT);
      openPositions[i].open_time = (datetime)PositionGetInteger(POSITION_TIME);
   }

   // 4. Coletar Ordens Pendentes (Stop Orders / Limit Orders)
   SPendingOrderDetail pendingOrders[];
   int totalOrders = OrdersTotal();
   ArrayResize(pendingOrders, totalOrders);

   for(int i = 0; i < totalOrders; i++)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;

      ulong magic = OrderGetInteger(ORDER_MAGIC);
      double volInitial = OrderGetDouble(ORDER_VOLUME_INITIAL);
      double volCurrent = OrderGetDouble(ORDER_VOLUME_CURRENT);

      int idx = FindOrAddMagicGroup(groups, magic);
      groups[idx].pending_orders_count++;
      groups[idx].pending_volume += volCurrent;

      pendingOrders[i].ticket = ticket;
      pendingOrders[i].symbol = OrderGetString(ORDER_SYMBOL);
      pendingOrders[i].type = OrderTypeToString((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE));
      pendingOrders[i].volume_initial = volInitial;
      pendingOrders[i].volume_current = volCurrent;
      pendingOrders[i].price_open = OrderGetDouble(ORDER_PRICE_OPEN);
      pendingOrders[i].sl = OrderGetDouble(ORDER_SL);
      pendingOrders[i].tp = OrderGetDouble(ORDER_TP);
      pendingOrders[i].magic = magic;
      pendingOrders[i].comment = OrderGetString(ORDER_COMMENT);
      pendingOrders[i].setup_time = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
   }

   // Atualizar contagem após possíveis novos magics adicionados nas ordens/posições
   groupCount = ArraySize(groups);

   // 5. Construção do Documento JSON
   CJsonBuilder json;
   json.StartObject();

   // Metadados Gerais
   json.AddString("timestamp", FormatDateTimeISO(now));
   json.AddInteger("server_time_epoch", (long)now);
   json.AddString("bridge_version", "1.00");

   // Informações da Conta
   json.StartObject("account");
   json.AddUnsigned("login", (ulong)AccountInfoInteger(ACCOUNT_LOGIN));
   json.AddString("currency", AccountInfoString(ACCOUNT_CURRENCY));
   json.AddString("name", AccountInfoString(ACCOUNT_NAME));
   json.AddString("broker", AccountInfoString(ACCOUNT_COMPANY));
   json.AddString("server", AccountInfoString(ACCOUNT_SERVER));
   json.AddInteger("leverage", AccountInfoInteger(ACCOUNT_LEVERAGE));
   json.AddNumber("balance", AccountInfoDouble(ACCOUNT_BALANCE), 2);
   json.AddNumber("equity", AccountInfoDouble(ACCOUNT_EQUITY), 2);
   json.AddNumber("margin", AccountInfoDouble(ACCOUNT_MARGIN), 2);
   json.AddNumber("margin_free", AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2);
   json.AddNumber("margin_level", AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2);
   json.AddNumber("floating_profit", AccountInfoDouble(ACCOUNT_PROFIT), 2);

   // Resumo de Hoje da Conta (Intraday)
   if(InpIncludeTodayStats)
   {
      json.StartObject("today_summary");
      json.AddNumber("pnl", accountTodayPnl, 2);
      json.AddInteger("deals_total", accountTodayDeals);
      json.AddInteger("deals_won", accountTodayWon);
      json.AddInteger("deals_lost", accountTodayLost);
      double acctTodayWinRate = (accountTodayDeals > 0) ? ((double)accountTodayWon / accountTodayDeals) * 100.0 : 0.0;
      json.AddNumber("win_rate_pct", acctTodayWinRate, 2);
      json.AddNumber("total_volume", accountTodayVolume, 2);
      json.EndObject();
   }
   json.EndObject();

   // Grupos por Magic Number
   json.StartObject("magic_groups");
   for(int g = 0; g < groupCount; g++)
   {
      string magicKey = IntegerToString(groups[g].magic);
      json.StartObject(magicKey);
      
      json.AddUnsigned("magic", groups[g].magic);
      string tag = (groups[g].magic == 0) ? "Manual_or_NoMagic" : ("Magic_" + magicKey);
      json.AddString("tag", tag);

      // Estatísticas de Deals Fechados
      json.StartObject("closed_stats");
      json.AddInteger("deals_total", groups[g].deals_total);
      json.AddInteger("deals_won", groups[g].deals_won);
      json.AddInteger("deals_lost", groups[g].deals_lost);
      
      double winRate = (groups[g].deals_total > 0) ? ((double)groups[g].deals_won / groups[g].deals_total) * 100.0 : 0.0;
      json.AddNumber("win_rate_pct", winRate, 2);
      
      json.AddNumber("net_pnl", groups[g].net_pnl, 2);
      json.AddNumber("gross_profit", groups[g].gross_profit, 2);
      json.AddNumber("gross_loss", groups[g].gross_loss, 2);
      
      double profitFactor = (MathAbs(groups[g].gross_loss) > 0.0001) ? (groups[g].gross_profit / MathAbs(groups[g].gross_loss)) : (groups[g].gross_profit > 0 ? 999.0 : 0.0);
      json.AddNumber("profit_factor", profitFactor, 2);

      json.AddNumber("total_swap", groups[g].total_swap, 2);
      json.AddNumber("total_commission", groups[g].total_commission, 2);
      json.AddNumber("total_fee", groups[g].total_fee, 2);
      json.AddNumber("total_volume", groups[g].total_volume, 2);
      
      json.AddNumber("peak_pnl", groups[g].peak_cum_pnl, 2);
      json.AddNumber("max_drawdown_currency", groups[g].max_drawdown, 2);
      json.AddNumber("current_drawdown_currency", groups[g].current_drawdown, 2);
      
      double ddPctPeak = (groups[g].peak_cum_pnl > 0.0) ? (groups[g].max_drawdown / groups[g].peak_cum_pnl) * 100.0 : 0.0;
      json.AddNumber("max_drawdown_pct_peak", ddPctPeak, 2);
      json.EndObject(); // closed_stats

      // Estatísticas de Hoje do Magic (Intraday)
      if(InpIncludeTodayStats)
      {
         json.StartObject("today_stats");
         json.AddInteger("deals_total", groups[g].today_deals_total);
         json.AddInteger("deals_won", groups[g].today_deals_won);
         json.AddInteger("deals_lost", groups[g].today_deals_lost);
         
         double todayWinRate = (groups[g].today_deals_total > 0) ? ((double)groups[g].today_deals_won / groups[g].today_deals_total) * 100.0 : 0.0;
         json.AddNumber("win_rate_pct", todayWinRate, 2);
         
         json.AddNumber("net_pnl", groups[g].today_net_pnl, 2);
         json.AddNumber("gross_profit", groups[g].today_gross_profit, 2);
         json.AddNumber("gross_loss", groups[g].today_gross_loss, 2);
         
         double todayProfitFactor = (MathAbs(groups[g].today_gross_loss) > 0.0001) ? (groups[g].today_gross_profit / MathAbs(groups[g].today_gross_loss)) : (groups[g].today_gross_profit > 0 ? 999.0 : 0.0);
         json.AddNumber("profit_factor", todayProfitFactor, 2);
         json.AddNumber("total_volume", groups[g].today_volume, 2);
         json.EndObject(); // today_stats
      }

      // Estatísticas de Posições em Aberto
      json.StartObject("open_stats");
      json.AddInteger("positions_count", groups[g].open_positions_count);
      json.AddNumber("floating_pnl", groups[g].floating_pnl, 2);
      json.AddNumber("open_volume", groups[g].open_volume, 2);
      json.EndObject(); // open_stats

      // Estatísticas de Ordens Pendentes
      json.StartObject("pending_stats");
      json.AddInteger("orders_count", groups[g].pending_orders_count);
      json.AddNumber("pending_volume", groups[g].pending_volume, 2);
      json.EndObject(); // pending_stats

      // Posições abertas deste Magic
      if(InpIncludeOpenTrades)
      {
         json.StartArray("positions");
         for(int p = 0; p < totalPositions; p++)
         {
            if(openPositions[p].magic == groups[g].magic)
            {
               json.StartObject();
               json.AddUnsigned("ticket", openPositions[p].ticket);
               json.AddString("symbol", openPositions[p].symbol);
               json.AddString("type", openPositions[p].type);
               json.AddNumber("volume", openPositions[p].volume, 2);
               json.AddNumber("open_price", openPositions[p].open_price, 5);
               json.AddNumber("current_price", openPositions[p].current_price, 5);
               json.AddNumber("sl", openPositions[p].sl, 5);
               json.AddNumber("tp", openPositions[p].tp, 5);
               json.AddNumber("profit", openPositions[p].profit, 2);
               json.AddNumber("swap", openPositions[p].swap, 2);
               json.AddString("comment", openPositions[p].comment);
               json.AddString("open_time", FormatDateTimeISO(openPositions[p].open_time));
               json.EndObject();
            }
         }
         json.EndArray();
      }

      // Ordens pendentes deste Magic
      if(InpIncludePendingOrders)
      {
         json.StartArray("pending_orders");
         for(int o = 0; o < totalOrders; o++)
         {
            if(pendingOrders[o].magic == groups[g].magic)
            {
               json.StartObject();
               json.AddUnsigned("ticket", pendingOrders[o].ticket);
               json.AddString("symbol", pendingOrders[o].symbol);
               json.AddString("type", pendingOrders[o].type);
               json.AddNumber("volume_initial", pendingOrders[o].volume_initial, 2);
               json.AddNumber("volume_current", pendingOrders[o].volume_current, 2);
               json.AddNumber("price_open", pendingOrders[o].price_open, 5);
               json.AddNumber("sl", pendingOrders[o].sl, 5);
               json.AddNumber("tp", pendingOrders[o].tp, 5);
               json.AddString("comment", pendingOrders[o].comment);
               json.AddString("setup_time", FormatDateTimeISO(pendingOrders[o].setup_time));
               json.EndObject();
            }
         }
         json.EndArray();
      }

      json.EndObject(); // magicKey
   }
   json.EndObject(); // magic_groups

   // Lista Completa de Posições Ativas Globais (Facilidade para ingestão pelo backend)
   if(InpIncludeOpenTrades)
   {
      json.StartArray("all_open_positions");
      for(int p = 0; p < totalPositions; p++)
      {
         json.StartObject();
         json.AddUnsigned("ticket", openPositions[p].ticket);
         json.AddUnsigned("magic", openPositions[p].magic);
         json.AddString("symbol", openPositions[p].symbol);
         json.AddString("type", openPositions[p].type);
         json.AddNumber("volume", openPositions[p].volume, 2);
         json.AddNumber("open_price", openPositions[p].open_price, 5);
         json.AddNumber("current_price", openPositions[p].current_price, 5);
         json.AddNumber("sl", openPositions[p].sl, 5);
         json.AddNumber("tp", openPositions[p].tp, 5);
         json.AddNumber("profit", openPositions[p].profit, 2);
         json.AddNumber("swap", openPositions[p].swap, 2);
         json.AddString("comment", openPositions[p].comment);
         json.AddString("open_time", FormatDateTimeISO(openPositions[p].open_time));
         json.EndObject();
      }
      json.EndArray();
   }

   // Lista Completa de Ordens Pendentes Globais
   if(InpIncludePendingOrders)
   {
      json.StartArray("all_pending_orders");
      for(int o = 0; o < totalOrders; o++)
      {
         json.StartObject();
         json.AddUnsigned("ticket", pendingOrders[o].ticket);
         json.AddUnsigned("magic", pendingOrders[o].magic);
         json.AddString("symbol", pendingOrders[o].symbol);
         json.AddString("type", pendingOrders[o].type);
         json.AddNumber("volume_initial", pendingOrders[o].volume_initial, 2);
         json.AddNumber("volume_current", pendingOrders[o].volume_current, 2);
         json.AddNumber("price_open", pendingOrders[o].price_open, 5);
         json.AddNumber("sl", pendingOrders[o].sl, 5);
         json.AddNumber("tp", pendingOrders[o].tp, 5);
         json.AddString("comment", pendingOrders[o].comment);
         json.AddString("setup_time", FormatDateTimeISO(pendingOrders[o].setup_time));
         json.EndObject();
      }
      json.EndArray();
   }

   // Lista Opcional de Deals Recentes Fechados
   if(InpIncludeRecentDeals && dealCount > 0)
   {
      json.StartArray("recent_deals");
      int startIdx = MathMax(0, dealCount - InpMaxRecentDeals);
      for(int d = dealCount - 1; d >= startIdx; d--)
      {
         json.StartObject();
         json.AddUnsigned("ticket", dealItems[d].ticket);
         json.AddUnsigned("magic", dealItems[d].magic);
         json.AddNumber("net_profit", dealItems[d].net_profit, 2);
         json.AddNumber("volume", dealItems[d].volume, 2);
         json.AddString("time", FormatDateTimeISO(dealItems[d].time));
         json.EndObject();
      }
      json.EndArray();
   }

   json.EndObject(); // Root Object

   // 6. Gravação do Arquivo no Disco (MQL5\Files ou Common\Files)
   string targetFileName = InpFileName;
   if(InpAppendAccountToFileName)
   {
      ulong login = (ulong)AccountInfoInteger(ACCOUNT_LOGIN);
      targetFileName = "tradeops_" + IntegerToString(login) + ".json";
   }

   int fileFlags = FILE_WRITE | FILE_TXT | FILE_ANSI;
   if(InpUseCommonFolder)
      fileFlags |= FILE_COMMON;

   int fileHandle = FileOpen(targetFileName, fileFlags, 0, CP_UTF8);
   if(fileHandle != INVALID_HANDLE)
   {
      FileWriteString(fileHandle, json.GetString());
      FileClose(fileHandle);
      PrintFormat("TradeOpsBridge: Dados exportados com sucesso para '%s' (%d bytes) às %s", 
                  targetFileName, StringLen(json.GetString()), TimeToString(now, TIME_SECONDS));
   }
   else
   {
      PrintFormat("TradeOpsBridge: Erro ao abrir arquivo '%s' para escrita. Código do Erro = %d", 
                  targetFileName, GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("TradeOpsBridge: Inicializando Expert Advisor...");

   if(InpTimerSeconds <= 0)
   {
      Print("TradeOpsBridge: Erro - InpTimerSeconds deve ser maior que zero.");
      return INIT_PARAMETERS_INCORRECT;
   }

   // Ativação do Timer periódico
   if(!EventSetTimer(InpTimerSeconds))
   {
      Print("TradeOpsBridge: Falha crítica ao inicializar EventSetTimer. Erro = ", GetLastError());
      return INIT_FAILED;
   }

   PrintFormat("TradeOpsBridge: EventSetTimer configurado para rodar a cada %d segundos.", InpTimerSeconds);

   // Exportação imediata no startup para inicializar o arquivo
   if(InpExportImmediately)
   {
      ExportTradeOpsData();
   }

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   PrintFormat("TradeOpsBridge: Finalizado. Timer destruído. Motivo: %d", reason);
}

//+------------------------------------------------------------------+
//| Expert timer function                                            |
//+------------------------------------------------------------------+
void OnTimer()
{
   ExportTradeOpsData();
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Vazio intencionalmente para não sobrecarregar em cada variação de preço (tick).
   // O processamento ocorre exclusivamente dentro do ciclo de 60s do OnTimer().
}
//+------------------------------------------------------------------+
