import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { createRoot } from 'react-dom/client';

// ---------- NEW • Глобальная тёмная тема из Рекомендация.md ----------
const globalStyles = `
:root{
  --bg:#0f172a;
  --bg-primary:#111827;
  --text:#f1f5f9;
  --text-secondary:#94a3b8;
  --border:#334155;
  --primary:#6366f1;
  --success:#10b981;
  --warning:#f59e0b;
  --danger:#ef4444;
}
/* базовые */
html,body{margin:0;font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--text);}
.container{max-width:1400px;margin:0 auto;padding:1rem;}
.header{margin-bottom:1.5rem;}
.header h1{margin:0;font-size:2.25rem;line-height:1.1;}
.header > div{color: var(--text-secondary); font-size: 1rem; margin-top: 0.25rem;}
/* статистика */
.stats-grid{display:grid;gap:1rem;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));margin-bottom:1.5rem;}
.stat-card{background:var(--bg-primary);border:2px solid; border-radius:.75rem;padding:1.5rem;}
.stat-number{font-size:2.5rem;font-weight:700;line-height:1.1;}
.stat-label{text-transform:uppercase;margin-top:.25rem;font-size:.75rem;color:var(--text-secondary);}

/* === новый список статистики === */
.stats-list{list-style:none;margin:0 0 1.5rem 0;padding:0;}
.stats-list li{display:flex;align-items:center;gap:.75rem;
  font-size:1rem;margin:.75rem 0;padding:.75rem;border-radius:.5rem;
  transition:background .2s ease;}
.stats-list li:hover{background:rgba(255,255,255,.03);}
.stats-list .stat-icon{font-size:1.25rem;width:1.75rem;text-align:center;}
.stats-list .stat-name{color:var(--text-secondary);}
.stats-list .stat-value{font-weight:700;margin-left:.5rem;}
/* быстрые фильтры */
.quick-filters{display:flex;gap:.5rem;margin-bottom:1rem;flex-wrap:wrap;}
.quick-filter{padding:.375rem .75rem;font-size:.8rem;border:1px solid var(--border);
  border-radius:.375rem;background:var(--bg-primary);color:var(--text-secondary);
  cursor:pointer;transition:all .2s ease;}
.quick-filter:hover{border-color:var(--primary);color:var(--text);}
.quick-filter.active{background:var(--primary);color:#fff;border-color:var(--primary);}
/* toast уведомления */
.toast-container{position:fixed;top:1rem;right:1rem;z-index:2000;display:flex;flex-direction:column;gap:.5rem;}
.toast{background:var(--bg-primary);border:1px solid var(--border);border-radius:.5rem;
  padding:1rem;min-width:300px;box-shadow:0 4px 12px rgba(0,0,0,.3);
  transform:translateX(100%);animation:slideIn .3s ease forwards;}
.toast.success{border-left:4px solid var(--success);}
.toast.error{border-left:4px solid var(--danger);}
.toast.info{border-left:4px solid var(--primary);}
.toast-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;}
.toast-title{font-weight:600;font-size:.9rem;}
.toast-message{font-size:.85rem;color:var(--text-secondary);}
.toast-close{background:none;border:none;color:var(--text-secondary);cursor:pointer;padding:0;width:20px;height:20px;}
@keyframes slideIn{to{transform:translateX(0);}}
@keyframes slideOut{to{transform:translateX(100%);}}
/* скелетоны загрузки */
.skeleton{background:linear-gradient(90deg,var(--bg-primary) 25%,rgba(255,255,255,.05) 50%,var(--bg-primary) 75%);
  background-size:200% 100%;animation:shimmer 1.5s infinite;border-radius:.5rem;}
@keyframes shimmer{0%{background-position:200% 0;}100%{background-position:-200% 0;}}
.skeleton-table{border:1px solid var(--border);border-radius:.75rem;overflow:hidden;}
.skeleton-row{display:flex;padding:.75rem 1rem;border-bottom:1px solid var(--border);}
.skeleton-row:last-child{border-bottom:none;}
.skeleton-cell{height:1.2rem;border-radius:.25rem;margin-right:1rem;}
.skeleton-cell:last-child{margin-right:0;}
.skeleton-cell.id{width:80px;}
.skeleton-cell.phone{width:120px;}
.skeleton-cell.date{width:140px;}
.skeleton-cell.duration{width:60px;}
.skeleton-cell.status{width:100px;}
/* фильтры по статусам */
.status-filters{display:flex;gap:.5rem;margin-bottom:1rem;flex-wrap:wrap;align-items:center;}
.status-filters-label{font-size:.875rem;color:var(--text-secondary);margin-right:.5rem;}
.status-chip{padding:.25rem .75rem;font-size:.75rem;border:1px solid var(--border);
  border-radius:1rem;background:var(--bg-primary);color:var(--text-secondary);
  cursor:pointer;transition:all .2s ease;display:flex;align-items:center;gap:.375rem;}
.status-chip:hover{border-color:var(--primary);color:var(--text);}
.status-chip.active{color:#fff;border-color:transparent;}
.status-chip.completed.active{background:var(--success);}
.status-chip.failed.active{background:var(--danger);}
.status-chip.inprogress.active{background:var(--warning);}
.status-chip.all.active{background:var(--primary);}
.status-chip-count{background:rgba(255,255,255,.2);padding:.125rem .375rem;border-radius:.75rem;font-size:.7rem;font-weight:600;}
/* сортировка таблицы */
.sortable-header{cursor:pointer;user-select:none;position:relative;transition:color .2s ease;}
.sortable-header:hover{color:var(--primary);}
.sort-icon{margin-left:.5rem;opacity:.5;transition:opacity .2s ease;}
.sortable-header.active .sort-icon{opacity:1;color:var(--primary);}
/* контролы */
.controls{margin-bottom:1rem;}
.search-row{display:flex;gap:.75rem;margin-bottom:.75rem;align-items:center;}
.actions-row{display:flex;flex-wrap:wrap;gap:.75rem;align-items:center;}
.search-container{position:relative;flex:1 1 280px;}
.search-container svg{position:absolute;left:.75rem;top:50%;transform:translateY(-50%);width:16px;height:16px;color:var(--text-secondary);}
.search-input, input[type="file"]{box-sizing: border-box;}
.search-input{width:100%;padding:.5rem .75rem .5rem 2.25rem;background:var(--bg-primary);border:1px solid var(--border);border-radius:.5rem;color:var(--text);}
.search-input:focus{outline:none;border-color:var(--primary);}
input[type="date"].search-input{max-width:160px;padding-left:.75rem;}
/* кнопки */
.btn{display:inline-flex;align-items:center;gap:.5rem;padding:.5rem 1rem;border:1px solid transparent;border-radius:.5rem;font-size:.875rem;font-weight:500;cursor:pointer;transition:.2s background;
  background:var(--primary);color:#fff; text-decoration: none;}
.btn-secondary{background: var(--border); color: var(--text);}
.btn-success{background:var(--success);}
.btn-danger{background:var(--danger);}
.btn:disabled{opacity:.5;cursor:not-allowed;}
/* таблица */
.table-container{overflow-x:auto;border:1px solid var(--border);border-radius:.75rem;}
table{width:100%;border-collapse:collapse;}
th,td{padding:.75rem 1rem;text-align:left;}
thead{background:var(--bg-primary);}
tbody tr:nth-child(odd){background:rgba(255,255,255,.015);}
tbody tr:hover{background:rgba(99,102,241,.08); cursor: pointer;}
th{font-size:.75rem;text-transform:uppercase;color:var(--text-secondary);}
.status{padding:.25rem .5rem;border-radius:.375rem;font-size:.75rem;font-weight:700;text-transform:uppercase;}
.status.completed{background:rgba(16,185,129,.15);color:var(--success);}
.status.failed{background:rgba(239,68,68,.15);color:var(--danger);}
.status.inprogress{background:rgba(245,158,11,.15);color:var(--warning);}
.status.initiated{background:rgba(99,102,241,.15);color:var(--primary);}
/* модалки */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;z-index:1000; backdrop-filter: blur(4px);}
.modal.show { opacity: 1; visibility: visible; }
.modal-content{background:var(--bg-primary);border-radius:.75rem;max-height:90vh;display: flex; flex-direction: column; overflow: hidden; box-shadow:0 10px 25px rgba(0,0,0,.3); width: 100%;}
.modal-header{display:flex;align-items:center;justify-content:space-between;padding:1rem 1.5rem;border-bottom:1px solid var(--border); flex-shrink: 0;}
.modal-body{padding:0; overflow-y: auto;}
.modal-body-padding{padding:1.5rem;}
.close-btn{background:none;border:none;color:var(--text);cursor:pointer;}
.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:1rem;margin-bottom:1rem;}
.info-item{background:var(--bg);border:1px solid var(--border);border-radius:.5rem;padding:.75rem;}
.info-label{font-size:.7rem;color:var(--text-secondary);text-transform:uppercase;}
.info-value{margin-top:.25rem;font-size:.875rem;}
.transcript h4 { margin: 1.5rem 0 1rem; }
.transcript .turn{padding: 0.75rem 1rem; border-radius: 0.5rem; margin-bottom:.5rem; line-height: 1.5;}
.turn.user{background:var(--primary); color: #fff;}
.turn.bot{background: var(--bg); border: 1px solid var(--border);}
.turn.system{color:var(--warning); text-align: center; font-style: italic;}
/* вкладки */
.tabs{display:flex;border-bottom:1px solid var(--border); padding: 0 1.5rem;}
.tab{padding:.75rem 1rem;cursor:pointer;font-size:.875rem;border-bottom:2px solid transparent; margin-bottom: -1px;}
.tab.active{border-color:var(--primary);color:var(--primary);}
.tab-content { display: none; }
.tab-content.active { display: block; }
.prompt-group { padding: 1.5rem; }
.prompt-label { font-size: 1.125rem; font-weight: 500; margin-bottom: 0.25rem;}
.prompt-description { font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 1rem; }
.prompt-textarea{width:100%;padding:.75rem;background:var(--bg);border:1px solid var(--border);border-radius:.5rem;color:var(--text);font-family:inherit; resize: vertical;}
.actions{display:flex;gap:.75rem;justify-content:space-between; align-items: center; padding:1rem 1.5rem;border-top:1px solid var(--border); background: var(--bg-primary); flex-shrink: 0;}
.status-message { font-size: 0.875rem; color: var(--text-secondary); }
.spinner-wrapper{display:flex; justify-content:center; align-items: center; padding: 3rem;}
.spinner{width:42px;height:42px;border:4px solid var(--primary);border-top-color:transparent;border-radius:50%;animation:spin 1s linear infinite;}@keyframes spin{to{transform:rotate(360deg);}}
.empty-state{display:flex;flex-direction:column;align-items:center;gap:.5rem;padding:2rem;border:1px dashed var(--border);border-radius:.75rem; text-align: center;}
.empty-state svg { width: 3rem; height: 3rem; opacity: 0.5; margin-bottom: 0.5rem; }
.success-message, .error { padding: 0.75rem 1rem; border-radius: 0.5rem; margin-bottom: 1rem; }
.success-message { background: rgba(16,185,129,.15); color: var(--success); }
.error { background: rgba(239,68,68,.15); color: var(--danger); }

/* form fields (settings modal) */
.form-field{display:flex;flex-direction:column;gap:.35rem;margin-bottom:1rem;}
.form-field .hint{font-size:.8rem;color:var(--text-secondary);}
.form-inline{display:flex;gap:1rem;flex-wrap:wrap;}
.form-inline .form-field{flex:1 1 220px;}
`;
if (typeof document !== 'undefined' && !document.getElementById('admin-panel-theme')) {
  const styleTag = document.createElement('style');
  styleTag.id = 'admin-panel-theme';
  styleTag.textContent = globalStyles;
  document.head.appendChild(styleTag);
}
// ---------- /NEW ----------

const debounce = (func, delay) => {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      func.apply(this, args);
    }, delay);
  };
};

const formatDuration = (start, end) => {
  if (!start || !end) return "—";
  const duration = (new Date(end) - new Date(start)) / 1000;
  const minutes = Math.floor(duration / 60);
  const seconds = Math.floor(duration % 60);
  return minutes > 0 ? `${minutes}м ${seconds}с` : `${seconds}с`;
};

const formatDate = (dateString) => {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
};

const SearchIcon = () => React.createElement("svg", { fill: "none", stroke: "currentColor", viewBox: "0 0 24 24" }, React.createElement("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "m21 21-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z" }));
const DownloadIcon = () => React.createElement("svg", { fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", width: "16", height: "16" }, React.createElement("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" }));
const BookIcon = () => React.createElement("svg", { fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", width: "16", height: "16" }, React.createElement("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" }));
const TrashIcon = () => React.createElement("svg", { fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", width: "16", height: "16" }, React.createElement("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" }));
const CloseIcon = () => React.createElement("svg", { fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", width: "20", height: "20" }, React.createElement("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M6 18L18 6M6 6l12 12" }));
const EmptyIcon = () => React.createElement("svg", { fill: "none", stroke: "currentColor", viewBox: "0 0 24 24" }, React.createElement("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707.293l-2.414-2.414A1 1 0 006.586 13H4" }));
const SortUpIcon = () => React.createElement("svg", { fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", width: "14", height: "14" }, React.createElement("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M5 15l7-7 7 7" }));
const SortDownIcon = () => React.createElement("svg", { fill: "none", stroke: "currentColor", viewBox: "0 0 24 24", width: "14", height: "14" }, React.createElement("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, d: "M19 9l-7 7-7-7" }));

// Toast компонент
const Toast = ({ toast, onClose }) => {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose(toast.id);
        }, toast.duration || 5000);
        return () => clearTimeout(timer);
    }, [toast.id, toast.duration, onClose]);

    return React.createElement("div", { className: `toast ${toast.type}` },
        React.createElement("div", { className: "toast-header" },
            React.createElement("div", { className: "toast-title" }, toast.title),
            React.createElement("button", { className: "toast-close", onClick: () => onClose(toast.id) },
                React.createElement(CloseIcon)
            )
        ),
        toast.message && React.createElement("div", { className: "toast-message" }, toast.message)
    );
};

const ToastContainer = ({ toasts, onClose }) => {
    if (!toasts.length) return null;
    return React.createElement("div", { className: "toast-container" },
        toasts.map(toast => React.createElement(Toast, { key: toast.id, toast, onClose }))
    );
};

// Скелетон для таблицы
const TableSkeleton = () => {
    const rows = Array.from({ length: 8 }, (_, i) => i);
    return React.createElement("div", { className: "skeleton-table" },
        React.createElement("div", { className: "skeleton-row" },
            React.createElement("div", { className: "skeleton skeleton-cell id" }),
            React.createElement("div", { className: "skeleton skeleton-cell phone" }),
            React.createElement("div", { className: "skeleton skeleton-cell date" }),
            React.createElement("div", { className: "skeleton skeleton-cell duration" }),
            React.createElement("div", { className: "skeleton skeleton-cell status" })
        ),
        rows.map(i => React.createElement("div", { key: i, className: "skeleton-row" },
            React.createElement("div", { className: "skeleton skeleton-cell id" }),
            React.createElement("div", { className: "skeleton skeleton-cell phone" }),
            React.createElement("div", { className: "skeleton skeleton-cell date" }),
            React.createElement("div", { className: "skeleton skeleton-cell duration" }),
            React.createElement("div", { className: "skeleton skeleton-cell status" })
        ))
    );
};

const StatsCard = ({ number, label, color = 'var(--primary)' }) => (
  React.createElement("div", { className: "stat-card", style: { borderColor: color } },
    React.createElement("div", { className: "stat-number", style: { color } }, number),
    React.createElement("div", { className: "stat-label" }, label)
  )
);

// ----------  NEW • StatsList ----------
const StatsList = ({ stats }) => (
    React.createElement("ul", { className: "stats-list" },
        React.createElement("li", null, 
            React.createElement("span", { className: "stat-icon" }, "📞"),
            React.createElement("span", { className: "stat-name" }, "Всего звонков"),
            React.createElement("span", { className: "stat-value", style: { color: 'var(--primary)' } }, stats.total)
        ),
        React.createElement("li", null,
            React.createElement("span", { className: "stat-icon" }, "✅"),
            React.createElement("span", { className: "stat-name" }, "Завершенных"),
            React.createElement("span", { className: "stat-value", style: { color: 'var(--success)' } }, stats.completed)
        ),
        React.createElement("li", null,
            React.createElement("span", { className: "stat-icon" }, "⚠️"),
            React.createElement("span", { className: "stat-name" }, "Прерванных"),
            React.createElement("span", { className: "stat-value", style: { color: 'var(--warning)' } }, stats.inprogress)
        ),
        React.createElement("li", null,
            React.createElement("span", { className: "stat-icon" }, "❌"),
            React.createElement("span", { className: "stat-name" }, "Неудачных"),
            React.createElement("span", { className: "stat-value", style: { color: 'var(--danger)' } }, stats.failed)
        )
    )
);

// Helper: извлечь kb из последнего ответа бота в транскрипте
const getKbFromLog = (log) => {
  try {
    const arr = JSON.parse(log.transcript_json || '[]');
    for (let i = arr.length - 1; i >= 0; i--) {
      const t = arr[i];
      if (t && t.speaker === 'bot' && t.kb) return t.kb;
    }
  } catch (e) { /* ignore */ }
  return null;
};

const LogTable = ({ logs, onRowClick, sortField, sortDirection, onSort }) => {
  if (!logs.length) {
    return (
      React.createElement("div", { className: "empty-state" },
        React.createElement(EmptyIcon, null),
        React.createElement("h3", null, "Нет логов"),
        React.createElement("p", null, "Логи звонков появятся здесь")
      )
    );
  }

  const headers = [
    { key: 'id', label: 'ID' },
    { key: 'callerId', label: 'Номер телефона' },
    { key: 'startTime', label: 'Время начала' },
    { key: 'duration', label: 'Длительность' },
    { key: 'status', label: 'Статус' }
  ];

  return (
    React.createElement("div", { className: "table-container" },
      React.createElement("table", { className: "table" },
        React.createElement("thead", null,
          React.createElement("tr", null, 
            headers.map(header => 
              React.createElement("th", { 
                key: header.key, 
                className: `sortable-header ${sortField === header.key ? 'active' : ''}`,
                onClick: () => onSort(header.key)
              }, 
                header.label,
                sortField === header.key && React.createElement("span", { className: "sort-icon" },
                  sortDirection === 'asc' ? React.createElement(SortUpIcon) : React.createElement(SortDownIcon)
                )
              )
            )
          )
        ),
        React.createElement("tbody", null,
          logs.map(log => {
            const kb = getKbFromLog(log);
            return (
              React.createElement("tr", { key: log.id, onClick: () => onRowClick(log) },
                React.createElement("td", null, React.createElement("code", null, `${(log.id || '').slice(0, 8)}…`)),
                React.createElement("td", null, log.callerId || '—'),
                React.createElement("td", null, formatDate(log.startTime)),
                React.createElement("td", null, formatDuration(log.startTime, log.endTime)),
                React.createElement("td", null,
                  React.createElement("span", { className: `status ${(log.status || '').toLowerCase()}` }, log.status),
                  kb ? React.createElement("span", { style:{marginLeft:'.5rem', fontSize:'.7rem', opacity:.8} }, `[${kb}]`) : null
                )
              )
            );
          })
        )
      )
    )
  );
};

const Modal = ({ log, onClose }) => {
    if (!log) return null;
    let transcript = [];
    try {
        transcript = log.transcript_json ? JSON.parse(log.transcript_json) : (log.transcript || []);
    } catch (e) {
        transcript = [{ speaker: 'system', text: 'Ошибка в формате диалога' }];
    }
    return React.createElement("div", { className: "modal show", onClick: onClose },
        React.createElement("div", { className: "modal-content", style:{maxWidth: '800px'}, onClick: e => e.stopPropagation() },
            React.createElement("div", { className: "modal-header" },
                React.createElement("h3", null, `Детали звонка`),
                React.createElement("button", { className: "close-btn", onClick: onClose }, React.createElement(CloseIcon))
            ),
            React.createElement("div", { className: "modal-body modal-body-padding" },
                React.createElement("div", { className: "info-grid" },
                    React.createElement("div", { className: "info-item" }, React.createElement("div", { className: "info-label" }, "ID звонка"), React.createElement("div", { className: "info-value" }, React.createElement("code", null, log.id))),
                    React.createElement("div", { className: "info-item" }, React.createElement("div", { className: "info-label" }, "Номер телефона"), React.createElement("div", { className: "info-value" }, log.callerId || "Не указан")),
                    React.createElement("div", { className: "info-item" }, React.createElement("div", { className: "info-label" }, "Время начала"), React.createElement("div", { className: "info-value" }, formatDate(log.startTime))),
                    React.createElement("div", { className: "info-item" }, React.createElement("div", { className: "info-label" }, "Время окончания"), React.createElement("div", { className: "info-value" }, formatDate(log.endTime))),
                    React.createElement("div", { className: "info-item" }, React.createElement("div", { className: "info-label" }, "Длительность"), React.createElement("div", { className: "info-value" }, formatDuration(log.startTime, log.endTime))),
                    React.createElement("div", { className: "info-item" }, React.createElement("div", { className: "info-label" }, "Статус"), React.createElement("div", { className: "info-value" }, React.createElement("span", { className: `status ${(log.status || '').toLowerCase()}` }, log.status)))
                ),
                React.createElement("div", { className: "transcript" },
                    React.createElement("h4", null, "Транскрипт разговора"),
                    transcript.map((turn, index) =>
                        React.createElement("div", { key: index, className: `turn ${turn.speaker}` },
                            React.createElement("div", null, turn.text),
                            (turn.speaker === 'bot' && turn.kb) ? React.createElement("div", { style:{ fontSize: '.75rem', opacity: .7, marginTop: '.25rem' } }, `[${turn.kb}]`) : null
                        )
                    )
                )
            )
        )
    );
};

const KnowledgeBaseModal = ({ content, onClose }) => {
    if (!content) return null;
    return React.createElement("div", { className: "modal show", onClick: onClose },
        React.createElement("div", { className: "modal-content", style:{maxWidth: '800px'}, onClick: e => e.stopPropagation() },
            React.createElement("div", { className: "modal-header" },
                React.createElement("h3", null, "База знаний"),
                React.createElement("button", { className: "close-btn", onClick: onClose }, React.createElement(CloseIcon))
            ),
            React.createElement("div", { className: "modal-body modal-body-padding" },
                React.createElement("pre", { style: { whiteSpace: 'pre-wrap', lineHeight: '1.6', background: 'var(--bg)', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--border)' } }, content.text || content.error)
            )
        )
    );
};

const ApiKeyModal = ({ onClose, onSave }) => {
    const [key, setKey] = useState('');
    return React.createElement("div", { className: "modal show", onClick: onClose },
        React.createElement("div", { className: "modal-content", style: { maxWidth: '500px' }, onClick: e => e.stopPropagation() },
            React.createElement("div", { className: "modal-header" },
                React.createElement("h3", null, "Введите API Ключ"),
                React.createElement("button", { className: "close-btn", onClick: onClose }, React.createElement(CloseIcon))
            ),
            React.createElement("div", { className: "modal-body-padding" },
                React.createElement("p", { style: { color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: 0 } }, "Для выполнения этого действия требуется API-ключ. Введите его ниже."),
                React.createElement("input", { 
                    type: "password", 
                    className: "search-input", 
                    style: { paddingLeft: '0.75rem', width: '100%' },
                    value: key,
                    onChange: e => setKey(e.target.value),
                    placeholder: "Ваш секретный ключ"
                })
            ),
            React.createElement("div", { className: "actions" },
                React.createElement("button", { className: "btn btn-secondary", onClick: onClose }, "Отмена"),
                React.createElement("button", { className: "btn btn-primary", onClick: () => onSave(key) }, "Сохранить и продолжить")
            )
        )
    );
};

// NEW: Settings modal for KB_TOP_K and KB_FALLBACK_THRESHOLD
const SettingsModal = ({ initial, onClose, fetchWithAuth }) => {
    const [k, setK] = useState(initial?.kb_top_k ?? 3);
    const [thr, setThr] = useState(initial?.kb_fallback_threshold ?? 0.2);
    const [modelPrimary, setModelPrimary] = useState(initial?.llm_model_primary || 'gpt-4o-mini');
    const [modelFallback, setModelFallback] = useState(initial?.llm_model_fallback || '');
    const [temperature, setTemperature] = useState(initial?.llm_temperature ?? 0.2);
    const [status, setStatus] = useState('');
    const save = async () => {
        setStatus('Сохранение...');
        try {
            // 1) Поисковые настройки
            const res1 = await fetchWithAuth('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kb_top_k: Number(k), kb_fallback_threshold: Number(thr) })
            });
            const data1 = await res1.json();
            if (!res1.ok) throw new Error(data1.detail || 'Ошибка сохранения (search)');
            // 2) Модельные настройки
            const res2 = await fetchWithAuth('/api/model-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    llm_model_primary: modelPrimary,
                    llm_model_fallback: modelFallback,
                    llm_temperature: Number(temperature)
                })
            });
            const data2 = await res2.json();
            if (!res2.ok) throw new Error(data2.detail || 'Ошибка сохранения (model)');
            setStatus('Настройки сохранены');
            setTimeout(onClose, 800);
        } catch (e) {
            setStatus('Ошибка: ' + e.message);
        }
    };
    return React.createElement('div', { className: 'modal show', onClick: onClose },
        React.createElement('div', { className: 'modal-content', style:{maxWidth:'620px'}, onClick: e=>e.stopPropagation() },
            React.createElement('div', { className: 'modal-header' },
                React.createElement('h3', null, 'Настройки поиска'),
                React.createElement('button', { className: 'close-btn', onClick: onClose }, React.createElement(CloseIcon))
            ),
            React.createElement('div', { className: 'modal-body-padding' },
                React.createElement('div', { className: 'form-inline' },
                    React.createElement('div', { className: 'form-field' },
                        React.createElement('label', { className: 'prompt-label' }, 'Сколько документов брать (k)'),
                        React.createElement('input', { type:'number', min:1, max:20, value:k, onChange: e=>setK(e.target.value), className:'search-input', style:{maxWidth:'160px'} })
                    ),
                    React.createElement('div', { className: 'form-field' },
                        React.createElement('label', { className: 'prompt-label' }, 'Порог уверенности (0..1)'),
                        React.createElement('input', { type:'number', step:'0.05', min:0, max:1, value:thr, onChange: e=>setThr(e.target.value), className:'search-input', style:{maxWidth:'160px'} })
                    )
                ),
                React.createElement('div', { className: 'form-field' },
                    React.createElement('label', { className: 'prompt-label' }, 'Основная модель (PRIMARY)'),
                    React.createElement('input', { type:'text', value:modelPrimary, onChange: e=>setModelPrimary(e.target.value), className:'search-input', placeholder:'например, gpt-4o-mini' })
                ),
                React.createElement('div', { className: 'form-field' },
                    React.createElement('label', { className: 'prompt-label' }, 'Запасная модель (FALLBACK, опционально)'),
                    React.createElement('input', { type:'text', value:modelFallback, onChange: e=>setModelFallback(e.target.value), className:'search-input', placeholder:'например, gpt-4o-mini-mini' }),
                    React.createElement('div', { className:'hint' }, 'Оставьте пустым, если не используете фолбэк')
                ),
                React.createElement('div', { className: 'form-field' },
                    React.createElement('label', { className: 'prompt-label' }, 'Температура (0..1)'),
                    React.createElement('input', { type:'number', step:'0.05', min:0, max:1, value:temperature, onChange: e=>setTemperature(e.target.value), className:'search-input', style:{maxWidth:'160px'} }),
                    React.createElement('div', { className:'hint' }, '0 — максимально детерминированный ответ; 0.7–0.9 — более креативный')
                ),
                status && React.createElement('div', { style:{marginTop:'0.5rem', color:'var(--text-secondary)'} }, status)
            ),
            React.createElement('div', { className:'actions' },
                React.createElement('button', { className:'btn btn-secondary', onClick:onClose }, 'Отмена'),
                React.createElement('button', { className:'btn', onClick:save }, 'Сохранить')
            )
        )
    );
};

// NEW: Help / instruction modal
const HelpModal = ({ onClose }) => {
  const [text, setText] = React.useState('Загрузка инструкции...');
  React.useEffect(() => {
    fetch('instruction.md').then(r => r.text()).then(setText).catch(() => setText('Не удалось загрузить instruction.md'));
  }, []);
  return React.createElement('div', { className:'modal show', onClick:onClose },
    React.createElement('div', { className:'modal-content', style:{maxWidth:'720px'}, onClick:e=>e.stopPropagation() },
      React.createElement('div', { className:'modal-header' },
        React.createElement('h3', null, 'Инструкция по настройке'),
        React.createElement('button', { className:'close-btn', onClick:onClose }, React.createElement(CloseIcon))
      ),
      React.createElement('div', { className:'modal-body' },
        React.createElement('div', { className:'modal-body-padding' },
          React.createElement('pre', { style:{ whiteSpace:'pre-wrap', lineHeight:'1.6' } }, text)
        )
      ),
      React.createElement('div', { className:'actions' },
        React.createElement('button', { className:'btn', onClick:onClose }, 'Понятно')
      )
    )
  );
};


const PromptsModal = ({ onClose, fetchWithAuth }) => {
    const [prompts, setPrompts] = useState(null);
    const [originalPrompts, setOriginalPrompts] = useState(null);
    const [status, setStatus] = useState("");
    const [activeTab, setActiveTab] = useState('greeting');

    useEffect(() => {
        setStatus("Загрузка промптов...");
        fetch('/api/prompts')
            .then(res => {
                if (!res.ok) throw new Error("Ошибка сети");
                return res.json();
            })
            .then(data => {
                setPrompts(data);
                setOriginalPrompts(data);
                setStatus("");
            })
            .catch(() => setStatus("Ошибка загрузки промптов"));
    }, []);

    const handleChange = (e) => {
        setPrompts({ ...prompts, [e.target.name]: e.target.value });
    };
    
    const handleReset = () => {
        if(confirm("Вы уверены, что хотите сбросить все изменения?")) {
            setPrompts(originalPrompts);
            setStatus("Изменения сброшены");
             setTimeout(() => setStatus(""), 3000);
        }
    };

    const handleSave = async () => {
        setStatus("Сохранение...");
        try {
            const response = await fetchWithAuth('/api/prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(prompts),
            });
            const result = await response.json();
            if (response.ok) {
                setStatus("Промпты успешно сохранены!");
                setOriginalPrompts(prompts);
            } else {
                throw new Error(result.error || result.detail || "Неизвестная ошибка");
            }
        } catch (err) {
            setStatus(`Ошибка сохранения: ${err.message}`);
        }
        setTimeout(() => setStatus(""), 5000);
    };

    const renderTabContent = () => {
        if (!prompts) return React.createElement("div", {className: "spinner-wrapper"}, React.createElement("div", {className: "spinner"}));

        const tabsData = {
            greeting: { title: "Приветственное сообщение", desc: "Текст, который бот произносит в начале каждого звонка", name: "greeting", rows: 3 },
            context: { title: "Контекстуализация", desc: "Инструкции для модели о том, как переформулировать вопросы пользователя с учетом контекста беседы.", name: "contextualize_q_system_prompt", rows: 8 },
            system: { title: "Системный промпт", desc: "Главные инструкции для модели, определяющие поведение, стиль общения и функциональность бота.", name: "qa_system_prompt", rows: 12 }
        };

        return Object.keys(tabsData).map(key => {
            const currentTabData = tabsData[key];
            return React.createElement("div", { key: key, className: `tab-content ${activeTab === key ? 'active' : ''}`},
                React.createElement("div", {className: "prompt-group"},
                    React.createElement("div", {className: "prompt-label"}, currentTabData.title),
                    React.createElement("div", {className: "prompt-description"}, currentTabData.desc),
                    React.createElement("textarea", { 
                        name: currentTabData.name, 
                        className: "prompt-textarea", 
                        value: prompts[currentTabData.name], 
                        onChange: handleChange, 
                        rows: currentTabData.rows
                    })
                )
            );
        });
    };

    return React.createElement("div", { className: "modal show", onClick: onClose },
        React.createElement("div", { className: "modal-content", style: { maxWidth: '1000px' }, onClick: e => e.stopPropagation() },
            React.createElement("div", { className: "modal-header" },
                React.createElement("h3", null, "Управление промптами"),
                React.createElement("button", { className: "close-btn", onClick: onClose }, React.createElement(CloseIcon))
            ),
            React.createElement("div", { className: "modal-body" },
                React.createElement("div", { className: "tabs" },
                    React.createElement("div", { className: `tab ${activeTab === 'greeting' ? 'active' : ''}`, onClick: () => setActiveTab('greeting') }, "Приветствие"),
                    React.createElement("div", { className: `tab ${activeTab === 'context' ? 'active' : ''}`, onClick: () => setActiveTab('context') }, "Контекстуализация"),
                    React.createElement("div", { className: `tab ${activeTab === 'system' ? 'active' : ''}`, onClick: () => setActiveTab('system') }, "Системный промпт")
                ),
                renderTabContent()
            ),
            React.createElement("div", { className: "actions" },
                 React.createElement("button", { className: "btn btn-secondary", onClick: handleReset }, "Сбросить"),
                 React.createElement("p", { className: "status-message" }, status),
                 React.createElement("button", { className: "btn btn-primary", onClick: handleSave }, "Сохранить промпты")
            )
        )
    );
};


const App = () => {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [query, setQuery] = useState("");
    const [modalLog, setModalLog] = useState(null);
    const [kbContent, setKbContent] = useState(null);
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [uploadStatus, setUploadStatus] = useState('');
    const [showPromptsModal, setShowPromptsModal] = useState(false);
    const [activeQuickFilter, setActiveQuickFilter] = useState('');
    const [toasts, setToasts] = useState([]);
    const [statusFilter, setStatusFilter] = useState('');
    const [sortField, setSortField] = useState('startTime');
    const [sortDirection, setSortDirection] = useState('desc');
    const [apiKey, setApiKey] = useState(null);
    const [showApiKeyModal, setShowApiKeyModal] = useState(false);
    const [apiKeyCallback, setApiKeyCallback] = useState(null);
    const [settings, setSettings] = useState(null);
  const [helpOpen, setHelpOpen] = useState(false);

    useEffect(() => {
        const storedKey = sessionStorage.getItem('api_secret_key');
        if (storedKey) {
            setApiKey(storedKey);
        }
    }, []);

    const requestApiKey = useCallback((callback) => {
        const storedKey = sessionStorage.getItem('api_secret_key');
        if (storedKey) {
            setApiKey(storedKey); // Убедимся что стейт свежий
            callback(storedKey);
        } else {
            setApiKeyCallback(() => callback);
            setShowApiKeyModal(true);
        }
    }, []);
    
    const handleApiKeySave = (key) => {
        if (key) {
            sessionStorage.setItem('api_secret_key', key);
            setApiKey(key);
            if (apiKeyCallback) {
                apiKeyCallback(key);
            }
        }
        setShowApiKeyModal(false);
        setApiKeyCallback(null);
    };

    const fetchWithAuth = useCallback((url, options = {}) => {
        return new Promise((resolve, reject) => {
            const performFetch = (key) => {
                if (!key) {
                    // Если ключ так и не получен, отклоняем промис
                    const err = new Error("API ключ не предоставлен.");
                    showToast("Ошибка", err.message, "error");
                    return reject(err);
                }
                const headers = { ...options.headers, 'X-API-Key': key };
                fetch(url, { ...options, headers }).then(resolve, reject);
            };

            const currentApiKey = sessionStorage.getItem('api_secret_key');
            if (currentApiKey) {
                performFetch(currentApiKey);
            } else {
                requestApiKey(newKey => performFetch(newKey));
            }
        });
    }, [requestApiKey]); // showToast не меняется, requestApiKey мемоизирован

    const openSettings = async () => {
        try {
            const res = await fetch('/api/settings');
            const data = await res.json();
            setSettings(data);
        } catch (e) {
            showToast('Ошибка', 'Не удалось загрузить настройки', 'error');
        }
    };
    
    const stats = useMemo(() => {
        const lower = s => (s || '').toLowerCase();
        const total = logs.length;
        const completed = logs.filter(l => lower(l.status) === 'completed').length;
        const failed = logs.filter(l => lower(l.status) === 'failed').length;
        const interrupted = logs.filter(l => lower(l.status) === 'interrupted').length;
        const inprogress = logs.filter(l => lower(l.status) === 'inprogress').length;
        const initiated = logs.filter(l => lower(l.status) === 'initiated').length;
        return { total, completed, failed, interrupted, inprogress, initiated };
    }, [logs]);

    const filteredLogs = useMemo(() => {
        let filtered = logs;
        
        if (statusFilter) {
            filtered = filtered.filter(log => {
                const status = (log.status || '').toLowerCase();
                return status === statusFilter.toLowerCase();
            });
        }
        
        return [...filtered].sort((a, b) => {
            let aVal, bVal;
            
            switch(sortField) {
                case 'startTime':
                    aVal = new Date(a.startTime || 0).getTime();
                    bVal = new Date(b.startTime || 0).getTime();
                    break;
                case 'duration':
                    aVal = a.endTime && a.startTime ? new Date(a.endTime) - new Date(a.startTime) : 0;
                    bVal = b.endTime && b.startTime ? new Date(b.endTime) - new Date(b.startTime) : 0;
                    break;
                case 'callerId':
                    aVal = a.callerId || '';
                    bVal = b.callerId || '';
                    break;
                case 'status':
                    aVal = a.status || '';
                    bVal = b.status || '';
                    break;
                case 'id':
                default:
                    aVal = a.id || '';
                    bVal = b.id || '';
                    break;
            }
            
            if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
            if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
            return 0;
        });
    }, [logs, statusFilter, sortField, sortDirection]);

    const setQuickFilter = (filterType) => {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const weekAgo = new Date(today);
        weekAgo.setDate(weekAgo.getDate() - 7);

        const formatDate = (date) => date.toISOString().split('T')[0];

        switch(filterType) {
            case 'today':
                setDateFrom(formatDate(today));
                setDateTo(formatDate(today));
                setActiveQuickFilter('today');
                break;
            case 'yesterday':
                setDateFrom(formatDate(yesterday));
                setDateTo(formatDate(yesterday));
                setActiveQuickFilter('yesterday');
                break;
            case 'week':
                setDateFrom(formatDate(weekAgo));
                setDateTo(formatDate(today));
                setActiveQuickFilter('week');
                break;
            case 'clear':
                setDateFrom('');
                setDateTo('');
                setActiveQuickFilter('');
                break;
        }
    };

    const showToast = (title, message, type = 'info', duration = 5000) => {
        const id = Date.now() + Math.random();
        const newToast = { id, title, message, type, duration };
        setToasts(prev => [...prev, newToast]);
    };

    const closeToast = (id) => {
        setToasts(prev => prev.filter(toast => toast.id !== id));
    };

    const handleSort = (field) => {
        if (sortField === field) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortDirection('desc');
        }
    };

    const fetchLogs = async (searchQuery, isInitialLoad = false) => {
        if (isInitialLoad) setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            if (searchQuery) params.append('q', searchQuery);
            if (dateFrom) params.append('date_from', new Date(dateFrom).toISOString());
            if (dateTo) params.append('date_to', new Date(dateTo).toISOString());
            const url = `/logs?${params.toString()}`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Ошибка ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();
            setLogs(Array.isArray(data) ? data : []);
        } catch (err) {
            setError(err.message);
            setLogs([]);
        } finally {
            if (isInitialLoad) setLoading(false);
        }
    };

    const showKnowledgeBase = async () => {
        try {
            const response = await fetch("/kb");
            const data = await response.json();
            setKbContent(data);
        } catch (err) {
            setKbContent({ error: "Ошибка загрузки базы знаний" });
        }
    };

    // NEW: показать TECH базу знаний
    const showKnowledgeBaseTech = async () => {
        try {
            const response = await fetch("/kb2");
            const data = await response.json();
            setKbContent(data);
        } catch (err) {
            setKbContent({ error: "Ошибка загрузки TECH базы знаний" });
        }
    };

    const clearAllLogs = async () => {
        if (window.confirm("Вы уверены, что хотите удалить ВСЕ логи? Это действие необратимо.")) {
            setError(null);
            try {
                const response = await fetchWithAuth("/logs", { method: 'DELETE' });
                if (!response.ok) {
                    const res = await response.json();
                    throw new Error(res.detail || `Ошибка: Неверный API-ключ или другая ошибка сервера.`);
                }
                showToast("Успешно", "Все логи были удалены", "success");
                fetchLogs(query, true);
            } catch (err) {
                showToast("Ошибка", err.message, "error");
                setError(err.message);
            }
        }
    };

    const handleKbUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        if (!file.name.endsWith('.md')) {
            setUploadStatus('Ошибка: Пожалуйста, выберите .md файл.');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        setUploadStatus('Загрузка файла и обновление базы...');
        setError(null);
        try {
            const response = await fetchWithAuth('/kb/upload', {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();
            if (response.ok) {
                setUploadStatus(`Успешно: ${result.message}`);
                showToast("База знаний обновлена", result.message, "success");
            } else {
                throw new Error(result.detail || `Ошибка: Неверный API-ключ или другая ошибка сервера.`);
            }
        } catch (err) {
            setUploadStatus(`Ошибка: ${err.message}`);
            showToast("Ошибка загрузки", err.message, "error");
            setError(err.message);
        }
    };

    // NEW: загрузить TECH базу знаний
    const handleKbUploadTech = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        if (!file.name.endsWith('.md')) {
            setUploadStatus('Ошибка: Пожалуйста, выберите .md файл.');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        setUploadStatus('Загрузка TECH базы и обновление индексов...');
        setError(null);
        try {
            const response = await fetchWithAuth('/kb2/upload', {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();
            if (response.ok) {
                setUploadStatus(`Успешно: ${result.message}`);
                showToast("TECH база знаний обновлена", result.message, "success");
            } else {
                throw new Error(result.detail || `Ошибка: Неверный API-ключ или другая ошибка сервера.`);
            }
        } catch (err) {
            setUploadStatus(`Ошибка: ${err.message}`);
            showToast("Ошибка загрузки TECH базы", err.message, "error");
            setError(err.message);
        }
    };

    useEffect(() => {
        fetchLogs(query, true);
        const intervalId = setInterval(() => {
            if (document.activeElement.tagName !== 'INPUT' && document.activeElement.type !== 'date' && !document.querySelector('.modal.show')) {
                fetchLogs(query);
            }
        }, 5000);
        return () => clearInterval(intervalId);
    }, [query, dateFrom, dateTo]);

    return React.createElement("div", { className: "container" },
        React.createElement("div", { className: "header" },
            React.createElement("h1", null, "Admin Panel"),
            React.createElement("div", null, "Логи звонков")
        ),
        React.createElement(StatsList, { stats: stats }),
        React.createElement("div", { className: "quick-filters" },
            React.createElement("button", { 
                className: `quick-filter ${activeQuickFilter === 'today' ? 'active' : ''}`, 
                onClick: () => setQuickFilter('today') 
            }, "Сегодня"),
            React.createElement("button", { 
                className: `quick-filter ${activeQuickFilter === 'yesterday' ? 'active' : ''}`, 
                onClick: () => setQuickFilter('yesterday') 
            }, "Вчера"),
            React.createElement("button", { 
                className: `quick-filter ${activeQuickFilter === 'week' ? 'active' : ''}`, 
                onClick: () => setQuickFilter('week') 
            }, "Эта неделя"),
            React.createElement("button", { 
                className: `quick-filter ${activeQuickFilter === '' ? 'active' : ''}`, 
                onClick: () => setQuickFilter('clear') 
            }, "Все")
        ),
        React.createElement("div", { className: "controls" },
            React.createElement("div", { className: "search-row" },
                React.createElement("div", { className: "search-container" },
                    React.createElement(SearchIcon),
                    React.createElement("input", { type: "text", className: "search-input", placeholder: "Поиск по номеру или диалогу...", value: query, onChange: (e) => setQuery(e.target.value) })
                ),
                React.createElement("input", { type: "date", className: "search-input", value: dateFrom, onChange: (e) => setDateFrom(e.target.value) }),
                React.createElement("input", { type: "date", className: "search-input", value: dateTo, onChange: (e) => setDateTo(e.target.value) })
            ),
            React.createElement("div", { className: "actions-row" },
                React.createElement("a", { href: "/logs/csv", className: "btn btn-success", style: { pointerEvents: !logs.length ? "none" : "auto", opacity: !logs.length ? 0.5 : 1 } }, React.createElement(DownloadIcon), "Экспорт CSV"),
                React.createElement("button", { className: "btn", onClick: showKnowledgeBase }, React.createElement(BookIcon), "База знаний (general)"),
                React.createElement("button", { className: "btn", onClick: showKnowledgeBaseTech }, React.createElement(BookIcon), "База знаний (tech)"),
                React.createElement("label", { htmlFor: "kb-upload", className: "btn" }, "Обновить БЗ (general)", React.createElement("input", { id: "kb-upload", type: "file", accept: ".md", style: { display: "none" }, onChange: handleKbUpload })),
                React.createElement("label", { htmlFor: "kb2-upload", className: "btn" }, "Обновить БЗ (tech)", React.createElement("input", { id: "kb2-upload", type: "file", accept: ".md", style: { display: "none" }, onChange: handleKbUploadTech })),
                React.createElement("button", { className: "btn", onClick: () => setShowPromptsModal(true) }, "Упр. промптами"),
                React.createElement("button", { className: "btn btn-secondary", onClick: openSettings }, "Настройки поиска"),
                React.createElement("button", { className: "btn btn-secondary", onClick: () => setHelpOpen(true) }, "Инструкция по настройке"),
                React.createElement("button", { className: "btn btn-danger", onClick: clearAllLogs, disabled: !logs.length }, React.createElement(TrashIcon), "Очистить логи")
            )
        ),
        uploadStatus && React.createElement("div", { className: uploadStatus.startsWith('Ошибка') ? "error" : "success-message" }, uploadStatus),
        error && React.createElement("div", { className: "error" }, `⚠️ ${error}`),
        React.createElement("div", { className: "status-filters" },
            React.createElement("span", { className: "status-filters-label" }, "Фильтр по статусу:"),
            React.createElement("button", { 
                className: `status-chip all ${statusFilter === '' ? 'active' : ''}`, 
                onClick: () => setStatusFilter('') 
            }, 
                "Все", 
                React.createElement("span", { className: "status-chip-count" }, stats.total)
            ),
            React.createElement("button", { 
                className: `status-chip completed ${statusFilter === 'completed' ? 'active' : ''}`, 
                onClick: () => setStatusFilter('completed') 
            }, 
                "✅ Завершенные", 
                React.createElement("span", { className: "status-chip-count" }, stats.completed)
            ),
            React.createElement("button", { 
                className: `status-chip inprogress ${statusFilter === 'inprogress' ? 'active' : ''}`, 
                onClick: () => setStatusFilter('inprogress') 
            }, 
                "⚠️ Прерванные", 
                React.createElement("span", { className: "status-chip-count" }, stats.inprogress)
            ),
            React.createElement("button", { 
                className: `status-chip failed ${statusFilter === 'failed' ? 'active' : ''}`, 
                onClick: () => setStatusFilter('failed') 
            }, 
                "❌ Неудачные", 
                React.createElement("span", { className: "status-chip-count" }, stats.failed)
            )
        ),
        loading ? React.createElement(TableSkeleton) : React.createElement(LogTable, { 
            logs: filteredLogs, 
            onRowClick: setModalLog,
            sortField,
            sortDirection,
            onSort: handleSort
        }),
        React.createElement(Modal, { log: modalLog, onClose: () => setModalLog(null) }),
        settings && React.createElement(SettingsModal, { initial: settings, onClose: () => setSettings(null), fetchWithAuth }),
        helpOpen && React.createElement(HelpModal, { onClose: () => setHelpOpen(false) }),
        React.createElement(KnowledgeBaseModal, { content: kbContent, onClose: () => setKbContent(null) }),
        showPromptsModal && React.createElement(PromptsModal, { onClose: () => setShowPromptsModal(false), fetchWithAuth: fetchWithAuth }),
        showApiKeyModal && React.createElement(ApiKeyModal, { onClose: () => handleApiKeySave(null), onSave: handleApiKeySave }),
        React.createElement(ToastContainer, { toasts, onClose: closeToast })
    );
};

createRoot(document.getElementById("root")).render(React.createElement(App));
