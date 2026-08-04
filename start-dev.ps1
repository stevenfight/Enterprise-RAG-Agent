# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    一键启动企业财务年报分析系统（前端 + 后端）

.DESCRIPTION
    同时启动 FastAPI 后端 (端口 8000) 和 React 前端开发服务器 (端口 5173)
    关闭任一窗口即可停止对应服务

.EXAMPLE
    .\start-dev.ps1
    默认启动前后端

.EXAMPLE
    .\start-dev.ps1 -BackendOnly
    仅启动后端

.EXAMPLE
    .\start-dev.ps1 -FrontendOnly
    仅启动前端
#>

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  企业财务年报分析智能 RAG Agent - 开发环境启动" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$backendJob = $null
$frontendJob = $null

# 启动后端
if (-not $FrontendOnly) {
    Write-Host "[后端] 启动 FastAPI 服务..." -ForegroundColor Green
    Write-Host "  > 地址: http://localhost:8000" -ForegroundColor Gray
    Write-Host "  > 文档: http://localhost:8000/docs" -ForegroundColor Gray
    Write-Host ""

    $backendJob = Start-Job -Name "Backend" -ArgumentList $projectRoot -ScriptBlock {
        param($root)
        Set-Location $root
        python -m uvicorn src.api_service:app --host 0.0.0.0 --port 8000 --log-level info 2>&1
    }
    Write-Host "[后端] 已启动 (PID: $($backendJob.Id))" -ForegroundColor Green
}

# 启动前端
if (-not $BackendOnly) {
    Write-Host "[前端] 启动 Vite 开发服务器..." -ForegroundColor Green
    Write-Host "  > 地址: http://localhost:5173" -ForegroundColor Gray
    Write-Host ""

    $frontendJob = Start-Job -Name "Frontend" -ArgumentList $projectRoot -ScriptBlock {
        param($root)
        Set-Location "$root\frontend"
        npm run dev 2>&1
    }
    Write-Host "[前端] 已启动 (PID: $($frontendJob.Id))" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  后端: http://localhost:8000" -ForegroundColor Yellow
Write-Host "  前端: http://localhost:5173" -ForegroundColor Yellow
Write-Host "  按 Ctrl+C 停止所有服务" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 等前端就绪后自动打开浏览器
if (-not $BackendOnly) {
    Write-Host "[前端] 等待服务就绪，即将打开浏览器..." -ForegroundColor Green
    Start-Sleep -Seconds 5
    Start-Process "http://localhost:5173"
    Write-Host "[浏览器] 已打开 http://localhost:5173" -ForegroundColor Green
}

# 等待用户中断
try {
    while ($true) {
        # 检查后端状态
        if ($backendJob -and $backendJob.State -eq 'Failed') {
            Write-Host "[后端] 异常退出:" -ForegroundColor Red
            Receive-Job $backendJob | Select-Object -Last 20 | ForEach-Object { Write-Host "  $_" }
            break
        }
        if ($frontendJob -and $frontendJob.State -eq 'Failed') {
            Write-Host "[前端] 异常退出:" -ForegroundColor Red
            Receive-Job $frontendJob | Select-Object -Last 20 | ForEach-Object { Write-Host "  $_" }
            break
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host ""
    Write-Host "正在停止所有服务..." -ForegroundColor Yellow
    if ($backendJob) {
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -ErrorAction SilentlyContinue
        Write-Host "[后端] 已停止" -ForegroundColor Gray
    }
    if ($frontendJob) {
        Stop-Job $frontendJob -ErrorAction SilentlyContinue
        Remove-Job $frontendJob -ErrorAction SilentlyContinue
        Write-Host "[前端] 已停止" -ForegroundColor Gray
    }
    Write-Host "所有服务已停止" -ForegroundColor Green
}
