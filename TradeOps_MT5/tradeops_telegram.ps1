# ====================================================================
# TradeOps Telegram Monitor & Supabase Cloud Sync (PowerShell Nativo)
# ====================================================================
param (
    [switch]$Test
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFile = Join-Path $scriptDir "config.json"

if (-not (Test-Path $configFile)) {
    Write-Host "[ERRO] config.json nao encontrado em: $configFile" -ForegroundColor Red
    exit 1
}

$config = Get-Content -Raw -Path $configFile -Encoding UTF8 | ConvertFrom-Json
$token = $config.telegram_bot_token.Trim()
$chatId = $config.telegram_chat_id.Trim()
$vpsId = $config.vps_identifier
$interval = if ($config.check_interval_seconds) { [int]$config.check_interval_seconds } else { 60 }
$customFolder = $config.custom_json_folder

function Send-TelegramMessage {
    param (
        [string]$MessageHtml
    )
    $url = "https://api.telegram.org/bot$token/sendMessage"
    $out = & curl.exe -s -X POST $url -d "chat_id=$chatId" --data-urlencode "text=$MessageHtml" -d "parse_mode=HTML" -d "disable_web_page_preview=true"
    return ($out -match '"ok":true')
}

function Send-SupabaseSnapshot {
    param (
        $data
    )
    if (-not $config.sync_to_supabase -or -not $config.supabase_url -or -not $config.supabase_key) {
        return $false
    }
    
    $sbUrl = "$($config.supabase_url.TrimEnd('/'))/rest/v1/tradeops_metrics"
    $sbKey = $config.supabase_key.Trim()

    $account = $data.account
    $today = $account.today_summary
    $brokerVal = if ($null -ne $account.broker) { [string]$account.broker } elseif ($null -ne $account.'\broker') { [string]$account.'\broker' } else { "Broker" }
    $balanceVal = if ($null -ne $account.balance) { [double]$account.balance } elseif ($null -ne $account.'\balance') { [double]$account.'\balance' } else { 0.0 }

    $payloadObj = @{
        vps_id        = $vpsId
        account_login = [string]$account.login
        broker        = $brokerVal
        currency      = [string]$account.currency
        balance       = $balanceVal
        equity        = [double]$account.equity
        today_pnl     = if ($today) { [double]$today.pnl } else { 0.0 }
        today_deals   = if ($today) { [int]$today.deals_total } else { 0 }
        raw_data      = $data
    }
    $payloadJson = $payloadObj | ConvertTo-Json -Depth 10

    $headers = @{
        "apikey"        = $sbKey
        "Authorization" = "Bearer $sbKey"
        "Content-Type"  = "application/json"
        "Prefer"        = "return=minimal"
    }

    try {
        Invoke-RestMethod -Uri $sbUrl -Method Post -Headers $headers -Body $payloadJson | Out-Null
        return $true
    } catch {
        Write-Host "[ERRO Supabase] $($_.Exception.Message)" -ForegroundColor DarkRed
        return $false
    }
}

function Find-JsonFiles {
    $list = @()
    if ($customFolder -and (Test-Path $customFolder)) {
        $list += Get-ChildItem -Path $customFolder -Filter "tradeops*.json" -File | ForEach-Object { $_.FullName }
    }
    
    # Pasta atual do script
    if (Test-Path $scriptDir) {
        $list += Get-ChildItem -Path $scriptDir -Filter "tradeops*.json" -File | ForEach-Object { $_.FullName }
    }
    
    # Pasta pai (ex: c:\Projetos)
    $parentDir = Split-Path -Parent $scriptDir
    if ($parentDir -and (Test-Path $parentDir)) {
        $list += Get-ChildItem -Path $parentDir -Filter "tradeops*.json" -File | ForEach-Object { $_.FullName }
    }
    
    # Common Files MT5
    if ($env:APPDATA) {
        $mt5Common = Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files"
        if (Test-Path $mt5Common) {
            $list += Get-ChildItem -Path $mt5Common -Filter "tradeops*.json" -File | ForEach-Object { $_.FullName }
        }
    }
    return $list | Select-Object -Unique
}

function Format-Report {
    param (
        $data,
        [string]$AlertTitle = ""
    )
    $account = $data.account
    $login = $account.login
    $broker = $account.broker
    $name = $account.name
    $currency = $account.currency
    $balance = "{0:N2}" -f $account.balance
    $equity = "{0:N2}" -f $account.equity

    $today = $account.today_summary
    $todayPnl = if ($today) { [double]$today.pnl } else { 0.0 }
    $todayDeals = if ($today) { [int]$today.deals_total } else { 0 }
    $todayWon = if ($today) { [int]$today.deals_won } else { 0 }
    $todayLost = if ($today) { [int]$today.deals_lost } else { 0 }
    $todayWin = if ($today) { "{0:N1}" -f [double]$today.win_rate_pct } else { "0.0" }

    if ($todayPnl -gt 0) {
        $pnlBadge = "<b>+`$$("{0:N2}" -f $todayPnl)</b>"
    } elseif ($todayPnl -lt 0) {
        $pnlBadge = "<b>-`$$("{0:N2}" -f [math]::Abs($todayPnl))</b>"
    } else {
        $pnlBadge = "<b>`$0.00</b>"
    }

    $header = if ($AlertTitle -ne "") { "<b>[ALERTA] $AlertTitle</b>" } else { "<b>TradeOps Status Report</b>" }

    $lines = @(
        "$header",
        "<b>VPS:</b> <code>$vpsId</code>",
        "<b>Conta:</b> <code>$login</code> ($broker)",
        "<b>Titular:</b> $name",
        "<b>Saldo:</b> `$$balance $currency | <b>Equity:</b> `$$equity",
        "",
        "<b>Resultado de Hoje:</b> $pnlBadge",
        "<b>Trades Hoje:</b> $todayDeals (Win: $todayWon | Loss: $todayLost | $todayWin%)"
    )

    $tradedToday = @()
    if ($data.magic_groups) {
        $data.magic_groups.psobject.properties | ForEach-Object {
            $mVal = $_.Value
            $tStats = $mVal.today_stats
            if ($tStats -and $tStats.deals_total -gt 0) {
                $mPnl = [double]$tStats.net_pnl
                $pnlStr = if ($mPnl -ge 0) { "+`$" + ("{0:N2}" -f $mPnl) } else { "-`$" + ("{0:N2}" -f [math]::Abs($mPnl)) }
                $sign = if ($mPnl -gt 0) { "[+] " } elseif ($mPnl -lt 0) { "[-] " } else { "    " }
                $tag = $mVal.tag
                $tDeals = $tStats.deals_total
                $tradedToday += "  $sign<b>${tag}:</b> $pnlStr ($tDeals trade" + $(if ($tDeals -gt 1) { "s" } else { "" }) + ")"
            }
        }
    }

    if ($tradedToday.Count -gt 0) {
        $lines += ""
        $lines += "<b>Atividade dos Robos Hoje:</b>"
        $lines += $tradedToday
    } else {
        $lines += ""
        $lines += "<i>Nenhum robo fechou operacoes hoje.</i>"
    }

    $timeStr = $data.timestamp
    $lines += ""
    $lines += "<i>Atualizado as $timeStr (Servidor)</i>"

    return ($lines -join "`n")
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "     TRADEOPS TELEGRAM MONITOR & CLOUD SYNC             " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "[*] VPS: $vpsId"
Write-Host "[*] Intervalo de checagem: ${interval}s"
Write-Host "[*] Supabase Sync: $(if ($config.sync_to_supabase) { 'ATIVADO' } else { 'DESATIVADO' })"

$files = Find-JsonFiles
Write-Host "[*] Arquivos de metricas encontrados: $($files.Count)"
foreach ($f in $files) { Write-Host "    - $f" }

if ($Test) {
    Write-Host "`n[*] Enviando relatorio de teste para o Telegram e Nuvem..." -ForegroundColor Yellow
    if ($files.Count -eq 0) {
        $testMsg = "<b>[TradeOps] Teste Concluido!</b>`n`nMonitoramento online na <code>$vpsId</code>.`n<i>Aguardando o MT5 gerar os arquivos JSON...</i>"
        $ok = Send-TelegramMessage -MessageHtml $testMsg
        if ($ok) { Write-Host "[SUCESSO] Mensagem de teste enviada ao Telegram!" -ForegroundColor Green }
        else { Write-Host "[ERRO] Falha ao enviar mensagem ao Telegram." -ForegroundColor Red }
    } else {
        foreach ($f in $files) {
            $raw = Get-Content -Raw -Path $f -Encoding UTF8 | ConvertFrom-Json
            $msg = Format-Report -data $raw
            $ok = Send-TelegramMessage -MessageHtml $msg
            if ($ok) { Write-Host "[SUCESSO] Relatorio da conta $($raw.account.login) enviado ao Telegram!" -ForegroundColor Green }
            else { Write-Host "[ERRO] Falha ao enviar relatorio ao Telegram." -ForegroundColor Red }

            if ($config.sync_to_supabase) {
                Send-SupabaseSnapshot -data $raw | Out-Null
                Write-Host "[SUCESSO] Snapshot da conta $($raw.account.login) sincronizado com o Supabase!" -ForegroundColor Green
            }
        }
    }
    exit 0
}

# Modo Loop
$lastState = @{}
Write-Host "`n[*] Monitoramento em execucao. Pressione Ctrl+C para parar.`n" -ForegroundColor Green

while ($true) {
    $currentFiles = Find-JsonFiles
    foreach ($f in $currentFiles) {
        try {
            $raw = Get-Content -Raw -Path $f -Encoding UTF8 | ConvertFrom-Json
            $login = [string]$raw.account.login
            $deals = if ($raw.account.today_summary) { [int]$raw.account.today_summary.deals_total } else { 0 }
            $pnl = if ($raw.account.today_summary) { [double]$raw.account.today_summary.pnl } else { 0.0 }

            if (-not $lastState.ContainsKey($login)) {
                $lastState[$login] = @{ deals = $deals; pnl = $pnl }
                $msg = Format-Report -data $raw
                Send-TelegramMessage -MessageHtml $msg | Out-Null
                Send-SupabaseSnapshot -data $raw | Out-Null
                Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] Relatorio inicial sincronizado para conta $login" -ForegroundColor Cyan
            } else {
                $prev = $lastState[$login]
                if ($deals -ne $prev.deals -or $pnl -ne $prev.pnl) {
                    $diffPnl = $pnl - $prev.pnl
                    $pnlFmt = if ($diffPnl -ge 0) { "+`$" + ("{0:N2}" -f $diffPnl) } else { "-`$" + ("{0:N2}" -f [math]::Abs($diffPnl)) }
                    $title = "Novo Fechamento ($pnlFmt)"
                    $msg = Format-Report -data $raw -AlertTitle $title
                    Send-TelegramMessage -MessageHtml $msg | Out-Null
                    Send-SupabaseSnapshot -data $raw | Out-Null
                    Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] Alerta de trade enviado e sincronizado com a Nuvem! Conta $login ($pnlFmt)" -ForegroundColor Yellow
                    $lastState[$login] = @{ deals = $deals; pnl = $pnl }
                }
            }
        } catch {
            Write-Host "[AVISO] Falha ao processar $f : $_" -ForegroundColor DarkGray
        }
    }
    Start-Sleep -Seconds $interval
}
