#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import urllib.parse
import mimetypes
import time
import json
import uuid
from datetime import datetime
from html import escape
from werkzeug.utils import secure_filename
from markupsafe import Markup
from flask import Flask, render_template_string, request, send_file, jsonify, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room

# ✅ Set your upload directory here
UPLOAD_DIR = r"C:\Users\sushant.kanchan\Downloads\shareMe\uploadFiles"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Flask app setup
app = Flask(__name__, static_url_path='/_static')
app.config['SECRET_KEY'] = 'riddler_secret_key_2024'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 * 1024  # 16GB max upload
socketio = SocketIO(app, cors_allowed_origins="*", max_size=16 * 1024 * 1024 * 1024)

# Chat storage
chat_messages = []
MAX_CHAT_HISTORY = 1000

# Known devices (by IP) and live socket connection counts
known_users = {}
socket_counts = {}

# Recent clients tracker
recent_clients = {}
CLIENT_RECENT_SECONDS = 60 * 10  # 10 minutes

# HTML Template
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Riddler's LAN Server</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%95%B5%3C/text%3E%3C/svg%3E">
  <!-- Local copies first (works offline / behind firewalls); CDN only as a fallback -->
  <script src="/_static/vendor/tailwind.js"></script>
  <script>window.tailwind || document.write('<scr' + 'ipt src="https://cdn.tailwindcss.com"></scr' + 'ipt>');</script>
  <script src="/_static/vendor/socket.io.min.js"></script>
  <script>window.io || document.write('<scr' + 'ipt src="https://cdn.socket.io/4.5.4/socket.io.min.js"></scr' + 'ipt>');</script>
  <style>
    :root{--wa-bg:#111827;--wa-panel:#1f2937;--wa-panel2:#374151;--wa-line:#2b3647;--wa-text:#f3f4f6;--wa-muted:#9ca3af;--wa-accent:#22d3ee;--wa-accent2:#0891b2;--wa-accent3:#0e7490;--wa-out:#166534;--wa-out-text:#fff;--wa-in:#1f2937;--wa-chat:#0b1220;--wa-input:#374151;--wa-chip:#1f2937;--wa-foot:rgba(255,255,255,.6);--wa-green:#4ade80;--wa-dots:rgba(34,211,238,.05);--wa-shadow:rgba(0,0,0,.45)}
    :root.wa-light{--wa-bg:#ffffff;--wa-panel:#f0f2f5;--wa-panel2:#e3e7ea;--wa-line:#e4e8eb;--wa-text:#111b21;--wa-muted:#667781;--wa-accent:#008069;--wa-accent2:#00a884;--wa-accent3:#008069;--wa-out:#d9fdd3;--wa-out-text:#111b21;--wa-in:#ffffff;--wa-chat:#e6f0fa;--wa-input:#ffffff;--wa-chip:#ffffff;--wa-foot:#667781;--wa-green:#008069;--wa-dots:rgba(0,0,0,.035);--wa-shadow:rgba(11,20,26,.13)}
    .wa-hidden{display:none!important}
    body.chat-open #scrollBtn{display:none}
    .wa-root{position:fixed;left:0;right:0;bottom:0;top:var(--hdr,64px);z-index:5;background:var(--wa-bg);color:var(--wa-text);display:flex;flex-direction:column;font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:14px;animation:waIn .28s cubic-bezier(.2,.8,.2,1) both}
    .wa-root.wa-closing{animation:waOut .2s ease-in both}
    @keyframes waIn{from{opacity:0;transform:translateY(28px) scale(.985)}to{opacity:1;transform:none}}
    @keyframes waOut{from{opacity:1;transform:none}to{opacity:0;transform:translateY(28px) scale(.985)}}
    @keyframes waPop{from{opacity:0;transform:translateY(8px) scale(.94)}to{opacity:1;transform:none}}
    @keyframes waRow{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:none}}
    @keyframes waPulse{0%,100%{opacity:1}50%{opacity:.35}}
    @keyframes waBadge{0%{transform:scale(.4)}60%{transform:scale(1.25)}100%{transform:scale(1)}}
    @keyframes waFade{from{opacity:0}to{opacity:1}}
    .wa-root *,.wa-modal *{box-sizing:border-box}
    .wa-topbar{height:48px;flex:0 0 auto;display:flex;align-items:center;gap:12px;padding:0 16px;border-bottom:1px solid var(--wa-line)}
    .wa-title{font-size:16px;font-weight:700;color:var(--wa-accent)}
    .wa-spacer{flex:1}
    .wa-iconbtn{width:34px;height:34px;border-radius:50%;border:0;background:transparent;color:var(--wa-muted);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:0 0 auto;transition:background .15s,color .15s,transform .15s}
    .wa-iconbtn:hover{background:var(--wa-panel2);color:var(--wa-text)}
    .wa-iconbtn:active{transform:scale(.9)}
    .wa-body{flex:1;display:flex;min-height:0}
    .wa-body.list-collapsed .wa-list{display:none}
    .wa-list{width:30%;min-width:300px;max-width:400px;border-right:1px solid var(--wa-line);display:flex;flex-direction:column;background:var(--wa-bg)}
    .wa-list-head{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 2px}
    .wa-list-head h2{font-size:18px;font-weight:700;margin:0;color:var(--wa-text)}
    .wa-me{padding:0 16px 8px;font-size:12px;color:var(--wa-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .wa-me button{color:var(--wa-accent);background:none;border:0;cursor:pointer;font-size:12px;margin-left:6px;padding:0}
    .wa-me button:hover{text-decoration:underline}
    .wa-search{margin:4px 12px 8px;background:var(--wa-panel);border:1px solid transparent;border-radius:999px;display:flex;align-items:center;gap:8px;padding:0 14px;height:38px;color:var(--wa-muted);transition:border-color .2s,box-shadow .2s}
    .wa-search:focus-within{border-color:var(--wa-accent);box-shadow:0 0 0 3px rgba(34,211,238,.15)}
    .wa-search input{flex:1;min-width:0;border:0;background:transparent;outline:none;font-size:14px;color:var(--wa-text)}
    .wa-chips{display:flex;gap:8px;padding:0 12px 10px}
    .wa-chip{border:0;background:var(--wa-panel);color:var(--wa-muted);border-radius:999px;padding:5px 13px;font-size:13px;font-weight:500;cursor:pointer;transition:background .2s,color .2s,transform .15s}
    .wa-chip:hover{background:var(--wa-panel2);color:var(--wa-text)}
    .wa-chip:active{transform:scale(.95)}
    .wa-chip.active{background:color-mix(in srgb,var(--wa-accent) 16%,transparent);color:var(--wa-accent)}
    .wa-rows{flex:1;overflow-y:auto}
    .wa-rows.stagger .wa-row{animation:waRow .35s both;animation-delay:calc(var(--i,0)*45ms)}
    .wa-row{display:flex;gap:12px;padding:11px 14px;cursor:pointer;border-bottom:1px solid var(--wa-line);transition:background .15s,transform .15s}
    .wa-row:hover{background:var(--wa-panel)}
    .wa-row:active{transform:scale(.99)}
    .wa-row.active{background:var(--wa-panel);box-shadow:inset 3px 0 0 var(--wa-accent)}
    .wa-avatar{border-radius:50%;color:#fff;font-weight:600;display:flex;align-items:center;justify-content:center;flex:0 0 auto;transition:transform .2s}
    .wa-row:hover .wa-avatar{transform:scale(1.06)}
    .wa-row-body{flex:1;min-width:0}
    .wa-row-top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
    .wa-row-name{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--wa-text)}
    .wa-row-time{font-size:11px;color:var(--wa-muted);white-space:nowrap}
    .wa-row-time.unread{color:var(--wa-accent)}
    .wa-row-msg{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:13px;color:var(--wa-muted);margin-top:1px;min-height:19px}
    .wa-row-msg .txt{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .wa-unread{background:var(--wa-accent2);color:#fff;border-radius:999px;min-width:18px;height:18px;padding:0 6px;font-size:11px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;animation:waBadge .35s both}
    .wa-row-meta{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--wa-muted);margin-top:3px}
    .wa-pill{background:var(--wa-panel2);color:var(--wa-muted);border-radius:999px;padding:1px 8px;font-size:10px;font-weight:600;letter-spacing:.4px}
    .wa-pill.on{background:color-mix(in srgb,var(--wa-green) 18%,transparent);color:var(--wa-green)}
    .wa-conv{flex:1;min-width:0;display:flex;flex-direction:column;background:var(--wa-chat)}
    .wa-empty{flex:1;display:flex;align-items:center;justify-content:center;color:var(--wa-muted);font-size:15px;text-align:center;padding:24px}
    .wa-conv-inner{display:flex;flex-direction:column;height:100%;min-height:0;animation:waIn .25s ease both}
    .wa-conv-head{height:58px;flex:0 0 auto;background:var(--wa-panel);display:flex;align-items:center;gap:12px;padding:0 16px;border-bottom:1px solid var(--wa-line)}
    .wa-back{display:none}
    .wa-head-info{min-width:0}
    .wa-head-name{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .wa-head-sub{font-size:12px;color:var(--wa-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .wa-live{color:var(--wa-green);font-weight:500;animation:waPulse 1.8s ease-in-out infinite}
    .wa-msgs{flex:1;overflow-y:auto;padding:16px 6% 10px;background-image:radial-gradient(var(--wa-dots) 1px,transparent 1px);background-size:22px 22px}
    .wa-day{text-align:center;margin:12px 0}
    .wa-day span{display:inline-block;background:var(--wa-chip);border-radius:8px;padding:4px 12px;font-size:12px;color:var(--wa-muted);box-shadow:0 1px 2px var(--wa-shadow)}
    .wa-msg-row{display:flex;margin:2px 0}
    .wa-msg-row.first{margin-top:8px}
    .wa-msg-row.out{justify-content:flex-end}
    .wa-msg-row.anim .wa-bubble{animation:waPop .25s cubic-bezier(.2,.9,.3,1.2) both}
    .wa-msg-row.out.anim .wa-bubble{transform-origin:bottom right}
    .wa-msg-row.in.anim .wa-bubble{transform-origin:bottom left}
    .wa-bubble{position:relative;max-width:min(75%,620px);padding:6px 10px 5px;border-radius:10px;box-shadow:0 1px 2px var(--wa-shadow);font-size:14px;line-height:1.4}
    .wa-bubble.in{background:var(--wa-in);color:var(--wa-text)}
    .wa-bubble.out{background:var(--wa-out);color:var(--wa-out-text)}
    .wa-bubble.first::before{content:"";position:absolute;top:0;width:10px;height:12px}
    .wa-bubble.in.first{border-top-left-radius:0}
    .wa-bubble.out.first{border-top-right-radius:0}
    .wa-bubble.in.first::before{left:-8px;background:var(--wa-in);clip-path:polygon(100% 0,100% 100%,0 0)}
    .wa-bubble.out.first::before{right:-8px;background:var(--wa-out);clip-path:polygon(0 0,100% 0,0 100%)}
    .wa-sender{font-size:12px;font-weight:600;margin-bottom:2px}
    .wa-sender small{font-weight:400;color:var(--wa-muted);margin-left:6px}
    .wa-text{white-space:pre-wrap;word-break:break-word;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
    .wa-foot{display:flex;justify-content:flex-end;align-items:center;gap:8px;margin-top:2px;font-size:11px;color:var(--wa-foot)}
    .wa-copy{border:0;background:transparent;color:var(--wa-foot);cursor:pointer;padding:3px;display:inline-flex;border-radius:4px;transition:background .15s,color .15s,transform .15s}
    .wa-copy:hover{background:color-mix(in srgb,var(--wa-text) 12%,transparent);color:var(--wa-text)}
    .wa-copy:active{transform:scale(.85)}
    .wa-copy.copied{color:var(--wa-green)}
    .wa-composer{flex:0 0 auto;background:var(--wa-panel);display:flex;align-items:flex-end;gap:10px;padding:8px 12px;border-top:1px solid var(--wa-line)}
    .wa-composer textarea{flex:1;min-width:0;resize:none;border:1px solid transparent;outline:none;border-radius:20px;padding:8px 16px;font-size:14px;max-height:140px;height:38px;line-height:20px;overflow-y:hidden;scrollbar-width:thin;font-family:inherit;color:var(--wa-text);background:var(--wa-input);transition:border-color .2s,box-shadow .2s}
    .wa-composer textarea:focus{border-color:var(--wa-accent);box-shadow:0 0 0 3px rgba(34,211,238,.15)}
    .wa-composer textarea::placeholder{color:var(--wa-muted)}
    .wa-send{width:38px;height:38px;border-radius:50%;background:var(--wa-accent2);color:#fff;border:0;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;transition:background .15s,transform .15s}
    .wa-send:hover{background:var(--wa-accent3);transform:scale(1.08) rotate(-8deg)}
    .wa-send:active{transform:scale(.9)}
    .wa-badge-top{position:absolute;top:-9px;right:-9px;background:#22c55e;color:#fff;border-radius:999px;font-size:12px;font-weight:700;min-width:20px;height:20px;line-height:20px;padding:0 6px;text-align:center;animation:waBadge .35s both}
    .wa-modal{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;padding:16px;font-family:ui-sans-serif,system-ui,sans-serif;animation:waFade .2s both}
    .wa-card{background:var(--wa-bg);color:var(--wa-text);border:1px solid var(--wa-line);border-radius:14px;padding:22px;width:100%;max-width:380px;box-shadow:0 10px 40px rgba(0,0,0,.6);animation:waPop .3s cubic-bezier(.2,.9,.3,1.2) both}
    .wa-card h3{margin:0 0 6px;font-size:17px;font-weight:700;color:var(--wa-accent)}
    .wa-card p{margin:0 0 14px;color:var(--wa-muted);font-size:13px}
    .wa-card input{width:100%;border:1px solid var(--wa-panel2);border-radius:10px;padding:9px 12px;font-size:14px;outline:none;color:var(--wa-text);background:var(--wa-panel);transition:border-color .2s,box-shadow .2s}
    .wa-card input:focus{border-color:var(--wa-accent);box-shadow:0 0 0 3px rgba(34,211,238,.15)}
    .wa-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:16px}
    .wa-btn{border:0;border-radius:999px;padding:7px 18px;font-size:14px;font-weight:600;cursor:pointer;background:var(--wa-panel2);color:var(--wa-text);transition:background .15s,transform .15s}
    .wa-btn:active{transform:scale(.95)}
    .wa-btn.primary{background:var(--wa-accent2);color:#fff}
    .wa-btn.primary:hover{background:var(--wa-accent3)}
    .wa-rows::-webkit-scrollbar,.wa-msgs::-webkit-scrollbar{width:8px}
    .wa-rows::-webkit-scrollbar-thumb,.wa-msgs::-webkit-scrollbar-thumb{background:var(--wa-panel2);border-radius:8px}
    @media (max-width:760px){
      .wa-list{width:100%;max-width:none;min-width:0;border-right:0}
      .wa-body:not(.show-conv) .wa-conv{display:none}
      .wa-body.show-conv .wa-list{display:none}
      .wa-back{display:inline-flex}
      .wa-msgs{padding:12px 10px}
      .wa-bubble{max-width:88%}
    }
    @media (prefers-reduced-motion:reduce){.wa-root,.wa-root *,.wa-modal,.wa-modal *{animation:none!important;transition:none!important}}

    /* ---------- rChatServer: Cloudscape-style (overrides the base chat rules above) ---------- */
    :root{--wa-bg:#192534;--wa-panel:#212f42;--wa-panel2:#354150;--wa-line:#354150;--wa-text:#e9ebed;--wa-muted:#9ba7b6;--wa-accent:#539fe5;--wa-accent2:#0972d3;--wa-accent3:#033160;--wa-out:#12263c;--wa-out-text:#e9ebed;--wa-in:#192534;--wa-chat:#0f1b2a;--wa-input:#0f1b2a;--wa-chip:#192534;--wa-foot:#9ba7b6;--wa-green:#29ad32;--wa-dots:transparent;--wa-shadow:rgba(0,0,0,.4)}
    :root.wa-light{--wa-bg:#ffffff;--wa-panel:#f1f6fb;--wa-panel2:#e9ebed;--wa-line:#d5dbdb;--wa-text:#0f1b2a;--wa-muted:#5f6b7a;--wa-accent:#0972d3;--wa-accent2:#0972d3;--wa-accent3:#033160;--wa-out:#f2f8fd;--wa-out-text:#0f1b2a;--wa-in:#ffffff;--wa-chat:#f2f3f3;--wa-input:#ffffff;--wa-chip:#ffffff;--wa-foot:#5f6b7a;--wa-green:#037f0c;--wa-dots:transparent;--wa-shadow:rgba(0,28,36,.15)}
    .wa-root{background:var(--pg-bg);padding:16px max(16px,calc((100vw - 1200px) / 2)) 20px;font-family:"Amazon Ember","Helvetica Neue",Roboto,Arial,sans-serif}
    .wa-topbar{height:auto;background:transparent;border:0;padding:0 0 14px;gap:12px}
    .wa-title{font-size:22px;font-weight:700;color:var(--wa-text);line-height:1.2}
    .wa-subtitle{font-size:13px;color:var(--wa-muted);margin-top:2px}
    .wa-topbtn{border:1px solid var(--wa-line);color:var(--wa-text)}
    .wa-iconbtn{color:var(--wa-text)}
    .wa-iconbtn:hover{background:var(--wa-panel)}
    .wa-body{gap:16px}
    .wa-list,.wa-conv{border:1px solid var(--wa-line);border-radius:8px;overflow:hidden;box-shadow:0 1px 1px rgba(0,28,36,.12)}
    .wa-list{background:var(--wa-bg)}
    .wa-conv{background:var(--wa-chat)}
    .wa-conv-head,.wa-composer{background:var(--wa-bg)}
    .wa-search{background:var(--pg-input);border:1px solid var(--pg-border);border-radius:8px;height:36px}
    .wa-search:focus-within{border-color:var(--pg-focus);box-shadow:0 0 0 2px color-mix(in srgb,var(--pg-focus) 30%,transparent)}
    .wa-chip{background:transparent;border:1px solid var(--wa-line);color:var(--wa-text);padding:4px 14px}
    .wa-chip:hover{background:var(--wa-panel);color:var(--wa-text)}
    .wa-chip.active{background:var(--wa-accent2);border-color:var(--wa-accent2);color:#fff}
    .wa-row.active{background:var(--wa-panel)}
    .wa-unread{background:var(--wa-accent2)}
    .wa-pill{background:none;padding:0;color:var(--wa-muted);font-size:12px;font-weight:400;letter-spacing:0}
    .wa-pill::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--wa-muted);margin-right:6px}
    .wa-pill.on{background:none;color:var(--wa-green)}
    .wa-pill.on::before{background:var(--wa-green)}
    .wa-head-name{color:var(--wa-text)}
    .wa-day span{background:var(--wa-bg);border:1px solid var(--wa-line);box-shadow:none}
    .wa-bubble{border-radius:12px;box-shadow:none}
    .wa-bubble.in{border:1px solid var(--wa-line)}
    .wa-bubble.out{border:1px solid color-mix(in srgb,var(--wa-accent) 55%,transparent)}
    .wa-bubble.first::before{display:none}
    .wa-bubble.in.first,.wa-bubble.out.first{border-radius:12px}
    .wa-composer textarea{border-radius:8px;border:1px solid var(--pg-border)}
    .wa-composer textarea:focus{border-color:var(--pg-focus);box-shadow:0 0 0 2px color-mix(in srgb,var(--pg-focus) 30%,transparent)}
    .wa-send{background:#ff9900;color:#0f1b2a}
    .wa-send:hover{background:#ec7211;transform:scale(1.08)}
    .wa-badge-top{background:#d91515}
    .wa-btn{background:transparent;border:2px solid var(--wa-accent);color:var(--wa-accent)}
    .wa-btn.primary{background:#ff9900;border-color:#ff9900;color:#0f1b2a}
    .wa-btn.primary:hover{background:#ec7211;border-color:#ec7211}
    .wa-card h3{color:var(--wa-text)}
    @media (max-width:760px){
      .wa-root{padding:10px 10px 12px}
      .wa-body{gap:0}
    }
    /* ---------- page theme (AWS console style) ---------- */
    :root{--pg-bg:#0f1b2a;--pg-card:#192534;--pg-border:#354150;--pg-text:#e9ebed;--pg-muted:#9ba7b6;--pg-link:#539fe5;--pg-hover:#212f42;--pg-input:#0f1b2a;--pg-focus:#539fe5;--pg-btn-text:#539fe5;--pg-btn-hover:rgba(83,159,229,.14)}
    :root.wa-light{--pg-bg:#f2f3f3;--pg-card:#ffffff;--pg-border:#d5dbdb;--pg-text:#0f1b2a;--pg-muted:#5f6b7a;--pg-link:#0972d3;--pg-hover:#f1f6fb;--pg-input:#ffffff;--pg-focus:#0972d3;--pg-btn-text:#0972d3;--pg-btn-hover:rgba(9,114,211,.08)}
    body.pg-body{background:var(--pg-bg);color:var(--pg-text);font-family:"Amazon Ember","Helvetica Neue",Roboto,Arial,sans-serif;transition:background .2s,color .2s}
    .hdr{background:#232f3e;box-shadow:0 1px 0 #3b4a5c;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:8px 16px;gap:12px}
    .hdr-title{font-size:22px;font-weight:700;color:#22d3ee;white-space:nowrap}
    .hdr-right{display:flex;align-items:center;justify-content:flex-end;gap:12px;min-width:0}
    .hdr-iconbtn{width:34px;height:34px;border-radius:50%;border:0;background:transparent;color:#539fe5;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;transition:background .15s}
    .hdr-iconbtn:hover{background:#354150}
    .hdr-id{text-align:right;line-height:1.15;cursor:pointer;min-width:0;max-width:150px}
    .hdr-ip{font-size:13px;font-weight:700;color:#f3f4f6}
    .hdr-name{font-size:12px;color:#9ba7b6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .hdr-id:hover .hdr-name{color:#22d3ee}
    .hdr-panel{position:absolute;right:0;top:100%;margin-top:10px;width:min(19rem,88vw);background:#1b2733;color:#f3f4f6;border:1px solid #354150;border-radius:8px;box-shadow:0 8px 28px rgba(0,0,0,.55);padding:18px;z-index:50;animation:waPop .2s both}
    .hdr-panel h3{font-size:18px;font-weight:700;margin:0 0 12px}
    .hdr-panel hr{border:0;border-top:1px solid #354150;margin:12px 0}
    .hdr-panel .lbl{font-weight:700;font-size:14px;margin-bottom:8px}
    .hdr-panel .lbl em{font-weight:400;color:#9ba7b6}
    .hdr-panel label{display:flex;align-items:center;gap:10px;padding:5px 0;cursor:pointer;font-size:14px}
    .hdr-panel input[type=radio]{accent-color:#539fe5;width:16px;height:16px}
    .hdr-panel .linkbtn{background:none;border:0;color:#539fe5;font-weight:700;font-size:14px;cursor:pointer;padding:0}
    .hdr-panel .linkbtn:hover{text-decoration:underline}
    .pg-btn{border-radius:999px;font-weight:700;font-size:14px;padding:6px 20px;cursor:pointer;border:2px solid transparent;transition:background .15s,transform .15s,box-shadow .15s;display:inline-block}
    .pg-btn:active{transform:scale(.97)}
    .pg-btn.primary{background:#ff9900;color:#0f1b2a;border-color:#ff9900}
    .pg-btn.primary:hover{background:#ec7211;border-color:#ec7211}
    .pg-btn.secondary{background:transparent;color:var(--pg-btn-text);border-color:var(--pg-btn-text)}
    .pg-btn.secondary:hover{background:var(--pg-btn-hover)}
    .pg-item{background:var(--pg-card);border:1px solid var(--pg-border)}
    .pg-card{background:var(--pg-card);border:1px solid var(--pg-border);border-radius:8px;box-shadow:0 1px 1px rgba(0,28,36,.12)}
    .pg-card-head{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px 20px;border-bottom:1px solid var(--pg-border)}
    .pg-h2{font-size:20px;font-weight:700;line-height:1.2;margin:0}
    .pg-count{font-weight:400;color:var(--pg-muted);font-size:16px;margin-left:4px}
    .pg-sub{margin:4px 0 0;font-size:13px;color:var(--pg-muted)}
    .pg-search{position:relative;width:100%;max-width:280px}
    .pg-search input{width:100%;background:var(--pg-input);color:var(--pg-text);border:1px solid var(--pg-border);border-radius:8px;padding:6px 30px 6px 34px;font-size:14px;outline:none;transition:border-color .15s,box-shadow .15s}
    .pg-search input::placeholder{color:var(--pg-muted)}
    .pg-search input:focus{border-color:var(--pg-focus);box-shadow:0 0 0 2px color-mix(in srgb,var(--pg-focus) 30%,transparent)}
    .pg-search .mag{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--pg-muted);display:inline-flex}
    .pg-search button{position:absolute;right:8px;top:50%;transform:translateY(-50%);color:var(--pg-muted);font-size:12px;background:none;border:0;cursor:pointer}
    .pg-search button:hover{color:#ef4444}
    .pg-path{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 20px;font-size:13px;color:var(--pg-muted);border-bottom:1px solid var(--pg-border)}
    .pg-path a{color:var(--pg-link);text-decoration:none;font-weight:700}
    .pg-path a:hover{text-decoration:underline}
    .pg-table-wrap{overflow-x:auto}
    .pg-table{width:100%;border-collapse:collapse;font-size:14px}
    .pg-table th{text-align:left;font-weight:700;font-size:13px;color:var(--pg-muted);padding:10px 16px;border-bottom:1px solid var(--pg-border);white-space:nowrap;user-select:none}
    .pg-table th.sortable{cursor:pointer}
    .pg-table th.sortable:hover{color:var(--pg-text)}
    .pg-table th[aria-sort]::after{content:"";display:inline-block;margin-left:7px;vertical-align:middle;border:4px solid transparent}
    .pg-table th[aria-sort="ascending"]::after{border-bottom:5px solid var(--pg-link);border-top:0}
    .pg-table th[aria-sort="descending"]::after{border-top:5px solid var(--pg-link);border-bottom:0}
    .pg-table td{padding:9px 16px;border-bottom:1px solid var(--pg-border);vertical-align:middle}
    .pg-table tbody tr:last-child td{border-bottom:0}
    .pg-table tr.file-item{transition:background .12s}
    .pg-table tr.file-item:hover{background:var(--pg-hover)}
    .pg-name{display:flex;align-items:center;gap:10px;min-width:0}
    .pg-name a{color:var(--pg-link);text-decoration:none;word-break:break-word}
    .pg-name a:hover{text-decoration:underline}
    .pg-ficon{flex:0 0 auto;display:inline-flex}
    .pg-muted{color:var(--pg-muted);white-space:nowrap}
    .pg-empty{padding:28px 20px;text-align:center;color:var(--pg-muted)}
    .pg-hide{display:none!important}
    :root.wa-light #dropzone{border-color:#aab7b8}
    :root.wa-light #dropzone .text-gray-400{color:#5f6b7a}
    :root.wa-light #attachBtn{background:#fff;color:#0f1b2a;border:1px solid #d5dbdb}
    :root.wa-light #attachBtn:hover{background:#f1f6fb}
    body.pg-body{overflow-x:clip}
    html.chat-open,html.chat-open body{overflow:hidden!important}
    .wa-root{overscroll-behavior:contain}
    .wa-rows,.wa-msgs{overscroll-behavior:contain}
    @media (max-width:700px){
      .hdr{grid-template-columns:1fr;justify-items:center;padding:6px 10px;gap:4px}
      .hdr-side{display:none}
      .hdr-title{font-size:16px}
      .hdr-right{width:100%;justify-content:center;gap:14px}
      .hdr-id{max-width:none;text-align:left}
      .hdr-panel,#whoDropdown{position:fixed!important;left:8px!important;right:8px!important;top:calc(var(--hdr,96px) + 4px)!important;width:auto!important;margin-top:0!important}
      main{padding:10px!important}
      .pg-card-head{padding:12px}
      .pg-search{max-width:none}
      .pg-col-type{display:none}
      .pg-table,.pg-table tbody,.pg-table thead{display:block}
      .pg-table thead tr{display:flex;gap:2px;padding:0 4px;border-bottom:1px solid var(--pg-border)}
      .pg-table th{border:0;padding:8px}
      .pg-table tr.file-item{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding:9px 12px;border-bottom:1px solid var(--pg-border)}
      .pg-table tbody tr.file-item:last-child{border-bottom:0}
      .pg-table tr.file-item td{display:block;border:0;padding:0}
      .pg-table tr.file-item td.pg-col-type{display:none}
      .pg-table tr.file-item td:first-child{grid-column:1/-1}
      .pg-table tr.file-item td.pg-muted{font-size:12px}
      .pg-table tr.file-item td:last-child{text-align:right}
      .pg-btn{padding:6px 16px}
    }
  </style>
  <script>
    (function () {
      var p = "dark";
      try { p = localStorage.getItem("rc_theme") || "dark"; } catch (e) {}
      var light = p === "light" || (p === "auto" && window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches);
      document.documentElement.classList.toggle("wa-light", light);
    })();
  </script>
  <script>
    const myIP = "{{ client_ip }}";
    let selectedFiles = [];
    let socket = null;
    let allMessages = [];
    let users = {};
    let activeChat = null;   // "everyone" or the other device's IP
    let chatOpen = false;
    let listFilter = "all";
    let listQuery = "";
    let lastRead = {};
    let lastReadFresh = true;
    let seenIds = new Set();
    let chatScrollY = 0;
    try {
      const stored = localStorage.getItem("rc_lastRead");
      if (stored) { lastRead = JSON.parse(stored); lastReadFresh = false; }
    } catch (e) {}

    document.addEventListener("DOMContentLoaded", () => {
      initChat();

      const dropZone = document.getElementById("dropzone");
      const fileInput = document.getElementById("fileInput");
      const fileList = document.getElementById("fileList");

      // Who's Connected dropdown
      const whoBtn = document.getElementById("whoBtn");
      const whoDropdown = document.getElementById("whoDropdown");
      const whoList = document.getElementById("whoList");
      const whoRefresh = document.getElementById("whoRefresh");

      whoBtn.addEventListener("click", () => {
        if (whoDropdown.classList.contains("hidden")) {
          whoDropdown.classList.remove("hidden");
          fetchClients();
        } else {
          whoDropdown.classList.add("hidden");
        }
      });

      whoRefresh.addEventListener("click", () => {
        fetchClients();
      });

      document.addEventListener("click", (e) => {
        if (!whoBtn.contains(e.target) && !whoDropdown.contains(e.target)) {
          whoDropdown.classList.add("hidden");
        }
      });

      function fetchClients() {
        fetch("/_clients")
          .then(res => res.json())
          .then(data => {
            whoList.innerHTML = "";
            if (data.length === 0) {
              whoList.innerHTML = '<div class="px-3 py-2 text-gray-400">No recent connections found</div>';
              return;
            }
            data.forEach(client => {
              const agoSec = Math.floor((Date.now() - client.last_seen*1000) / 1000);
              let agoStr = "";
              if (agoSec < 60) agoStr = `${agoSec}s ago`;
              else if (agoSec < 3600) agoStr = `${Math.floor(agoSec/60)}m ago`;
              else agoStr = `${Math.floor(agoSec/3600)}h ago`;

              const div = document.createElement("div");
              div.className = "px-3 py-2 border-b border-gray-700 hover:bg-gray-700 cursor-default";

              const nameEl = document.createElement("div");
              nameEl.className = "font-semibold text-cyan-200";
              nameEl.textContent = displayName(client.ip) + " · " + client.ip;
              const uaEl = document.createElement("div");
              uaEl.className = "text-gray-400 text-xs";
              uaEl.textContent = client.ua;
              const agoEl = document.createElement("div");
              agoEl.className = "text-xs text-cyan-300";
              agoEl.textContent = agoStr;

              div.appendChild(nameEl);
              div.appendChild(uaEl);
              div.appendChild(agoEl);
              whoList.appendChild(div);
            });
          })
          .catch(() => {
            whoList.innerHTML = '<div class="px-3 py-2 text-red-500">Oops! Error loading clients</div>';
          });
      }

      // File upload functionality
      dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("bg-blue-100", "border-blue-500");
      });

      dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("bg-blue-100", "border-blue-500");
      });

      dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("bg-blue-100", "border-blue-500");
        addFiles(e.dataTransfer.files);
      });

      fileInput.addEventListener("change", () => {
        addFiles(fileInput.files);
        fileInput.value = "";
      });

      function addFiles(files) {
        for (let file of files) {
          selectedFiles.push(file);
        }
        renderFileList();
      }

      window.removeFile = function(index) {
        selectedFiles.splice(index, 1);
        renderFileList();
      }

      function renderFileList() {
        fileList.innerHTML = "";
        selectedFiles.forEach((file, index) => {
          const li = document.createElement("li");
          li.className = "pg-item flex justify-between items-center px-4 py-2 rounded";
          li.innerHTML = `
            <span class="truncate">${file.name} (${(file.size / 1024).toFixed(1)} KB)</span>
            <button onclick="removeFile(${index})" class="text-red-400 hover:text-red-600">❌</button>
          `;
          fileList.appendChild(li);
        });
      }

      window.submitSelectedFiles = function() {
        if (selectedFiles.length === 0) {
          alert("Pehle files to select kar le (¬_¬'')💢");
          return;
        }

        const formData = new FormData();
        for (let file of selectedFiles) {
          formData.append("files", file);
        }

        const xhr = new XMLHttpRequest();

        const progressContainer = document.getElementById("uploadProgressContainer");
        const progressBar = document.getElementById("uploadProgressBar");
        const statusText = document.getElementById("uploadStatusText");

        progressContainer.classList.remove("hidden");
        progressBar.style.width = "0%";
        statusText.textContent = "Uploading... 0%";

        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            const percentComplete = Math.round((e.loaded / e.total) * 100);
            progressBar.style.width = percentComplete + "%";

            const hue = percentComplete * 1.2;
            const saturation = 90;
            const lightness = 50;
            const color = `hsl(${hue}, ${saturation}%, ${lightness}%)`;

            progressBar.style.backgroundColor = color;
            progressBar.style.boxShadow = `0 0 4px ${color}`;

            statusText.textContent = `Uploading... ${percentComplete}%`;
            if (percentComplete == 100)
              statusText.textContent = `Uploaded ${percentComplete}%. Finalizing...`;
          }
        });

        xhr.onload = () => {
          statusText.textContent = "✅ Upload complete!";
          setTimeout(() => {
            progressContainer.classList.add("hidden");
            location.reload();
          }, 2700);
        };

        xhr.onerror = () => {
          statusText.textContent = "❌ Upload failed.";
          progressBar.classList.replace("bg-cyan-500", "bg-red-500");
          setTimeout(() => {
            progressContainer.classList.add("hidden");
          }, 3000);
        };

        xhr.open("POST", "/upload", true);
        xhr.send(formData);
      };


      fetchClients();
      setInterval(fetchClients, 30000); // Refresh clients every 30 seconds
    });
    // ================= rChatServer (WhatsApp-style) =================
    const AV_COLORS = ["#8e24aa", "#d81b60", "#00897b", "#5e35b1", "#1e88e5", "#f4511e", "#6d4c41", "#3949ab", "#c0392b", "#00838f"];
    const SVG_OPEN = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">';
    const ICON_COPY = SVG_OPEN + '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    const ICON_CHECK = SVG_OPEN + '<polyline points="20 6 9 17 4 12"/></svg>';

    function el(id) { return document.getElementById(id); }
    function isNarrow() { return window.innerWidth <= 760; }

    function defaultName(ip) {
      const p = ip.split(".");
      return p.length === 4 ? "noob " + p[2] + "." + p[3] : "noob " + ip.slice(-5);
    }
    function displayName(ip) {
      const u = users[ip];
      return (u && u.name) ? u.name : defaultName(ip);
    }
    function colorFor(s) {
      let h = 0;
      for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
      return AV_COLORS[h % AV_COLORS.length];
    }
    function lightColorFor(s) {
      let h = 0;
      for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
      return "hsl(" + (h % 360) + ", 70%, " + (isLightTheme() ? "36%" : "68%") + ")";
    }
    function isLightTheme() { return document.documentElement.classList.contains("wa-light"); }
    function themePref() {
      try { return localStorage.getItem("rc_theme") || "dark"; } catch (e) { return "dark"; }
    }
    function applyTheme() {
      const pref = themePref();
      const light = pref === "light" || (pref === "auto" && window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches);
      document.documentElement.classList.toggle("wa-light", light);
      document.querySelectorAll('input[name="vmode"]').forEach(r => { r.checked = (r.value === pref); });
    }
    function setThemePref(p) {
      try { localStorage.setItem("rc_theme", p); } catch (e) {}
      applyTheme();
      refreshChatUI();
    }
    function renderIdentity() {
      const ip = el("hdrIp"), nm = el("hdrName");
      if (!ip || !nm) return;
      ip.textContent = myIP;
      nm.textContent = displayName(myIP);
    }
    function initHeaderMenus() {
      syncHeaderHeight();
      const btn = el("settingsBtn"), panel = el("settingsPanel");
      btn.addEventListener("click", (e) => { e.stopPropagation(); panel.classList.toggle("hidden"); });
      document.addEventListener("click", (e) => {
        if (!panel.contains(e.target) && !btn.contains(e.target)) panel.classList.add("hidden");
      });
      document.addEventListener("keydown", (e) => { if (e.key === "Escape") panel.classList.add("hidden"); });
      document.querySelectorAll('input[name="vmode"]').forEach(r => r.addEventListener("change", () => setThemePref(r.value)));
      el("editNameBtn").addEventListener("click", () => { panel.classList.add("hidden"); showNameModal(); });
      el("hdrId").addEventListener("click", showNameModal);
      if (window.matchMedia) {
        const mq = window.matchMedia("(prefers-color-scheme: light)");
        const onChange = () => { if (themePref() === "auto") { applyTheme(); refreshChatUI(); } };
        if (mq.addEventListener) mq.addEventListener("change", onChange);
      }
    }
    function initialsOf(name) {
      const w = name.trim().split(" ").filter(Boolean);
      return (w.length > 1 ? w[0][0] + w[1][0] : name.slice(0, 2)).toUpperCase();
    }
    function makeAvatar(name, key, size) {
      const d = document.createElement("div");
      d.className = "wa-avatar";
      d.style.width = d.style.height = size + "px";
      d.style.fontSize = Math.round(size * 0.38) + "px";
      if (key === "everyone") {
        d.style.background = "#0972d3";
        d.textContent = "👥";
      } else {
        d.style.background = colorFor(key);
        d.textContent = initialsOf(name);
      }
      return d;
    }
    function mk(tag, cls, text) {
      const n = document.createElement(tag);
      if (cls) n.className = cls;
      if (text !== undefined) n.textContent = text;
      return n;
    }

    // ---- time formatting ----
    function ordinal(n) {
      const s = ["th", "st", "nd", "rd"], v = n % 100;
      return n + (s[(v - 20) % 10] || s[v] || s[0]);
    }
    function dayStart(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); }
    function fmtTime(ts) {
      return new Date(ts * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }).toLowerCase();
    }
    function fmtDay(ts) {
      const d = new Date(ts * 1000);
      const diff = Math.round((dayStart(new Date()) - dayStart(d)) / 86400000);
      if (diff === 0) return "Today";
      if (diff === 1) return "Yesterday";
      if (diff > 1 && diff < 7) return d.toLocaleDateString("en-US", { weekday: "long" });
      return ordinal(d.getDate()) + " " + d.toLocaleDateString("en-US", { month: "long" }) + ", " + d.getFullYear();
    }
    function fmtListTime(ts) {
      return dayStart(new Date(ts * 1000)) === dayStart(new Date()) ? fmtTime(ts) : fmtDay(ts);
    }

    // ---- conversations ----
    function convKey(m) { return m.to === "everyone" ? "everyone" : (m.ip === myIP ? m.to : m.ip); }
    function convMessages(key) {
      return allMessages.filter(m => convKey(m) === key).sort((a, b) => a.time - b.time);
    }
    function unreadFor(key) {
      const lr = lastRead[key] || 0;
      return allMessages.filter(m => convKey(m) === key && m.ip !== myIP && m.time > lr).length;
    }
    function totalUnread() {
      let n = 0;
      new Set(allMessages.map(convKey)).forEach(k => { n += unreadFor(k); });
      return n;
    }
    function saveLastRead() {
      try { localStorage.setItem("rc_lastRead", JSON.stringify(lastRead)); } catch (e) {}
    }
    function markRead(key) {
      const ms = convMessages(key);
      if (!ms.length) return;
      const t = ms[ms.length - 1].time;
      if ((lastRead[key] || 0) < t) { lastRead[key] = t; saveLastRead(); }
    }
    function updateBadge() {
      const n = totalUnread();
      const b = el("chatBadge");
      b.textContent = n > 99 ? "99+" : n;
      b.classList.toggle("wa-hidden", n === 0);
    }

    // ---- copy (clipboard API only works on https/localhost, so keep the fallback) ----
    function legacyCopy(text, done) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        if (document.execCommand("copy")) done(); else alert("Copy failed. Please copy manually.");
      } catch (err) {
        alert("Copy failed. Please copy manually.");
      }
      document.body.removeChild(ta);
    }
    function copyText(text, btn) {
      const done = () => {
        btn.innerHTML = ICON_CHECK;
        btn.classList.add("copied");
        setTimeout(() => { btn.innerHTML = ICON_COPY; btn.classList.remove("copied"); }, 1000);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done).catch(() => legacyCopy(text, done));
      } else {
        legacyCopy(text, done);
      }
    }

    // ---- rendering ----
    function renderMe() {
      const me = el("waMe");
      me.textContent = "You: " + displayName(myIP) + " · " + myIP;
      const b = mk("button", "", "Edit name");
      b.addEventListener("click", showNameModal);
      me.appendChild(b);
    }

    function renderList() {
      const rows = el("waRows");
      rows.innerHTML = "";

      const keys = new Set(Object.keys(users));
      allMessages.forEach(m => { const k = convKey(m); if (k !== "everyone") keys.add(k); });
      keys.delete(myIP);

      const entries = [{ key: "everyone" }];
      keys.forEach(ip => entries.push({ key: ip }));
      entries.forEach(e => {
        const ms = convMessages(e.key);
        e.last = ms.length ? ms[ms.length - 1] : null;
        e.unread = unreadFor(e.key);
        e.name = e.key === "everyone" ? "Everyone" : displayName(e.key);
        e.online = e.key === "everyone" ? true : !!(users[e.key] && users[e.key].online);
      });
      entries.sort((a, b) => {
        if (a.key === "everyone") return -1;
        if (b.key === "everyone") return 1;
        return ((b.last ? b.last.time : 0) - (a.last ? a.last.time : 0)) || (Number(b.online) - Number(a.online));
      });

      const shown = entries.filter(e => {
        if (listFilter === "unread" && e.unread === 0) return false;
        if (listFilter === "online" && !e.online) return false;
        if (listQuery && !(e.name.toLowerCase().includes(listQuery) || e.key.includes(listQuery))) return false;
        return true;
      });

      if (!shown.length) {
        rows.appendChild(mk("div", "wa-empty", "No chats found"));
        return;
      }

      let shownIdx = 0;
      shown.forEach(e => {
        const row = mk("div", "wa-row" + (e.key === activeChat ? " active" : ""));
        row.style.setProperty("--i", String(shownIdx++));
        row.addEventListener("click", () => selectChat(e.key));
        row.appendChild(makeAvatar(e.name, e.key, 42));

        const body = mk("div", "wa-row-body");
        const top = mk("div", "wa-row-top");
        top.appendChild(mk("span", "wa-row-name", e.name));
        if (e.last) top.appendChild(mk("span", "wa-row-time" + (e.unread ? " unread" : ""), fmtListTime(e.last.time)));
        body.appendChild(top);

        const mid = mk("div", "wa-row-msg");
        let preview = "No messages yet";
        if (e.last) {
          const prefix = e.last.ip === myIP ? "You: " : (e.key === "everyone" ? displayName(e.last.ip) + ": " : "");
          preview = prefix + e.last.msg;
        }
        mid.appendChild(mk("span", "txt", preview));
        if (e.unread) mid.appendChild(mk("span", "wa-unread", e.unread > 99 ? "99+" : String(e.unread)));
        body.appendChild(mid);

        const meta = mk("div", "wa-row-meta");
        meta.appendChild(mk("span", "", e.key === "everyone" ? "All devices on this LAN" : e.key));
        if (e.key !== "everyone") meta.appendChild(mk("span", "wa-pill" + (e.online ? " on" : ""), e.online ? "Online" : "Offline"));
        body.appendChild(meta);

        row.appendChild(body);
        rows.appendChild(row);
      });
    }

    function updateHeader() {
      if (!activeChat) return;
      const key = activeChat;
      const name = key === "everyone" ? "Everyone" : displayName(key);
      const av = el("waHeadAvatar");
      av.innerHTML = "";
      av.appendChild(makeAvatar(name, key, 40));
      el("waHeadName").textContent = name;

      const sub = el("waHeadSub");
      sub.innerHTML = "";
      if (key === "everyone") {
        const online = Object.values(users).filter(u => u.online).length;
        sub.textContent = "Public chat · " + online + " online";
      } else {
        const u = users[key];
        sub.appendChild(document.createTextNode(key + " • "));
        if (u && u.online) sub.appendChild(mk("span", "wa-live", "● Live"));
        else sub.appendChild(document.createTextNode(u ? "last seen " + fmtListTime(u.last_seen) : "offline"));
      }
    }

    function renderMessages() {
      if (!activeChat) return;
      const box = el("waMessages");
      const sameChat = box.dataset.key === activeChat;
      const oldTop = box.scrollTop;
      const nearBottom = !sameChat || (box.scrollHeight - box.scrollTop - box.clientHeight < 80);
      box.innerHTML = "";
      box.dataset.key = activeChat;

      let prevDay = null, prevSender = null;
      if (!sameChat) seenIds = new Set();
      convMessages(activeChat).forEach(m => {
        const day = dayStart(new Date(m.time * 1000));
        if (day !== prevDay) {
          const chip = mk("div", "wa-day");
          chip.appendChild(mk("span", "", fmtDay(m.time)));
          box.appendChild(chip);
          prevDay = day;
          prevSender = null;
        }
        const self = m.ip === myIP;
        const first = prevSender !== m.ip;
        prevSender = m.ip;

        const isNew = sameChat && !seenIds.has(m.id);
        seenIds.add(m.id);
        const row = mk("div", "wa-msg-row " + (self ? "out" : "in") + (first ? " first" : "") + (isNew ? " anim" : ""));
        const bubble = mk("div", "wa-bubble " + (self ? "out" : "in") + (first ? " first" : ""));

        if (!self && activeChat === "everyone" && first) {
          const sender = mk("div", "wa-sender", displayName(m.ip));
          sender.style.color = lightColorFor(m.ip);
          sender.appendChild(mk("small", "", m.ip));
          bubble.appendChild(sender);
        }
        bubble.appendChild(mk("div", "wa-text", m.msg));

        const foot = mk("div", "wa-foot");
        const copy = mk("button", "wa-copy");
        copy.title = "Copy message";
        copy.innerHTML = ICON_COPY;
        copy.addEventListener("click", () => copyText(m.msg, copy));
        foot.appendChild(copy);
        foot.appendChild(mk("span", "", fmtTime(m.time)));
        bubble.appendChild(foot);

        row.appendChild(bubble);
        box.appendChild(row);
      });

      box.scrollTop = nearBottom ? box.scrollHeight : oldTop;
    }

    function refreshChatUI() {
      updateBadge();
      renderIdentity();
      if (!chatOpen) return;
      renderMe();
      renderList();
      updateHeader();
      renderMessages();
    }

    // ---- actions ----
    function selectChat(key) {
      activeChat = key;
      markRead(key);
      el("waEmpty").classList.add("wa-hidden");
      el("waConvInner").classList.remove("wa-hidden");
      el("waBody").classList.add("show-conv");
      refreshChatUI();
      if (!isNarrow()) el("waInput").focus();
    }
    function backToList() {
      activeChat = null;
      el("waBody").classList.remove("show-conv");
      el("waEmpty").classList.remove("wa-hidden");
      el("waConvInner").classList.add("wa-hidden");
      refreshChatUI();
    }
    function toggleList() {
      if (isNarrow()) backToList();
      else el("waBody").classList.toggle("list-collapsed");
    }
    function syncHeaderHeight() {
      const h = document.querySelector("header");
      if (h) document.documentElement.style.setProperty("--hdr", h.offsetHeight + "px");
    }
    window.addEventListener("resize", syncHeaderHeight);
    function openChat() {
      if (chatOpen) return;
      chatOpen = true;
      syncHeaderHeight();
      el("chatModal").classList.remove("wa-closing", "wa-hidden");
      chatScrollY = window.scrollY;
      window.scrollTo(0, 0);
      document.body.classList.add("chat-open");
      document.documentElement.classList.add("chat-open");
      const rows = el("waRows");
      rows.classList.add("stagger");
      setTimeout(() => rows.classList.remove("stagger"), 900);
      if (activeChat) selectChat(activeChat);
      else if (!isNarrow()) selectChat("everyone");
      else refreshChatUI();
    }
    function closeChat() {
      if (!chatOpen) return;
      chatOpen = false;
      const root = el("chatModal");
      root.classList.add("wa-closing");
      document.body.classList.remove("chat-open");
      document.documentElement.classList.remove("chat-open");
      window.scrollTo(0, chatScrollY);
      setTimeout(() => {
        if (!chatOpen) root.classList.add("wa-hidden");
        root.classList.remove("wa-closing");
      }, 200);
    }
    function refreshChat() {
      if (socket) socket.emit("hello", { name: savedName() });
    }
    function fitComposer() {
      const input = el("waInput");
      input.style.height = "auto";
      const h = Math.max(38, Math.min(input.scrollHeight + 2, 140));
      input.style.height = h + "px";
      input.style.overflowY = input.scrollHeight + 2 > 140 ? "auto" : "hidden";
    }
    function sendChatMessage() {
      if (!activeChat) return;
      const input = el("waInput");
      const msg = input.value.trim();
      if (!msg) return;
      socket.emit("send_message", { message: msg, to: activeChat });
      input.value = "";
      input.style.height = "";
      input.style.overflowY = "hidden";
      input.focus();
    }

    // ---- display name (optional) ----
    function savedName() {
      try { return localStorage.getItem("rc_name") || ""; } catch (e) { return ""; }
    }
    function showNameModal() {
      const input = el("nameInput");
      input.value = savedName();
      input.placeholder = defaultName(myIP);
      el("nameModal").classList.remove("wa-hidden");
      setTimeout(() => input.focus(), 50);
    }
    function saveName(skip) {
      const v = skip ? savedName() : el("nameInput").value.trim().slice(0, 24);
      try {
        localStorage.setItem("rc_asked", "1");
        if (!skip) localStorage.setItem("rc_name", v);
      } catch (e) {}
      if (!skip && socket) socket.emit("set_name", { name: v });
      el("nameModal").classList.add("wa-hidden");
    }

    function initChat() {
      socket = io();

      socket.on("connect", () => { socket.emit("hello", { name: savedName() }); });

      socket.on("chat_history", (d) => {
        allMessages = d.messages;
        if (lastReadFresh) {
          // first ever visit: don't flag old history as unread
          new Set(allMessages.map(convKey)).forEach(k => {
            const ms = convMessages(k);
            lastRead[k] = ms[ms.length - 1].time;
          });
          lastReadFresh = false;
          saveLastRead();
        }
        refreshChatUI();
      });

      socket.on("users", (list) => {
        users = {};
        list.forEach(u => { users[u.ip] = u; });
        refreshChatUI();
      });

      socket.on("new_message", (m) => {
        if (allMessages.some(x => x.id === m.id)) return;
        allMessages.push(m);
        if (chatOpen && activeChat === convKey(m)) markRead(activeChat);
        refreshChatUI();
      });

      el("waSearch").addEventListener("input", (e) => {
        listQuery = e.target.value.trim().toLowerCase();
        renderList();
      });
      document.querySelectorAll(".wa-chip").forEach(b => {
        b.addEventListener("click", () => {
          listFilter = b.dataset.f;
          document.querySelectorAll(".wa-chip").forEach(x => x.classList.toggle("active", x === b));
          renderList();
        });
      });

      const input = el("waInput");
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
      });
      input.addEventListener("input", fitComposer);
      el("nameInput").addEventListener("keydown", (e) => {
        if (e.key === "Enter") saveName(false);
      });

      applyTheme();
      renderIdentity();
      initHeaderMenus();

      let asked = true;
      try { asked = !!localStorage.getItem("rc_asked"); } catch (e) {}
      if (!asked) showNameModal();
      updateBadge();
    }
    // Scroll toggle logic
    function toggleScroll() {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const scrollHeight = document.documentElement.scrollHeight;
      const clientHeight = document.documentElement.clientHeight;

      if (scrollTop + clientHeight >= scrollHeight - 5) {
        window.scrollTo({ top: 0, behavior: 'smooth' });
        document.getElementById("scrollBtn").innerText = "⬇️";
      } else {
        window.scrollTo({ top: scrollHeight, behavior: 'smooth' });
        document.getElementById("scrollBtn").innerText = "⬆️";
      }
    }

    window.addEventListener("scroll", () => {
      const btn = document.getElementById("scrollBtn");
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const scrollHeight = document.documentElement.scrollHeight;
      const clientHeight = document.documentElement.clientHeight;

      if (scrollTop + clientHeight >= scrollHeight - 5) {
        btn.title = "scroll to top";
        btn.innerText = "⬆️";
      } else {
        btn.title = "scroll to bottom";
        btn.innerText = "⬇️";
      }
    });
  </script>
</head>
<body class="pg-body">
  <header class="hdr sticky top-0 z-10">
    <div class="hdr-side"></div>
    <div class="hdr-title">🕵 Riddler's LAN Server 🌐</div>
    <div class="hdr-right">
      <div class="relative">
        <button id="settingsBtn" class="hdr-iconbtn" title="Settings">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </button>
        <div id="settingsPanel" class="hidden hdr-panel">
          <h3>Current user settings</h3>
          <hr>
          <div class="lbl">Visual mode - <em>beta</em></div>
          <label><input type="radio" name="vmode" value="auto"> Browser default</label>
          <label><input type="radio" name="vmode" value="light"> Light</label>
          <label><input type="radio" name="vmode" value="dark"> Dark</label>
          <hr>
          <button id="editNameBtn" class="linkbtn" type="button">Edit display name</button>
        </div>
      </div>
      <div class="relative">
        <button id="whoBtn" class="bg-gray-700 hover:bg-gray-600 text-sm text-white px-3 py-1 rounded">H.C</button>
        <div id="whoDropdown" class="hidden absolute right-0 mt-2 w-64 bg-gray-800 text-sm text-gray-100 rounded shadow-lg z-50">
          <div class="px-3 py-2 border-b border-gray-700 text-xs text-gray-300">Recent devices (last 10 min)</div>
          <div id="whoList" class="max-h-48 overflow-auto"></div>
          <div class="px-2 py-2 text-right">
            <button id="whoRefresh" class="text-xs text-cyan-300 hover:underline px-2">Refresh ↻</button>
          </div>
        </div>
      </div>
      <div class="hdr-id" id="hdrId" title="Click to edit your display name">
        <div class="hdr-ip" id="hdrIp"></div>
        <div class="hdr-name" id="hdrName"></div>
      </div>
    </div>
  </header>

  <main class="max-w-5xl mx-auto p-4">
    {% if success_message %}
    <div class="bg-green-600 p-2 rounded mb-4 text-white">{{ success_message }}</div>
    {% endif %}

    <div id="dropzone" class="border-4 border-dashed border-gray-600 p-6 text-center rounded-lg mb-6 cursor-pointer transition">
      <p class="text-lg">📂 Drag & Drop files here</p>
      <p class="text-sm text-gray-400">or use the file picker below</p>
    </div>

    <div class="mb-8">
      <input type="file" id="fileInput" multiple hidden />
      <button type="button" id="attachBtn" onclick="document.getElementById('fileInput').click()" class="block w-full text-sm text-gray-300 bg-gray-800 rounded px-3 py-1.5 cursor-pointer hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-cyan-500">🔗 Attach Files</button>
      <ul id="fileList" class="mt-4 space-y-2"></ul>
      <button type="submit" onclick="submitSelectedFiles()" class="pg-btn secondary mt-4"> Upload </button>
      <button onclick="openChat()" class="pg-btn primary relative mt-4 ml-3"> rChatServer <span id="chatBadge" class="wa-badge-top wa-hidden">0</span></button>
    </div>

<section class="pg-card">
  <div class="pg-card-head">
    <div>
      <h2 class="pg-h2">🗃️ Uploaded Files <span class="pg-count" id="fileCount"></span></h2>
      <p class="pg-sub">Click a file to download it, or a folder to open it.</p>
    </div>
    <div class="pg-search">
      <span class="mag"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg></span>
      <input id="fileSearch" type="text" placeholder="Find files  ( / )" autocomplete="off">
      <button id="fileSearchClear" type="button" title="Clear (Esc)" class="pg-hide">✕</button>
    </div>
  </div>
  {% if current_path %}
  <div class="pg-path">
    <span>📂 Current Path: /{{ current_path }}</span>
    <a href="{{ parent_path }}" title="Go up one level">➽ Back</a>
  </div>
  {% endif %}
  <div class="pg-table-wrap">
    <table class="pg-table">
      <thead>
        <tr>
          <th class="sortable" data-sort="name" aria-sort="ascending">Name</th>
          <th class="sortable pg-col-type" data-sort="type">Type</th>
          <th class="sortable" data-sort="size">Size</th>
          <th class="sortable" data-sort="mtime">Last modified</th>
        </tr>
      </thead>
      <tbody id="fileItems">
        {% for file in files %}
        <tr class="file-item" data-name="{{ file.name|lower }}" data-type="{{ file.type|lower }}" data-size="{{ file.size_bytes }}" data-mtime="{{ file.mtime }}" data-dir="{{ 1 if file.is_dir else 0 }}">
          <td><div class="pg-name"><span class="pg-ficon">{{ file.icon }}</span><a href="{{ file.url }}">{{ file.name }}</a></div></td>
          <td class="pg-muted pg-col-type">{{ file.type }}</td>
          <td class="pg-muted">{{ file.size }}</td>
          <td class="pg-muted">{{ file.timestamp }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <div id="fileEmpty" class="pg-empty pg-hide"></div>
</section>
<script>
  (function () {
    const input = document.getElementById("fileSearch");
    const clear = document.getElementById("fileSearchClear");
    const empty = document.getElementById("fileEmpty");
    const count = document.getElementById("fileCount");
    const body = document.getElementById("fileItems");
    const heads = Array.from(document.querySelectorAll(".pg-table th.sortable"));
    const items = Array.from(body.querySelectorAll(".file-item"));
    let sortKey = "name", sortDir = 1;

    function cmp(a, b) {
      if (a.dataset.dir !== b.dataset.dir) return Number(b.dataset.dir) - Number(a.dataset.dir);
      let r = 0;
      if (sortKey === "size" || sortKey === "mtime") r = Number(a.dataset[sortKey]) - Number(b.dataset[sortKey]);
      else if (sortKey === "type") r = a.dataset.type.localeCompare(b.dataset.type);
      if (r === 0) return a.dataset.name.localeCompare(b.dataset.name, undefined, { numeric: true });
      return r * sortDir;
    }
    function nameSortDir(a, b) {
      if (a.dataset.dir !== b.dataset.dir) return Number(b.dataset.dir) - Number(a.dataset.dir);
      return a.dataset.name.localeCompare(b.dataset.name, undefined, { numeric: true }) * sortDir;
    }
    function applySort() {
      items.sort(sortKey === "name" ? nameSortDir : cmp).forEach(li => body.appendChild(li));
      heads.forEach(h => {
        if (h.dataset.sort === sortKey) h.setAttribute("aria-sort", sortDir === 1 ? "ascending" : "descending");
        else h.removeAttribute("aria-sort");
      });
    }
    heads.forEach(h => h.addEventListener("click", () => {
      if (sortKey === h.dataset.sort) sortDir = -sortDir;
      else { sortKey = h.dataset.sort; sortDir = (sortKey === "mtime" || sortKey === "size") ? -1 : 1; }
      applySort();
    }));

    function applyFilter() {
      const terms = input.value.toLowerCase().split(" ").filter(Boolean);
      let shown = 0;
      items.forEach(li => {
        const name = li.dataset.name;
        const ok = terms.every(t => name.includes(t));
        li.classList.toggle("pg-hide", !ok);
        if (ok) shown++;
      });
      clear.classList.toggle("pg-hide", !input.value);
      count.textContent = terms.length ? "(" + shown + "/" + items.length + ")" : "(" + items.length + ")";
      let msg = "";
      if (items.length === 0) msg = "This folder is empty.";
      else if (terms.length && shown === 0) msg = 'No files match "' + input.value.trim() + '"';
      empty.textContent = msg;
      empty.classList.toggle("pg-hide", !msg);
    }

    input.addEventListener("input", applyFilter);
    clear.addEventListener("click", () => { input.value = ""; applyFilter(); input.focus(); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { input.value = ""; applyFilter(); input.blur(); }
    });
    document.addEventListener("keydown", (e) => {
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && !chatOpen) {
        e.preventDefault();
        input.focus();
      }
    });
    applySort();
    applyFilter();
  })();
</script>

    <footer class="mt-10 text-sm text-center text-gray-500">
      Made by Sushant Kanchan 🕵 aka Riddler<br>
      Access from any device on Riddler's LAN
    </footer>
  </main>

  <div id="chatModal" class="wa-root wa-hidden">
    <div class="wa-topbar">
      <button class="wa-iconbtn wa-topbtn" title="Toggle chat list" onclick="toggleList()">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="9" y1="3" x2="9" y2="21"/><polyline points="15 9 12 12 15 15"/></svg>
      </button>
      <div>
        <div class="wa-title">rChatServer 𐦂𖨆𐀪𖠋</div>
        <div class="wa-subtitle">Chat with devices on this LAN</div>
      </div>
      <span class="wa-spacer"></span>
      <button class="wa-iconbtn" title="Close chat" onclick="closeChat()">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/></svg>
      </button>
    </div>
    <div class="wa-body" id="waBody">
      <aside class="wa-list">
        <div class="wa-list-head">
          <h2>Chats</h2>
          <button class="wa-iconbtn" title="Refresh" onclick="refreshChat()">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/></svg>
          </button>
        </div>
        <div class="wa-me" id="waMe"></div>
        <div class="wa-search">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>
          <input id="waSearch" type="text" placeholder="Search name or IP" autocomplete="off">
        </div>
        <div class="wa-chips">
          <button class="wa-chip active" data-f="all">All</button>
          <button class="wa-chip" data-f="unread">Unread</button>
          <button class="wa-chip" data-f="online">Online</button>
        </div>
        <div class="wa-rows" id="waRows"></div>
      </aside>
      <section class="wa-conv">
        <div class="wa-empty" id="waEmpty">Select a chat to start messaging</div>
        <div class="wa-conv-inner wa-hidden" id="waConvInner">
          <header class="wa-conv-head">
            <button class="wa-iconbtn wa-back" title="Back" onclick="backToList()">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            </button>
            <div id="waHeadAvatar"></div>
            <div class="wa-head-info">
              <div class="wa-head-name" id="waHeadName"></div>
              <div class="wa-head-sub" id="waHeadSub"></div>
            </div>
          </header>
          <div class="wa-msgs" id="waMessages"></div>
          <div class="wa-composer">
            <textarea id="waInput" rows="1" placeholder="Type a message"></textarea>
            <button class="wa-send" title="Send" onclick="sendChatMessage()">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>

  <div id="nameModal" class="wa-modal wa-hidden">
    <div class="wa-card">
      <h3>What should we call you?</h3>
      <p>Optional. Others will see this name with your IP. Leave empty to stay as the default.</p>
      <input id="nameInput" type="text" maxlength="24" autocomplete="off">
      <div class="wa-actions">
        <button class="wa-btn" onclick="saveName(true)">Skip</button>
        <button class="wa-btn primary" onclick="saveName(false)">Save</button>
      </div>
    </div>
  </div>

  <button onclick="toggleScroll()" id="scrollBtn" class="fixed bottom-10 right-10 bg-gray-600 hover:bg-cyan-700 text-white px-2 py-2 rounded shadow-lg z-50" title="scroll to bottom">⬇️</button>
  
  <div id="uploadProgressContainer" class="fixed bottom-0 left-0 w-full bg-gray-800 text-white z-50 hidden">
    <div class="px-4 py-2 text-sm" id="uploadStatusText">Uploading...</div>
    <div class="w-full bg-gray-600 h-3">
      <div id="uploadProgressBar" class="bg-cyan-500 h-2 transition-all duration-300" style="width: 0%;"></div>
    </div>
  </div>
</body>
</html>"""


def default_name(ip):
    """Fallback display name from the last two octets, e.g. 'noob 241.37'"""
    parts = ip.split('.')
    if len(parts) == 4:
        return f"noob {parts[2]}.{parts[3]}"
    return f"noob {ip[-5:]}"


def clean_name(raw):
    """Trim a user-supplied display name: printable chars only, max 24"""
    text = ''.join(ch for ch in str(raw or '') if ch.isprintable())
    return text.strip()[:24]


def note_client(ip, user_agent):
    """Track recent client connections"""
    global recent_clients
    now = time.time()
    recent_clients[ip] = {
        "time": now,
        "ua": user_agent
    }
    known_users.setdefault(ip, {"name": "", "last_seen": now})["last_seen"] = now


def users_payload():
    return [
        {
            "ip": ip,
            "name": u["name"] or default_name(ip),
            "online": socket_counts.get(ip, 0) > 0,
            "last_seen": u["last_seen"],
        }
        for ip, u in known_users.items()
    ]


def broadcast_users():
    socketio.emit('users', users_payload())


def visible_to(msg, ip):
    """Public messages, or private ones the device sent / received"""
    return msg["to"] == "everyone" or msg["ip"] == ip or msg["to"] == ip


def _svg(color, inner):
    return Markup(
        '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="' + color +
        '" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + inner + '</svg>'
    )


_FILE_BASE = '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>'
_LINES = '<line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/>'

# category -> (colour, svg inner, extensions)
FILE_KINDS = {
    "image":   ("#10b981", '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>', "jpg jpeg png gif bmp webp svg ico tif tiff heic"),
    "pdf":     ("#ef4444", _FILE_BASE + _LINES, "pdf"),
    "doc":     ("#3b82f6", _FILE_BASE + _LINES, "doc docx rtf odt"),
    "sheet":   ("#22c55e", _FILE_BASE + '<rect x="8" y="12" width="8" height="6"/><line x1="12" y1="12" x2="12" y2="18"/><line x1="8" y1="15" x2="16" y2="15"/>', "xls xlsx xlsm ods csv tsv"),
    "slides":  ("#f97316", '<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>', "ppt pptx odp"),
    "text":    ("#94a3b8", _FILE_BASE + _LINES, "txt md log ini cfg conf"),
    "archive": ("#a855f7", '<polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/>', "zip rar 7z tar gz tgz bz2 xz"),
    "apk":     ("#84cc16", '<path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7z"/><polyline points="3.3 7 12 12 20.7 7"/><line x1="12" y1="22" x2="12" y2="12"/>', "apk aab"),
    "exe":     ("#64748b", '<rect x="3" y="3" width="18" height="18" rx="2"/><polyline points="7 9 10 12 7 15"/><line x1="12" y1="15" x2="17" y2="15"/>', "exe msi bat cmd sh ps1 dll"),
    "disk":    ("#06b6d4", '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>', "iso img dmg"),
    "audio":   ("#ec4899", '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>', "mp3 wav flac aac ogg m4a wma"),
    "video":   ("#8b5cf6", '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>', "mp4 mkv avi mov wmv webm flv 3gp"),
    "code":    ("#0ea5e9", '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>', "py js ts html htm css java c cpp h cs go rs php rb sql"),
    "data":    ("#eab308", '<path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5a2 2 0 0 0 2 2h1"/><path d="M16 21h1a2 2 0 0 0 2-2v-5a2 2 0 0 1 2-2 2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"/>', "json xml yaml yml toml"),
    "key":     ("#f43f5e", '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>', "pem key crt cer pfx ppk"),
    "font":    ("#64748b", '<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/>', "ttf otf woff woff2"),
    "mail":    ("#14b8a6", '<path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><polyline points="22 6 12 13 2 6"/>', "eml msg pst"),
    "book":    ("#d97706", '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>', "epub mobi"),
}
KIND_BY_EXT = {ext: kind for kind, (_, _, exts) in FILE_KINDS.items() for ext in exts.split()}
FOLDER_ICON = _svg("#f59e0b", '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>')
DEFAULT_ICON = _svg("#94a3b8", _FILE_BASE)


def file_icon(name, is_dir):
    """Inline SVG icon picked from the file extension"""
    if is_dir:
        return FOLDER_ICON
    kind = KIND_BY_EXT.get(os.path.splitext(name)[1].lstrip('.').lower())
    if not kind:
        return DEFAULT_ICON
    color, inner, _ = FILE_KINDS[kind]
    return _svg(color, inner)


def file_type(name, is_dir):
    if is_dir:
        return "Folder"
    ext = os.path.splitext(name)[1].lstrip('.')
    return ext.upper() if ext else "File"


def format_size(n):
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:,.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:,.1f} MB"
    if n >= 1024:
        return f"{n / 1024:,.0f} KB"
    return f"{n} B"


def get_file_list(directory, current_subpath=''):
    """Get list of files/folders (folders first) with metadata"""
    try:
        names = os.listdir(directory)
    except OSError:
        return []

    files = []
    for name in names:
        full_path = os.path.join(directory, name)
        try:
            st = os.stat(full_path)
        except OSError:
            continue
        is_dir = os.path.isdir(full_path)
        url_path = current_subpath + '/' + name if current_subpath else name

        files.append({
            'name': name + "/" if is_dir else name,
            'icon': file_icon(name, is_dir),
            'type': file_type(name, is_dir),
            'is_dir': is_dir,
            'size': "—" if is_dir else format_size(st.st_size),
            'size_bytes': -1 if is_dir else st.st_size,
            'mtime': int(st.st_mtime),
            'timestamp': datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            'url': urllib.parse.quote(url_path)
        })

    files.sort(key=lambda f: (not f['is_dir'], f['name'].lower()))
    return files


@app.route('/', defaults={'subpath': ''})
@app.route('/<path:subpath>')
def index(subpath=''):
    """Main page - file listing with subdirectory support"""
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    note_client(client_ip, user_agent)
    
    # Construct the full path
    current_dir = os.path.join(UPLOAD_DIR, subpath)
    
    # Security check - prevent directory traversal
    current_dir = os.path.normpath(current_dir)
    if not current_dir.startswith(os.path.abspath(UPLOAD_DIR)):
        return "Access denied", 403
    
    # If it's a file, download it
    if os.path.isfile(current_dir):
        return send_file(current_dir, as_attachment=True)
    
    # If it's a directory, list its contents
    if not os.path.isdir(current_dir):
        return "Directory not found", 404
    
    files = get_file_list(current_dir, subpath)
    success_message = request.args.get('success', '')

    # Calculate parent path for back button
    parent_path = '/'
    if subpath:
        parent_parts = subpath.split('/')
        if len(parent_parts) > 1:
            parent_path = '/' + '/'.join(parent_parts[:-1])
    
    return render_template_string(
        HTML_TEMPLATE,
        client_ip=client_ip,
        files=files,
        success_message=success_message,
        current_path=subpath,
        parent_path=parent_path
    )


@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads"""
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    note_client(client_ip, user_agent)
    
    if 'files' not in request.files:
        return redirect('/?success=⚠️ No files uploaded')
    
    files = request.files.getlist('files')
    uploaded_names = []
    
    for file in files:
        if file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_DIR, filename)
            file.save(file_path)
            uploaded_names.append(filename)
    
    if uploaded_names:
        success_msg = f"✅ Uploaded: {', '.join(uploaded_names)}"
    else:
        success_msg = "⚠️ No files uploaded"
    
    return redirect(f'/?success={urllib.parse.quote(success_msg)}')


# @app.route('/<path:filename>')
# def download_file(filename):
#     """Download/view a file"""
#     client_ip = request.remote_addr
#     user_agent = request.headers.get('User-Agent', 'Unknown')
#     note_client(client_ip, user_agent)
    
#     file_path = os.path.join(UPLOAD_DIR, filename)
    
#     if not os.path.exists(file_path):
#         return "File not found", 404
    
#     if os.path.isdir(file_path):
#         # If it's a directory, show file listing for that directory
#         # For simplicity, redirect to main page
#         return redirect('/')
    
#     return send_file(file_path, as_attachment=True)


@app.route('/_clients')
def get_clients():
    """API endpoint for recent clients"""
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    note_client(client_ip, user_agent)
    
    cutoff = time.time() - CLIENT_RECENT_SECONDS
    items = [
        {"ip": ip, "last_seen": data["time"], "ua": data["ua"]}
        for ip, data in recent_clients.items()
        if data["time"] >= cutoff
    ]
    items.sort(key=lambda x: x["last_seen"], reverse=True)
    
    return jsonify(items)


# ============= WebSocket Events =============

@socketio.on('connect')
def handle_connect():
    """New WebSocket connection - the room is always the real socket IP, never client-supplied"""
    client_ip = request.remote_addr
    note_client(client_ip, request.headers.get('User-Agent', 'Unknown'))
    join_room(client_ip)
    socket_counts[client_ip] = socket_counts.get(client_ip, 0) + 1
    print(f"✅ Client connected: {client_ip}")
    broadcast_users()


@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket disconnected"""
    client_ip = request.remote_addr
    socket_counts[client_ip] = max(0, socket_counts.get(client_ip, 1) - 1)
    if client_ip in known_users:
        known_users[client_ip]["last_seen"] = time.time()
    print(f"❌ Client disconnected: {client_ip}")
    broadcast_users()


@socketio.on('hello')
def handle_hello(data):
    """Client (re)syncs: optionally sets its name, then gets users + only the history it may see"""
    client_ip = request.remote_addr
    note_client(client_ip, request.headers.get('User-Agent', 'Unknown'))
    name = clean_name((data or {}).get('name'))
    if name:
        known_users[client_ip]["name"] = name
    emit('chat_history', {'messages': [m for m in chat_messages if visible_to(m, client_ip)]})
    broadcast_users()


@socketio.on('set_name')
def handle_set_name(data):
    """Client changed (or cleared) its display name"""
    client_ip = request.remote_addr
    note_client(client_ip, request.headers.get('User-Agent', 'Unknown'))
    known_users[client_ip]["name"] = clean_name((data or {}).get('name'))
    broadcast_users()


@socketio.on('send_message')
def handle_message(data):
    """Handle incoming chat message"""
    global chat_messages

    client_ip = request.remote_addr
    data = data or {}
    msg = str(data.get('message', ''))[:30000]
    to_field = data.get('to', 'everyone')

    if not msg.strip() or not isinstance(to_field, str):
        return
    if to_field != 'everyone' and to_field not in known_users:
        return

    message_obj = {
        "id": uuid.uuid4().hex[:12],
        "ip": client_ip,
        "msg": msg,
        "time": time.time(),
        "to": to_field
    }

    chat_messages.append(message_obj)
    if len(chat_messages) > MAX_CHAT_HISTORY:
        chat_messages = chat_messages[-MAX_CHAT_HISTORY:]

    if to_field == 'everyone':
        emit('new_message', message_obj, broadcast=True)
        print(f"💬 Broadcast from {client_ip}: {msg[:50]}...")
    else:
        # Only the recipient's and sender's rooms ever receive a private message
        for room in {to_field, client_ip}:
            emit('new_message', message_obj, room=room)
        print(f"🔒 Private message from {client_ip} to {to_field}: {msg[:50]}...")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Riddler's LAN File Server with WebSocket Chat")
    print("="*60)
    print(f"📂 Upload directory: {UPLOAD_DIR}")
    print(f"🌐 Server running at http://0.0.0.0:6969/")
    print("🔍 Find your IP with `ipconfig` (Windows) or `hostname -I` (Linux/macOS)")
    print("   and access from other devices on your LAN.")
    print("💬 Real-time chat powered by Flask-SocketIO")
    print("="*60 + "\n")
    
    socketio.run(app, host='0.0.0.0', port=6969, debug=False, allow_unsafe_werkzeug=True)